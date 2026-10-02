"""Native PowerShell/Python golden-plan equivalence on shared fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid

from test_safety import ROOT, write
sys.path.insert(0, str(ROOT / "installer"))
from engine import answers_read, plan
from safety import encoded, json_read


class ParityTests(unittest.TestCase):
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
                for shell in shells:
                    result = subprocess.run([shell, "-NoProfile", "-File", str(ROOT / "install.ps1"), "-Answers", str(answer_path), "-Target", str(target), "-Operation", operation, "-Mode", "standard", "-DryRun"], capture_output=True, timeout=90)
                    self.assertEqual(result.returncode, 2 if name == "obsidian-collision" else 0, result.stderr.decode(errors="replace"))
                    actual = json.loads(result.stdout.decode("utf-8-sig"))
                    # Ordering is presentation; classifications, hashes and actions are contract.
                    actual["items"].sort(key=lambda x: (x["path"], x.get("kind", "file")))
                    if operation == "enhance":
                        self.assertEqual(expected["linkAudit"], actual["linkAudit"], shell + " link audit")
                    self.assertEqual(expected, actual, shell + " " + name)
        finally:
            self.assertEqual(base.resolve().parent, (ROOT / "test-output").resolve())
            shutil.rmtree(base)


if __name__ == "__main__":
    unittest.main()
