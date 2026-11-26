"""Existing KOS vaults use their live history and verified questionnaire inputs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_safety import ROOT, RUNS, STATE, answers_read, apply, digest, encoded, json_read, plan, write
from contracts import RELEASE
from engine import contents


class EnhanceAnswersTests(unittest.TestCase):
    def test_repeat_enhance_uses_only_explicit_answers(self):
        commands = [("python", [sys.executable, "-B", str(ROOT / "installer/install.py"),
                                "--operation", "enhance", "--approve", "--target"], "--answers")]
        for name in ("pwsh", "powershell"):
            shell = shutil.which(name)
            if shell:
                commands.append((name, [shell, "-NoProfile", "-File", str(ROOT / "install.ps1"),
                                        "-Operation", "enhance", "-Approve", "-Target"], "-Answers"))

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = base / "original.json"
            original.write_bytes(encoded({"user": {"preferred_name": "Avery Example"},
                                          "system": {"name": "Harbor Notes"},
                                          "privacy": {"restricted_folders": ["Private Notes"]}}))
            partial = base / "partial.json"
            partial.write_bytes(encoded({"system": {"name": "New Harbor"},
                                         "privacy": {"restricted_folders": ["New Private Notes"]}}))
            for name, command, answers_flag in commands:
                with self.subTest(engine=name):
                    vault = base / name
                    write(vault, ".obsidian/app.json", "{}")

                    def enhance(answers_file=None):
                        args = [*command, str(vault)]
                        if answers_file:
                            args.extend([answers_flag, str(answers_file)])
                        result = subprocess.run(args, capture_output=True, timeout=120)
                        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-600:])

                    enhance(original)
                    readme = vault / "README.md"
                    live = readme.read_bytes() + b"\nOwner's local workflow.\n"
                    self.assertIn(b"# Harbor Notes", live)
                    self.assertIn(b"Owner: Avery Example", live)
                    self.assertIn(b"Timezone: UTC", live)  # First enhancement fills omitted fields.
                    readme.write_bytes(live)
                    receipt = (vault / STATE).read_bytes()
                    self.assertEqual(json.loads(receipt)["privacy"]["restricted_folders"], ["Private Notes"])
                    runs = set((vault / RUNS).iterdir())

                    enhance()
                    self.assertEqual(set((vault / RUNS).iterdir()), runs)
                    self.assertEqual((vault / STATE).read_bytes(), receipt)
                    self.assertEqual(readme.read_bytes(), live)

                    enhance(partial)
                    new_runs = set((vault / RUNS).iterdir()) - runs
                    self.assertEqual(len(new_runs), 1)
                    proposals = new_runs.pop() / "proposals"
                    self.assertEqual([p.relative_to(proposals).as_posix() for p in proposals.rglob("*") if p.is_file()],
                                     ["00 - System/Home.md"])
                    self.assertIn(b"# New Harbor Home", (proposals / "00 - System/Home.md").read_bytes())
                    self.assertEqual(json_read(vault / STATE)["privacy"]["restricted_folders"],
                                     ["Private Notes", "New Private Notes"])
                    self.assertEqual(readme.read_bytes(), live)


class UpgradeAnswersTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.vault = Path(temp.name) / "vault"
        self.answers = answers_read({"user": {"preferred_name": "Avery Example"},
                                    "system": {"name": "Harbor Notes", "installation_date": "2004-02-03"},
                                    "privacy": {"restricted_folders": ["Private Notes"]}})
        planned, payload = plan(self.vault, "new", self.answers, "minimal")
        apply(self.vault, planned, payload)
        self.original = {
            "README.md": ("# Harbor Notes\n\nOwner: Avery Example  \nInstalled: 2004-02-03\n\n"
                          "## KOS Distribution\n\n- Edition: KOS Community `1.1.0`\n"
                          "- Bootstrap distribution: KOS Starter Kit `1.3.0`\n"
                          "- Architecture: KOS Core contract `1.0.0`\n\nA custom workflow.\n").encode(),
            "ARCHITECTURE.md": ("---\ntitle: Harbor Notes\nversion: 1.3.0\ncommunity_version: 1.1.0\n"
                                "kos_contract_version: 1.0.0\nowner: Avery Example\ncreated: 2004-02-03\n---\n\n"
                                "## Release\n\nKOS Community edition `1.1.0`, bootstrapped by KOS Starter Kit `1.3.0`\n"
                                "and conforming to KOS Core contract `1.0.0`.\n\nA custom workflow.\n").encode(),
            "CHANGELOG.md": b"# History\n\n## [1.3.0] - 2004-02-03\n\nA custom workflow.\n",
        }
        state = json_read(self.vault / STATE)
        state.pop("installationDate")  # Released 1.3.0 did not store the original date.
        state.update(starterKitVersion="1.3.0", installerVersion="1.3.0", communityVersion="1.1.0")
        for rel, raw in self.original.items():
            write(self.vault, rel, raw)
            state["components"][rel].update(sourceVersion="1.3.0", installedHash=digest(raw))
        # An unidentified prior package, a missing personal file and an edited live note.
        state["components"]["ARCHITECTURE.md"].pop("renderFingerprint")
        (self.vault / "DESIGN.md").unlink()
        state["components"].pop("DESIGN.md")
        write(self.vault, "memory.md", b"# Locally edited owner memory\n")
        write(self.vault, STATE, encoded(state))
        self.state = state

    def test_no_answers_preserves_owner_data_and_only_offers_three_documents(self):
        # Exercise both CLI entrypoints. Each must convey that no answer file was supplied.
        commands = [[sys.executable, "-B", str(ROOT / "installer/install.py"), "--dry-run", "--target",
                     str(self.vault), "--operation", "upgrade"]]
        shells = [shutil.which("pwsh"), shutil.which("powershell") if os.name == "nt" else None]
        commands.extend([shell, "-NoProfile", "-File", str(ROOT / "install.ps1"), "-DryRun", "-Target",
                         str(self.vault), "-Operation", "upgrade"] for shell in shells if shell)
        upgrade, payload = plan(self.vault, "upgrade", answers_read({}), supplied_answers={})
        expected = {i["path"]: i for i in upgrade["items"]}
        self.assertEqual({k for k, i in expected.items() if i["action"] == "PROPOSE"}, set(self.original))
        self.assertEqual(expected["DESIGN.md"]["action"], "SKIP")
        self.assertEqual(expected["memory.md"]["action"], "PRESERVE")
        self.assertIn("original questionnaire", expected["memory.md"]["reason"])
        for command in commands:
            result = subprocess.run(command, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            actual = {i["path"]: i for i in json.loads(result.stdout.decode("utf-8-sig"))["items"]}
            self.assertEqual(actual, expected)
        run = apply(self.vault, upgrade, payload)
        self.assertFalse((self.vault / "DESIGN.md").exists())
        self.assertEqual((self.vault / "memory.md").read_bytes(), b"# Locally edited owner memory\n")
        self.assertEqual(json_read(self.vault / STATE)["privacy"]["restricted_folders"], ["Private Notes"])
        for rel, old in self.original.items():
            self.assertEqual((self.vault / rel).read_bytes(), old)
            proposal = (self.vault / RUNS / run / "proposals" / rel).read_bytes()
            if rel != "CHANGELOG.md":
                for original in (b"Harbor Notes", b"Avery Example", b"2004-02-03", b"A custom workflow."):
                    self.assertIn(original, proposal)
                for new in ("communityVersion", "installerVersion"):
                    self.assertIn(RELEASE[new].encode(), proposal)
        again, files = plan(self.vault, "upgrade", answers_read({}), supplied_answers={})
        self.assertIsNone(apply(self.vault, again, files))
        # Adopting known bytes must not certify default questionnaire values.
        for rel in ("README.md", "ARCHITECTURE.md"):
            write(self.vault, rel, payload[rel])
        accepted, files = plan(self.vault, "repair", answers_read({}), supplied_answers={})
        apply(self.vault, accepted, files)
        final = json_read(self.vault / STATE)["components"]
        for rel in ("README.md", "ARCHITECTURE.md"):
            self.assertEqual(final[rel]["installedHash"], digest(payload[rel]))
            self.assertEqual(final[rel].get("renderFingerprint"), self.state["components"][rel].get("renderFingerprint"))

    def test_partial_answers_authorize_only_the_templates_they_cover(self):
        partial = {"user": {"preferred_name": "Avery Example"}, "system": {"name": "Harbor Notes"}}
        planned, files = plan(self.vault, "repair", answers_read(partial),
                              decisions={"memory.md": "propose"}, supplied_answers=partial)
        items = {item["path"]: item for item in planned["items"]}
        self.assertEqual(items["DESIGN.md"]["action"], "SKIP")  # installation_date was absent
        self.assertEqual(items["memory.md"]["action"], "PRESERVE")
        self.assertIn(b"2004-02-03", files["README.md"])
        partial["system"]["installation_date"] = "2004-02-03"
        planned, files = plan(self.vault, "repair", answers_read(partial), supplied_answers=partial)
        item = next(i for i in planned["items"] if i["path"] == "DESIGN.md")
        self.assertEqual(item["action"], "CREATE")
        for value in (b"Avery Example", b"Harbor Notes", b"2004-02-03"):
            self.assertIn(value, files["DESIGN.md"])

    def test_matching_default_fingerprint_does_not_authorize_regenerating_live_edits(self):
        # Simulate an original installation that used the kit defaults, followed by owner edits.
        defaults = answers_read({})
        assets = contents(defaults, "minimal")
        for rel in ("README.md", "ARCHITECTURE.md", "memory.md"):
            raw, asset = assets[rel]
            self.state["components"][rel].update(installedHash=digest(raw), renderFingerprint=asset["renderFingerprint"])
        write(self.vault, STATE, encoded(self.state))
        planned, files = plan(self.vault, "upgrade", defaults, supplied_answers={})
        items = {item["path"]: item for item in planned["items"]}
        self.assertEqual(items["memory.md"]["action"], "PRESERVE")
        self.assertEqual(files["memory.md"], b"# Locally edited owner memory\n")
        for rel in ("README.md", "ARCHITECTURE.md"):
            self.assertEqual(items[rel]["action"], "PROPOSE")
            self.assertIn(b"A custom workflow.", files[rel])
            self.assertIn(b"Avery Example", files[rel])
