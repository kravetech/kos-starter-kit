"""A vault's initial installation and owner-authored history survive an upgrade."""
import codecs
from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_safety import ROOT, RUNS, STATE, answers_read, apply, digest, encoded, json_read, plan, write
from contracts import RELEASE
from engine import upgrade_changelog
from transaction import rollback


class UpgradeChangelogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = Path(temporary.name) / "vault"
        self.changelog = self.vault / "CHANGELOG.md"
        self.answers = answers_read(json_read(ROOT / "installer/answers.example.json"))
        self.answers["system"]["installation_date"] = "2001-02-03"
        initial, files = plan(self.vault, "new", self.answers, "minimal")
        apply(self.vault, initial, files)

    def previous_install(self, distribution, community, raw):
        state = json_read(self.vault / STATE)
        state.update(starterKitVersion=distribution, installerVersion=distribution)
        if community:
            state["communityVersion"] = community
        else:
            state.pop("communityVersion", None)
        if raw is None:
            self.changelog.unlink()
            state["components"].pop("CHANGELOG.md")
        else:
            self.changelog.write_bytes(raw)
            state["components"]["CHANGELOG.md"].update(
                installedHash=digest(raw), sourceVersion=distribution,
                proposalHash=digest(b"previous release's unapplied proposal"))
        write(self.vault, STATE, encoded(state))

    def upgrade(self):
        planned, payload = plan(self.vault, "upgrade", self.answers)
        item = next(i for i in planned["items"] if i["path"] == "CHANGELOG.md")
        return planned, payload, item

    def test_proposal_preserves_exact_history_and_converges(self):
        old = codecs.BOM_UTF8 + "# Notes\r\n\r\n## [1.2.0] - 2001-02-03\r\n\r\nMy café release".encode()
        self.previous_install("1.3.0", "1.1.0", old)
        planned, files, item = self.upgrade()
        self.assertEqual(item["action"], "PROPOSE")
        self.assertEqual(item["ownership"], "user-owned")
        proposal = files["CHANGELOG.md"]
        self.assertTrue(proposal.startswith(old))
        addition = proposal[len(old):].decode()
        today = date.today().isoformat()
        self.assertIn(f"## KOS Community [{RELEASE['communityVersion']}] - {today}\r\n", addition)
        self.assertIn(f"from KOS Community 1.1.0 using installer {RELEASE['installerVersion']}", addition)
        run = apply(self.vault, planned, files)
        self.assertEqual(self.changelog.read_bytes(), old)
        self.assertEqual((self.vault / RUNS / run / "proposals/CHANGELOG.md").read_bytes(), proposal)
        self.assertEqual(json_read(self.vault / STATE)["components"]["CHANGELOG.md"]["installedHash"], digest(old))
        again, files, item = self.upgrade()
        self.assertEqual(item["action"], "PRESERVE")
        self.assertIsNone(apply(self.vault, again, files))
        self.changelog.write_bytes(proposal)
        accepted, files, item = self.upgrade()
        self.assertEqual(item["action"], "UNCHANGED")
        apply(self.vault, accepted, files)
        self.assertEqual(json_read(self.vault / STATE)["components"]["CHANGELOG.md"]["installedHash"], digest(proposal))
        again, files, _ = self.upgrade()
        self.assertIsNone(apply(self.vault, again, files))

    def test_missing_history_is_offered_without_fabricating_an_installation(self):
        self.previous_install("1.2.0", None, None)
        planned, files, item = self.upgrade()
        self.assertEqual((item["classification"], item["action"]), ("MISSING", "PROPOSE"))
        self.assertNotIn(b"Initial", files["CHANGELOG.md"])
        self.assertNotIn(b"from KOS Community", files["CHANGELOG.md"])
        run = apply(self.vault, planned, files)
        self.assertFalse(self.changelog.exists())
        self.assertNotIn("CHANGELOG.md", json_read(self.vault / STATE)["components"])
        self.assertTrue((self.vault / RUNS / run / "proposals/CHANGELOG.md").exists())
        rollback(self.vault, run, approve=True)
        self.assertFalse(self.changelog.exists())
        self.assertEqual(json_read(self.vault / STATE)["starterKitVersion"], "1.2.0")

    def test_existing_history_patch_only_and_unusual_content(self):
        state = {"communityVersion": RELEASE["communityVersion"], "installerVersion": "1.3.0"}
        def propose(raw):
            self.changelog.write_bytes(raw)
            return upgrade_changelog(self.changelog, digest(raw), state, "1.3.0", {})
        for raw in (b"", b"# My notes\r", codecs.BOM_UTF8):
            with self.subTest(raw=raw):
                _, action, candidate = propose(raw)
                self.assertEqual(action, "PROPOSE")
                self.assertTrue(candidate.startswith(raw))
                self.assertIn(f"from 1.3.0 to {RELEASE['installerVersion']}".encode(), candidate)
                self.assertEqual(propose(candidate)[1:], ("PRESERVE", candidate))
        for raw in (b"\xff\xfe#\0", b"custom\0content"):
            self.assertEqual(propose(raw)[1:], ("PRESERVE", raw))

    def test_powershell_and_python_plan_the_same_proposal(self):
        shells = [path for path in (shutil.which("pwsh"), shutil.which("powershell") if os.name == "nt" else None) if path]
        if not shells:
            self.skipTest("PowerShell unavailable")
        self.previous_install("1.2.0", "1.0.0", b"# User history\r\n")
        _, _, expected = self.upgrade()
        answers = self.vault.parent / "answers.json"
        answers.write_bytes(encoded(self.answers))
        for shell in shells:
            result = subprocess.run([shell, "-NoProfile", "-File", str(ROOT / "install.ps1"),
                                     "-Target", str(self.vault), "-Answers", str(answers),
                                     "-Operation", "upgrade", "-DryRun"], capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            items = json.loads(result.stdout.decode("utf-8-sig"))["items"]
            self.assertEqual(next(i for i in items if i["path"] == "CHANGELOG.md"), expected)
