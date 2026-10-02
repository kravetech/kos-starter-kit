"""Read-only compatibility entrypoint for pre-v1.2 YAML Power-Ups."""
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]


class PowerUpsCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / "test-output" / ("powerups-" + uuid.uuid4().hex)
        self.base.mkdir(parents=True)
        self.vault = self.base / "vault"
        self.legacy = self.vault / "00 - System/Power-Ups"
        self.legacy.mkdir(parents=True)
        (self.legacy / "registry.yaml").write_text('schema_version: "1.0"\npower_ups: []\n', encoding="utf-8")
        self.home = self.base / "legacy-home"
        self.home.mkdir()
        (self.legacy / "settings.yaml").write_text(
            'schema_version: "1.0"\npower_ups:\n  home_environment_variable: KOS_POWERUPS_HOME\n'
            f'  home_directory: "{self.home.as_posix()}"\n', encoding="utf-8")
        candidate = self.home / "kos-example"
        candidate.mkdir()
        (candidate / "manifest.yaml").write_bytes((ROOT / "templates/power-up-template/manifest.yaml").read_bytes())

    def tearDown(self):
        self.assertEqual(self.base.resolve().parent, (ROOT / "test-output").resolve())
        shutil.rmtree(self.base)

    def run_tooling(self, command):
        return subprocess.run([sys.executable, str(ROOT / "scripts/tooling.py"), command,
                               "--root", str(self.vault), "--home", str(self.home)],
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_discovery_and_status_are_read_only(self):
        before = {str(path.relative_to(self.base)): path.read_bytes()
                  for path in self.base.rglob("*") if path.is_file()}
        discovered = self.run_tooling("powerups-discover")
        self.assertEqual(0, discovered.returncode, discovered.stdout + discovered.stderr)
        self.assertIn("kos-example", discovered.stdout)
        status = self.run_tooling("powerups-status")
        self.assertEqual(0, status.returncode, status.stdout + status.stderr)
        self.assertIn("No Power-Ups registered.", status.stdout)
        after = {str(path.relative_to(self.base)): path.read_bytes()
                 for path in self.base.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_legacy_register_wrapper_is_blocked(self):
        shell = shutil.which("bash")
        if not shell and os.name == "nt":
            for install_root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
                if not install_root:
                    continue
                for relative in ("Git/bin/bash.exe", "Git/usr/bin/bash.exe"):
                    candidate = Path(install_root) / relative
                    if candidate.is_file():
                        shell = str(candidate)
                        break
                if shell:
                    break
        if not shell:
            self.skipTest("Bash unavailable")
        env = dict(os.environ, PYTHON=Path(sys.executable).as_posix())
        for command, expected in (("discover", "kos-example"), ("status", "No Power-Ups registered.")):
            with self.subTest(command=command):
                read_only = subprocess.run([shell, str(ROOT / "scripts/powerups.sh"), command,
                                            str(self.vault), "--home", str(self.home)],
                                           capture_output=True, text=True, encoding="utf-8", timeout=30, env=env)
                self.assertEqual(0, read_only.returncode, read_only.stdout + read_only.stderr)
                self.assertIn(expected, read_only.stdout)
        result = subprocess.run([shell, str(ROOT / "scripts/powerups.sh"), "register", str(self.vault),
                                 "--id", "kos-example"], capture_output=True, text=True,
                                encoding="utf-8", timeout=30, env=env)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("read-only", result.stderr)
        self.assertFalse((self.legacy / "manifests/kos-example.yaml").exists())


if __name__ == "__main__":
    unittest.main()
