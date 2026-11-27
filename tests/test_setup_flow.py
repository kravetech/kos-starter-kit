"""Exercise the guided workflow through the real packaged engine on disposable vaults."""
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import tempfile
from types import SimpleNamespace
import unittest

from test_safety import ROOT, STATE, RUNS, Blocked
from contracts import RELEASE
from safety import encoded, json_read
from setup_backup import snapshot
from setup_flow import console, describe_preview, setup


class GuidedSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()
        self.vault = self.parent / "My Workspace"
        self.output = []
        self.prompts = []
        self.release = SimpleNamespace(root=ROOT, version=RELEASE["starterKitVersion"],
                                       community_version=RELEASE["communityVersion"],
                                       changes_since=lambda _: [{"version": RELEASE["communityVersion"],
                                                                "complete": True, "changes": ["Example release change."]}])

    def invoke(self, *approvals, hook=None):
        answers = iter(approvals)
        def confirm(question, details):
            self.prompts.append(question)
            if hook:
                hook(question)
            return next(answers)
        return setup(self.release, self.vault, ask=confirm, adapter="gemini",
                     emit=lambda title, value: self.output.append((title, value)))

    def older(self):
        self.invoke(True)
        path = self.vault / STATE
        state = json_read(path)
        for key in ("communityVersion", "starterKitVersion", "installerVersion"):
            state[key] = "1.3.1"
        path.write_bytes(encoded(state))
        self.output.clear()
        self.prompts.clear()

    def test_fresh_and_current(self):
        self.assertEqual(self.invoke(False), "cancelled")
        self.assertFalse(self.vault.exists())
        self.assertEqual(self.invoke(True), "installed")
        report = self.output[-1][1]
        self.assertEqual(report["validation"]["status"], "PASS")
        self.assertIn("README.md", report["changes"]["created"])
        self.assertEqual(report["initialLinks"]["unresolved"], [])
        self.assertEqual(report["enabledAdapters"], ["gemini"])
        self.assertEqual(report, json_read(Path(report["report"])))
        before = snapshot(self.vault)
        self.assertEqual(self.invoke(), "current")
        self.assertEqual(snapshot(self.vault), before)
        run = Path(report["journal"])
        failed = json_read(run)
        failed["status"] = "failed"
        run.write_bytes(encoded(failed))
        with self.assertRaisesRegex(Blocked, "REVIEW_PREVIOUS_RUN"):
            self.invoke()

    def test_unrecognized_obsidian_pro_and_hidden_content(self):
        self.vault.mkdir()
        (self.vault / ".private").touch()
        with self.assertRaisesRegex(Blocked, "recognized vault"):
            self.invoke()
        (self.vault / ".obsidian").mkdir()
        with self.assertRaisesRegex(Blocked, "Obsidian"):
            self.invoke()
        version = self.vault / "00 - System/Core/version.json"
        version.parent.mkdir(parents=True)
        version.write_text('{"edition":"pro"}')
        with self.assertRaisesRegex(Blocked, "Pro installer"):
            self.invoke()
        self.assertEqual(self.prompts, [])

    def test_drift_during_new_approval(self):
        def occupy(_):
            self.vault.mkdir()
            (self.vault / "notes.md").write_text("mine")
        with self.assertRaisesRegex(Blocked, "changed"):
            self.invoke(True, hook=occupy)
        self.assertFalse((self.vault / STATE).exists())

    def test_terminal_preview_and_result_limit_large_lists(self):
        names = [f"note-{n}.md" for n in range(12)]
        plan = {"operation": "upgrade", "items": [{"action": "PROPOSE", "path": p} for p in names]}
        summary = {}
        describe_preview(self.vault, plan, lambda label, data: summary.update(data))
        self.assertEqual(summary["actionCounts"]["PROPOSE"], 12)
        self.assertEqual(summary["examples"]["PROPOSE"], names[:3])
        result = {"firstAction": "Open README.md.", "changes": {"created": names},
                  "validation": {"status": "PASS", "findings": names}, "report": "setup-summary.json"}
        output = StringIO()
        with redirect_stdout(output):
            console("Run result", result)
        self.assertIn("+4 in report", output.getvalue())
        self.assertNotIn(names[-1], output.getvalue())
        self.assertTrue(output.getvalue().strip().endswith("Next: Open README.md."))
        self.assertEqual(result["changes"]["created"], names)

    def test_terminal_update_preserves_custom_content_and_records_results(self):
        self.older()
        skill = self.vault / ".agents/skills/custom/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: custom\ndescription: Local skill\n---\n# My skill\n")
        note = self.vault / "work.md"
        note.write_text("[[README]]\n")
        self.assertEqual(self.invoke(True, True), "updated")
        self.assertEqual(len(self.prompts), 2)
        self.assertIn("Changes between releases", [label for label, _ in self.output])
        report = self.output[-1][1]
        backup = Path(report["backup"])
        self.assertEqual(skill.read_bytes(), (backup / skill.relative_to(self.vault)).read_bytes())
        self.assertEqual(note.read_bytes(), (backup / "work.md").read_bytes())
        self.assertEqual(json_read(backup / STATE)["starterKitVersion"], "1.3.1")
        self.assertEqual(report["previousDistribution"], "1.3.1")
        self.assertEqual(report["releaseChanges"][0]["version"], RELEASE["communityVersion"])
        self.assertFalse(report["audit"]["blockers"])
        self.assertIn(STATE, report["changes"]["updated"])
        self.assertTrue(Path(report["journal"]).is_file())
        self.assertTrue((self.vault / RUNS / report["runId"] / "setup-summary.json").is_file())

    def test_rehearsal_can_be_declined_and_original_drift_blocks_apply(self):
        self.older()
        before = snapshot(self.vault)
        self.assertEqual(self.invoke(False), "cancelled")
        self.assertEqual(self.invoke(True, False), "rehearsed")
        self.assertEqual(snapshot(self.vault), before)
        def edit(question):
            if "original vault?" in question:
                (self.vault / "late.md").write_text("new local work")
        with self.assertRaisesRegex(Blocked, "changed"):
            self.invoke(True, True, hook=edit)
        self.assertEqual(json_read(self.vault / STATE)["starterKitVersion"], "1.3.1")
        self.assertTrue((self.vault / "late.md").is_file())
