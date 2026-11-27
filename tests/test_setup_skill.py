"""Verify the portable skill, its release handoff, and the read-only diagnosis."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_setup_release import Download, package
from test_safety import ROOT, STATE
from contracts import RELEASE
from engine import answers_read, apply, plan
from setup_backup import snapshot
from setup_flow import setup
from setup_release import Release

SKILL = ROOT / "skills/kos-community-fix"
sys.path.insert(0, str(SKILL / "scripts"))
import community_asset as assets
import start


class SetupSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name).resolve()
        self.vault = self.work / "My notes"
        self.attachment = self.work / "attached community.zip"
        self.launcher = package(extra=("setup.py", "# test launcher"))

    def metadata(self, content, version="2.1.0"):
        return (version, hashlib.sha256(content).hexdigest(),
                assets.COMMUNITY_URL + f"/releases/download/v{version}/kos-community-v{version}.zip")

    def invoke(self, args):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = start.main(args)
        return code, output.getvalue()

    def test_latest_asset_handoff_uses_the_pinned_bytes_and_inherits_the_terminal(self):
        options = ["--target", str(self.vault), "--adapter", "gemini", "--check"]
        def launch(argv, **kwargs):
            self.assertEqual(argv[:3], [sys.executable, "-I", "-B"])
            self.assertEqual(Path(argv[3]).read_text(), "# test launcher")
            self.assertEqual(Path(argv[4]).read_bytes(), self.launcher)
            self.assertEqual(argv[5:], options)
            for key in ("stdin", "input", "stdout", "stderr", "capture_output", "cwd"):
                self.assertNotIn(key, kwargs)
            return subprocess.CompletedProcess(argv, 2)
        with patch.object(assets, "_metadata", return_value=self.metadata(self.launcher)) as latest, \
                patch.object(assets, "urlopen", return_value=Download(self.launcher)) as download, \
                patch.object(start.subprocess, "run", side_effect=launch) as child:
            self.assertEqual(self.invoke([assets.COMMUNITY_URL, *options])[0], 2)
        latest.assert_called_once_with()
        download.assert_called_once()
        child.assert_called_once()
        self.assertFalse(self.vault.exists())

    def test_legacy_attachment_uses_new_launcher_and_keeps_the_selected_distribution(self):
        old = package(version="1.2.0", community="1.0.0")
        self.attachment.write_bytes(old)
        def download(*args, **kwargs):
            self.attachment.write_bytes(b"attachment replaced after verification")
            return Download(self.launcher)
        def launch(argv):
            self.assertEqual(Path(argv[4]).read_bytes(), old)
            self.assertNotEqual(Path(argv[4]), self.attachment)
            self.assertEqual(Path(argv[3]).read_text(), "# test launcher")
            return subprocess.CompletedProcess(argv, 0)
        with patch.dict(assets._KNOWN, {"1.2.0": hashlib.sha256(old).hexdigest()}), \
                patch.object(assets, "_metadata", return_value=self.metadata(self.launcher)) as latest, \
                patch.object(assets, "urlopen", side_effect=download), \
                patch.object(start.subprocess, "run", side_effect=launch) as child:
            self.assertEqual(self.invoke([str(self.attachment)])[0], 0)
        latest.assert_called_once_with()
        child.assert_called_once()

    def test_missing_published_launcher_and_digest_mismatch_preserve_target(self):
        old = package(version="1.2.0", community="1.0.0")
        self.vault.mkdir()
        (self.vault / "work.md").write_bytes(b"Keep this file")
        baseline = snapshot(self.vault)
        for checked, received in ((old, old), (self.launcher, old)):
            with self.subTest(authentic=checked == received), \
                    patch.object(assets, "_metadata", return_value=self.metadata(checked, "1.2.0")), \
                    patch.object(assets, "urlopen", return_value=Download(received)) as download, \
                    patch.object(start.subprocess, "run") as child:
                self.assertEqual(self.invoke(["--target", str(self.vault)])[0], 2)
                child.assert_not_called()
                download.assert_called_once()
                self.assertEqual(snapshot(self.vault), baseline)

    def test_read_only_check_distinguishes_healthy_and_unresolved_links(self):
        release = Release(ROOT, RELEASE["starterKitVersion"], RELEASE["communityVersion"], "")
        apply(self.vault, *plan(self.vault, "new", answers_read({})))
        actual = []
        def check():
            before = snapshot(self.vault)
            result = setup(release, self.vault, check_only=True,
                           ask=lambda *_: self.fail("Read-only check asked for approval"),
                           emit=lambda label, data: actual.append((label, data)))
            self.assertEqual(snapshot(self.vault), before)
            self.assertEqual(actual[-1][0], "Vault check")
            return result, actual[-1][1]
        result, health = check()
        self.assertEqual((result, health["validation"]["status"]), ("checked", "PASS"))
        (self.vault / "Work.md").write_text("[[Unavailable destination]]\n", encoding="utf-8")
        receipt = self.vault / STATE
        old = json.loads(receipt.read_bytes())
        for field in ("communityVersion", "installerVersion", "starterKitVersion"):
            old[field] = "1.3.1"
        receipt.write_text(json.dumps(old), encoding="utf-8")
        result, health = check()
        self.assertEqual(result, "review needed")
        self.assertTrue(any(issue["source"].startswith("Work.md:") for issue in health["unresolvedLinks"]))

    def test_customer_archive_contains_one_public_prompt_and_a_complete_skill(self):
        files = set(json.loads((ROOT / "installer/archive-files.json").read_bytes())["files"])
        entry = "docs/prompts/setup.md"
        self.assertIn(entry, files)
        skill_files = {p.relative_to(ROOT).as_posix() for p in SKILL.rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts}
        self.assertTrue(skill_files <= files, sorted(skill_files - files))
        self.assertTrue({"skills/kos-community-fix/SKILL.md", "skills/kos-community-fix/scripts/start.py",
                         "skills/kos-community-fix/scripts/community_asset.py"} <= skill_files)
        text = (ROOT / entry).read_text(encoding="utf-8")
        blocks = re.findall(r"^```text\s*\n(.*?)^```\s*$", text, flags=re.M | re.S)
        self.assertEqual(len(blocks), 1)
        self.assertIn(assets.COMMUNITY_URL, blocks[0])
        self.assertNotIn(".zip", blocks[0].lower())
        self.assertIn(entry, (ROOT / "README.md").read_text(encoding="utf-8"))
        for alias in ("install", "update"):
            bridge = (ROOT / "docs/prompts" / (alias + ".md")).read_text(encoding="utf-8")
            self.assertIn("setup.md", bridge)
            self.assertNotIn("```text", bridge)


if __name__ == "__main__":
    unittest.main()
