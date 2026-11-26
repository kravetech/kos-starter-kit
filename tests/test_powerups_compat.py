"""Read-only compatibility entrypoint for pre-v1.2 YAML Power-Ups."""
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]


def bash_shell():
    # Windows can put its WSL launcher on PATH even when no Linux shell is installed.
    if os.name == "nt":
        for install_root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if install_root:
                for relative in ("Git/bin/bash.exe", "Git/usr/bin/bash.exe"):
                    candidate = Path(install_root) / relative
                    if candidate.is_file():
                        return str(candidate)
    return shutil.which("bash")


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

    def test_legacy_discovery_uses_only_verified_core_contract_versions(self):
        commands = []
        shell = bash_shell()
        if shell:
            commands.append([shell, (ROOT / "scripts/powerups.sh").as_posix(), "discover",
                             self.vault.as_posix(), "--home", self.home.as_posix()])
        for shell in (shutil.which("pwsh"), shutil.which("powershell") if os.name == "nt" else None):
            if shell:
                commands.append([shell, "-NoProfile", "-File", str(ROOT / "scripts/powerups.ps1"),
                                 "discover", "-InstallationRoot", str(self.vault), "-HomeDirectory", str(self.home)])
        if not commands:
            self.skipTest("No supported discovery shell available")
        source = self.home / "kos-example"
        shutil.copytree(ROOT / "templates/power-up-template/installer", source / "installer")
        manifest = source / "manifest.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace("maximum_version: null", "maximum_version: 1.0.0"), encoding="utf-8")
        receipt = self.vault / "00 - System/Installation/kos-installation.json"
        receipt.parent.mkdir()
        header = "---\nversion: 1.3.1\ncommunity_version: 1.1.1\n"
        unknown = "Power-Up compatibility was not checked because the installed KOS Core contract version is unknown."
        too_new = "Installed KOS Core contract 1.2.0 is newer than the Power-Up's maximum 1.0.0."
        cases = (
            ('{"kosContractVersion":"1.0.0"}', header + "kos_contract_version: 1.2.0\n---\n", "PASS", ""),
            (None, header + 'kos_contract_version: "1.0.0" # reviewed\n---\n', "PASS", ""),
            ('{"kosContractVersion":"invalid"}', header + "kos_contract_version: 1.2.0\n---\n", "ERROR", too_new),
            (None, header + "nested:\n  kos_contract_version: 1.0.0\n---\nkos_contract_version: 1.0.0\n", "WARNING", unknown),
            (None, header + "kos_contract_version: 1.0.0\n'kos_contract_version': invalid\n---\n", "WARNING", unknown),
            (None, header + "kos_contract_version: 1.0.0\n", "WARNING", unknown),
        )
        env = dict(os.environ, PYTHON=Path(sys.executable).as_posix(), PYTHONDONTWRITEBYTECODE="1")
        for record, architecture, status, message in cases:
            if record is None:
                receipt.unlink(missing_ok=True)
            else:
                receipt.write_text(record, encoding="utf-8")
            (self.vault / "ARCHITECTURE.md").write_bytes(architecture.replace("\n", "\r\n").encode("utf-8-sig"))
            before = {path: path.read_bytes() for path in self.base.rglob("*") if path.is_file()}
            for command in commands:
                with self.subTest(shell=command[0], architecture=architecture, record=record):
                    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                            errors="replace", timeout=45, env=env)
                    output = result.stdout + result.stderr
                    self.assertEqual(2 if status == "ERROR" else 0, result.returncode, output)
                    self.assertIn("[" + status + "] kos-example", output)
                    if message:
                        self.assertIn(message, output)
            self.assertEqual(before, {path: path.read_bytes() for path in self.base.rglob("*") if path.is_file()})

    def test_bash_discover_and_status(self):
        shell = bash_shell()
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

    def test_legacy_registration_refusal_matches_on_all_shells(self):
        commands = []
        shell = bash_shell()
        if shell:
            commands.append(([shell, (ROOT / "scripts/powerups.sh").as_posix(), "register", self.vault.as_posix()],
                             "install.sh --package-command install"))
        for name in ("pwsh", "powershell"):
            shell = shutil.which(name)
            if shell:
                commands.append(([shell, "-NoProfile", "-File", str(ROOT / "scripts/powerups.ps1"),
                                  "register", "-InstallationRoot", str(self.vault)], "install.ps1 -PackageCommand install"))
        if not commands:
            self.skipTest("No supported shell available")
        for command, replacement in commands:
            with self.subTest(shell=command[0]):
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertEqual("", result.stdout)
                self.assertEqual(f"ERROR: Legacy Power-Up discovery is read-only. Use {replacement} "
                                 "after reviewing an immutable package.", result.stderr.strip())
                self.assertFalse((self.legacy / "manifests/kos-example.yaml").exists())


if __name__ == "__main__":
    unittest.main()
