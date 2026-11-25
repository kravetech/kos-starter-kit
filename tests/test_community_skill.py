"""Exercise the shared Skill through the same packaged CLI that an owner uses."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import community_skill as cli


class CommunitySkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = tempfile.TemporaryDirectory()
        cls.addClassCleanup(parent.cleanup)
        cls.template = Path(parent.name) / "base"
        kit = ROOT / "examples/project-action-list"
        installer = [sys.executable, "-B", str(ROOT / "installer/install.py"),
                     "--target", str(cls.template), "--approve"]
        for command in [
            ["--operation", "new", "--answers", str(ROOT / "installer/answers.example.json")],
            ["--package-command", "install", "--package", str(kit / "skill")],
            ["--package-command", "enable", "--id", "project-action-list-skill"],
            ["--package-command", "install", "--package", str(kit / "powerup"), "--approve-permissions"],
            ["--package-command", "enable", "--id", "project-action-list"],
        ]:
            proc = subprocess.run(installer + command, capture_output=True, timeout=120)
            if proc.returncode:
                raise AssertionError((command[0:2], proc.stdout[-500:], proc.stderr[-500:]))

    def setUp(self):
        parent = tempfile.TemporaryDirectory()
        self.addCleanup(parent.cleanup)
        self.vault = Path(parent.name) / "DemoVault"
        shutil.copytree(self.template, self.vault)
        self.project = cli.lifecycle.project_path(self.vault, "Sample")
        cli.lifecycle.initialize(self.project)
        token = cli.lifecycle.review(self.project)["review_token"]
        cli.lifecycle.approve(self.project, token)
        self.activation = {"schemaVersion": "1.0.0", "packages": {"project-action-list": {"enabled": True}}}
        self.set_activation()
        self.note = self.project / "Meeting.md"
        self.note.write_text("---\nai_access: internal\n---\nPrivate prose.\n- [ ] Publish notes.\n"
                             "```text\n- [ ] Code example.\n```\n- [x] Finished.\n  * [ ] Check dates.\n", encoding="utf-8")

    def set_activation(self):
        (self.project / "power-ups.json").write_text(json.dumps(self.activation), encoding="utf-8")

    def command(self, provider, operation, *extra):
        return ["--vault", str(self.vault), "--project", self.project.name, "--power-up", "project-action-list",
                "--provider", provider, operation, "--source", self.note.name, *extra]

    def invoke(self, provider, operation, *extra, stdin=None, code=0):
        command = [sys.executable, "-B", str(ROOT / "scripts/community_skill.py"),
                   *self.command(provider, operation, *extra)]
        proc = subprocess.run(command, input=stdin, capture_output=True, timeout=60)
        self.assertEqual(proc.returncode, code, proc.stdout[-600:])
        return json.loads(proc.stdout)

    def test_installed_meeting_template_generates_cited_actions_and_survives_upgrade(self):
        template = self.vault / "08 - Templates/Meetings/Meeting-Note.md"
        text = template.read_text(encoding="utf-8")
        action = "Review the revised agenda."
        self.note.write_text(text.replace("[Next step]", action), encoding="utf-8")
        prepared = self.invoke("codex", "prepare")
        expected = [{"path": self.note.name, "line": text.splitlines().index("- [ ] [Next step]") + 1,
                     "text": action}]
        self.assertEqual(prepared["candidates"], expected)
        saved = self.invoke("codex", "save", "--preparation-sha256", prepared["preparationSha256"],
                            "--output", "meeting-actions.json")
        output = self.project / saved["output"]
        self.assertEqual(json.loads(output.read_bytes()), {"actions": expected})

        template.write_bytes(template.read_bytes() + b"\n## Additional notes\n")
        before = {path: path.read_bytes() for path in (template, self.note, output)}
        upgrade = subprocess.run(
            [sys.executable, "-B", str(ROOT / "installer/install.py"), "--operation", "upgrade",
             "--target", str(self.vault), "--answers", str(ROOT / "installer/answers.example.json"), "--approve"],
            capture_output=True, timeout=120)
        self.assertEqual(upgrade.returncode, 0, upgrade.stdout[-600:])
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_three_clients_resolve_one_skill_and_verified_output_never_overwrites(self):
        runs = [self.invoke(name, "prepare") for name in cli.PROVIDERS]
        self.assertEqual(len({run["skill"]["sha256"] for run in runs}), 1)
        for run in runs:
            self.assertEqual(run["candidates"], [
                {"path": "Meeting.md", "line": 5, "text": "Publish notes."},
                {"path": "Meeting.md", "line": 10, "text": "Check dates."}])
            self.assertNotIn("Private prose", json.dumps(run))
            self.assertNotIn("Code example", json.dumps(run))
            self.assertFalse(run["truncated"])
        preparation_sha = runs[0]["preparationSha256"]
        args = ["--preparation-sha256", preparation_sha, "--output", "actions.json", "--response-stdin"]
        wrong = json.dumps({"actions": []}).encode()
        denied = self.invoke(cli.PROVIDERS[0], "save", *args, stdin=wrong, code=2)
        self.assertEqual(denied["error"], "PROVIDER_RESPONSE_MISMATCH")
        self.assertFalse((self.project / "Results").exists())
        data = {"actions": runs[0]["candidates"]}
        response = json.dumps(data).encode()
        saved = self.invoke(cli.PROVIDERS[0], "save", *args, stdin=response)
        self.assertEqual(saved["output"], "Results/actions.json")
        self.assertEqual(json.loads((self.project / saved["output"]).read_bytes()), data)
        self.assertEqual(self.invoke(cli.PROVIDERS[0], "save", *args, stdin=response, code=2)["error"],
                         "OUTPUT_ALREADY_EXISTS")

    def test_project_opt_in_precedes_context_and_integrity_precedes_source_reads(self):
        prepared = self.invoke("gemini", "prepare")
        args = cli.arguments(self.command("gemini", "prepare"))
        with patch.object(cli.lifecycle, "check", side_effect=AssertionError("early context read")):
            self.activation["packages"]["project-action-list"]["enabled"] = False
            self.set_activation()
            with self.assertRaisesRegex(cli.Blocked, "OPT_IN"):
                cli.prepare(args)
            self.activation["packages"]["project-action-list"]["enabled"] = True
            self.set_activation()
            entry = self.vault / prepared["skill"]["entrypoint"]
            entry.write_bytes(entry.read_bytes() + b"\nEdited instructions\n")
            with self.assertRaisesRegex(cli.Blocked, "MODIFIED"):
                cli.prepare(args)

    def test_customer_kit_accepts_relative_vault_for_prepare_and_save(self):
        kit = self.vault.parent / "kit"
        for directory in ("scripts", "installer"):
            shutil.copytree(ROOT / directory, kit / directory)
        prefix = [sys.executable, "-B", "scripts/community_skill.py", "--vault", "../DemoVault",
                  "--project", self.project.name, "--power-up", "project-action-list", "--provider", "gemini"]
        def from_kit(*args):
            result = subprocess.run(prefix + list(args), cwd=kit, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout[-500:])
            return json.loads(result.stdout)
        prepared = from_kit("prepare", "--source", self.note.name)
        self.assertEqual(prepared, self.invoke("gemini", "prepare"))
        saved = from_kit("save", "--source", self.note.name, "--preparation-sha256", prepared["preparationSha256"],
                         "--output", "relative.json")
        self.assertEqual(saved["preparationSha256"], prepared["preparationSha256"])
        self.assertEqual(json.loads((self.project / saved["output"]).read_bytes()), {"actions": prepared["candidates"]})

    def test_visible_tasks_preserve_citations_and_omit_hidden_comments_and_code(self):
        lines = ["---", "ai_access: internal", "---",
                 "- [ ] Collect <!-- hidden inline -->notes.",
                 "%%", "- [ ] hidden Obsidian task", "```", "%%",
                 "<!--", "- [ ] hidden HTML task", "-->",
                 "    - [ ] hidden indented example", "\t- [ ] hidden tab example",
                 "  * [ ] Send%%hidden inline%% agenda.", "```md", "%%", "- [ ] hidden fenced example", "```",
                 "+ [ ] Review `draft` today. %%hidden until end", "- [ ] hidden trailing task"]
        self.note.write_text("\n".join(lines), encoding="utf-8")
        result = self.invoke("gemini", "prepare")
        expected = [{"path": "Meeting.md", "line": n, "text": t} for n, t in
                    [(4, "Collect notes."), (14, "Send agenda."), (19, "Review `draft` today.")]]
        self.assertEqual(result["candidates"], expected)
        self.assertNotIn("hidden", json.dumps(result["candidates"]))
        self.invoke("gemini", "save", "--run-token", result["preparationSha256"], "--output", "visible.json")
        self.assertEqual(json.loads((self.project / "Results/visible.json").read_bytes())["actions"], expected)

    def test_reclassification_context_edits_limits_and_incomplete_selection(self):
        self.activation["packages"]["project-action-list"]["configuration"] = {"maxActions": 1}
        self.set_activation()
        prepared = self.invoke("claude", "prepare")
        self.assertTrue(prepared["truncated"])
        self.assertEqual(len(prepared["candidates"]), 1)
        args = ["--preparation-sha256", prepared["preparationSha256"], "--output", "new.json"]
        self.note.write_bytes(self.note.read_bytes() + b"\nExtra prose.\n")
        self.assertIn("PREPARATION_CHANGED", self.invoke("claude", "save", *args, code=2)["error"])
        other = self.project / "Other.md"
        other.write_text("---\nai_access: restricted\n---\n- [ ] Restricted sample\n", encoding="utf-8")
        refused = self.invoke("claude", "prepare", "--source", "Other.md", code=2)
        self.assertIn("restricted", refused["error"])
        self.assertNotIn("Restricted sample", json.dumps(refused))
        handoff = self.project / "handoff.md"
        handoff.write_bytes(handoff.read_bytes() + b"\nDraft change\n")
        self.assertEqual(self.invoke("claude", "save", *args, code=2)["error"], "PROJECT_CONTEXT_REVIEW_REQUIRED")
        self.assertFalse((self.project / "Results").exists())
