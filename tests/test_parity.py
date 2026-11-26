"""Native PowerShell/Python golden-plan equivalence on shared fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import uuid

from test_safety import ROOT, write
sys.path.insert(0, str(ROOT / "installer"))
from contracts import RELEASE
from engine import answers_read, apply, plan
from packages import plan_package
from safety import STATE, encoded, json_read
from transaction import markdown


class ParityTests(unittest.TestCase):
    def test_operation_reports_identify_the_product_separately_from_the_installer(self):
        base = ROOT / "test-output"
        base.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=base) as folder:
            vault = Path(folder) / "vault"
            answers = answers_read(json_read(ROOT / "installer/answers.example.json"))
            install, payload = plan(vault, "new", answers)
            apply(vault, install, payload)
            state = json_read(vault / STATE)
            # This lower engine version deliberately differs from every supported distribution.
            state.update(communityVersion="1.0.0", installerVersion="1.2.7", starterKitVersion="1.3.0")
            write(vault, STATE, encoded(state))

            upgrade, _ = plan(vault, "upgrade", answers)
            self.assertEqual(upgrade["previousCommunityVersion"], state["communityVersion"])
            self.assertEqual(upgrade["communityVersion"], RELEASE["communityVersion"])
            self.assertEqual(upgrade["installerVersion"], RELEASE["installerVersion"])
            report = markdown(upgrade)
            self.assertIn("Previous KOS Community: 1.0.0", report)
            self.assertIn("Previous distribution version: 1.3.0", report)
            listed, _ = plan_package(vault, "list")
            self.assertIn("KOS Community: 1.0.0", markdown(listed))
            self.assertIn("Installer version: 1.2.7", markdown(listed))

            router = vault / "AGENTS.md"
            router.write_bytes(router.read_bytes() + b"\nLocal instructions for the synthetic project.\n")
            commands = [[sys.executable, str(ROOT / "installer/install.py"), "--target", str(vault),
                         "--operation", "validate", "--report"]]
            for shell in ("pwsh", "powershell"):
                if shutil.which(shell):
                    commands.append([shell, "-NoProfile", "-File", str(ROOT / "install.ps1"),
                                     "-Target", str(vault), "-Operation", "validate", "-Report"])
            for index, command in enumerate(commands):
                with self.subTest(engine=command[0]):
                    path = Path(folder) / f"validation-{index}.md"
                    result = subprocess.run([*command, str(path)], capture_output=True, timeout=90)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                    validation = json.loads(result.stdout.decode("utf-8-sig"))
                    self.assertEqual(validation["product"], "KOS Community")
                    self.assertEqual(validation["communityVersion"], "1.0.0")
                    self.assertEqual(validation["installerVersion"], "1.2.7")
                    report = path.read_text(encoding="utf-8-sig")
                    self.assertIn("Status: PASS", report)
                    self.assertIn("KOS Community: 1.0.0", report)
                    self.assertIn("Installer version: 1.2.7", report)
                    self.assertIn("warning ASSET_MODIFIED: AGENTS.md", report)
                    self.assertNotIn("Local instructions for the synthetic project", report)
                    self.assertNotIn("Starter Kit", report)

    def test_native_golden_plans(self):
        shells = [p for p in (shutil.which("pwsh"), shutil.which("powershell") if os.name == "nt" else None) if p]
        if not shells:
            self.skipTest("PowerShell unavailable; covered by Windows CI")
        base = ROOT / "test-output" / ("parity-" + uuid.uuid4().hex)
        base.mkdir(parents=True)
        answers = answers_read(json_read(ROOT / "installer/answers.example.json"))
        answers["installation"]["providers"] = ["codex", "claude", "gemini"]
        answer_path = base / "answers.json"
        write(base, "answers.json", encoded(answers))
        fixtures = [("empty", "new"), ("obsidian", "enhance"),
                    ("obsidian-collision", "enhance"), ("legacy-10", "upgrade"), ("legacy-11", "upgrade")]
        try:
            for name, operation in fixtures:
                target = base / name
                if operation == "enhance":
                    write(target, ".obsidian/app.json", "{}")
                    if name == "obsidian-collision":
                        write(target, "Notes/AGENTS.md", "# Existing note\n")
                        write(target, "Notes/Existing.md", "[[AGENTS]]\n")
                    else:
                        write(target, "AGENTS.md", "Customized router")
                        write(target, "Notes/Existing.md", "[[Other]] ![[diagram.png]] [relative](Other.md)\n")
                        write(target, "Notes/Other.md", "# Other\n")
                        write(target, "Media/diagram.png", b"synthetic bytes")
                elif operation == "upgrade":
                    write(target, "00 - System/Installation/installer-state.json", encoded({"installer_version": "1.0.0" if name.endswith("10") else "1.1.0"}))
                    write(target, "GEMINI.md", "Existing customized adapter")
                expected, _ = plan(target, operation, answers, "standard")
                for index, shell in enumerate(shells):
                    report_file = base / f"{name}-{index}.md"
                    result = subprocess.run([shell, "-NoProfile", "-File", str(ROOT / "install.ps1"), "-Answers", str(answer_path), "-Target", str(target), "-Operation", operation, "-Mode", "standard", "-DryRun", "-Report", str(report_file)], capture_output=True, timeout=90)
                    self.assertEqual(result.returncode, 2 if name == "obsidian-collision" else 0, result.stderr.decode(errors="replace"))
                    actual = json.loads(result.stdout.decode("utf-8-sig"))
                    # Ordering is presentation; classifications, hashes and actions are contract.
                    actual["items"].sort(key=lambda x: (x["path"], x.get("kind", "file")))
                    if operation == "enhance":
                        self.assertEqual(expected["linkAudit"], actual["linkAudit"], shell + " link audit")
                    if name.startswith("legacy-"):
                        for report in (markdown(expected), report_file.read_text(encoding="utf-8-sig")):
                            self.assertIn("Previous legacy installer version: " + expected["previousVersion"], report)
                            self.assertIn("Previous KOS Community: not recorded", report)
                            self.assertNotIn("Previous distribution version:", report)
                    self.assertEqual(expected, actual, shell + " " + name)
        finally:
            self.assertEqual(base.resolve().parent, (ROOT / "test-output").resolve())
            shutil.rmtree(base)


if __name__ == "__main__":
    unittest.main()
