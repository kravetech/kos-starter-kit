"""Customer-wrapper regression tests for recovery, report exports and guided setup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_safety import ROOT
from cli import OperationExports
from safety import STATE, RUNS, encoded
from transaction import Transaction


class InstallerCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        PYTHONDONTWRITEBYTECODE="1")
        bash = shutil.which("bash")
        if os.name == "nt":
            git = shutil.which("git")
            git_bash = Path(git).parents[1] / "bin/bash.exe" if git else None
            if git_bash and git_bash.exists():
                bash = str(git_bash)
            self.shell_script("python3", 'exec "' + Path(sys.executable).as_posix() + '" "$@"')
        self.hosts = {}
        if bash:
            self.hosts["bash"] = [bash]
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell:
            self.hosts["powershell"] = [powershell, "-NoProfile", "-NonInteractive", "-File"]
        self.assertTrue(self.hosts)

    def shell_script(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\n" + body + "\n", encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def test_second_export_reservation_failure_releases_first_file(self):
        plan = self.base / "plan.json"
        report = self.base / "report.md"
        vault = self.base / "vault"
        original_open = Path.open

        def open_file(path, *args, **kwargs):
            if path == report:
                raise PermissionError("unwritable report destination")
            return original_open(path, *args, **kwargs)

        with OperationExports() as outputs, patch.object(Path, "open", open_file):
            outputs.configure(vault, plan, report)
            with self.assertRaises(PermissionError):
                outputs.reserve()
        self.assertFalse(plan.exists())
        self.assertFalse(report.exists())
        self.assertFalse(vault.exists())

    def command(self, host, directory, script, *flags, code=0):
        shell = host == "bash"
        wrapper = directory / (script + (".sh" if shell else ".ps1"))
        argv = [*self.hosts[host], wrapper.as_posix()]
        for flag in flags:
            if isinstance(flag, Path):
                argv.append(flag.as_posix())
            elif flag.startswith("--") and not shell:
                argv.append("-" + "".join(word.capitalize() for word in flag[2:].split("-")))
            else:
                argv.append(flag)
        run = subprocess.run(argv, cwd=directory, env=self.env, input=b"", capture_output=True, timeout=120)
        if code is None:
            self.assertNotEqual(run.returncode, 0)
        else:
            self.assertEqual(run.returncode, code, run.stderr.decode(errors="replace"))
        return run

    def test_rollback_run_lookup_and_retry_exports(self):
        for host in self.hosts:
            with self.subTest(host=host):
                vault = self.base / host
                with Transaction(vault, {"operation": "repair", "targetType": "managed-kos", "items": []}) as tx:
                    tx.write("foundation.md", b"installed", None)
                run_id = "0" * 32
                run_dir = vault / RUNS / run_id
                plan = self.base / (host + "-retry.json")
                report = self.base / (host + "-retry.md")
                args = ("--target", vault, "--operation", "rollback")

                def lookup(action, code=2):
                    return self.command(host, ROOT, "install", *args, "--run-id", run_id, action,
                                        "--plan-output", plan, "--report", report, code=code)

                for action in ("--dry-run", "--approve"):
                    missing = lookup(action)
                    record = json.loads(missing.stdout.decode("utf-8-sig"))
                    self.assertEqual(record["items"][0]["rule"], "ROLLBACK_RUN_NOT_FOUND")
                    self.assertIn("existing run ID", record["requiredAction"])
                    self.assertFalse(plan.exists())
                    self.assertFalse(report.exists())
                    self.assertFalse(run_dir.exists())
                    self.assertEqual((vault / "foundation.md").read_bytes(), b"installed")
                self.command(host, ROOT, "install", *args, "--run-id", tx.run, "--dry-run",
                             "--plan-output", plan, "--report", report)
                self.assertEqual(json.loads(plan.read_bytes())["recovery"], "complete")
                self.assertIn("PLANNED", report.read_text(encoding="utf-8-sig"))

                run_dir.mkdir()
                journal = run_dir / "journal.json"
                for name, code in (("MISSING", 2), ("INVALID", 2), ("UNREADABLE", 3)):
                    plan.unlink()
                    report.unlink()
                    if name == "INVALID":
                        journal.write_text("{broken", encoding="utf-8")
                    if name == "UNREADABLE":
                        journal.unlink()
                        journal.mkdir()
                    damaged = lookup("--approve", code)
                    rule = "ROLLBACK_JOURNAL_" + name
                    self.assertEqual(json.loads(damaged.stdout.decode("utf-8-sig"))["items"][0]["rule"], rule)
                    self.assertEqual(json.loads(plan.read_bytes())["items"][0]["rule"], rule)
                    self.assertIn("verified backup", report.read_text(encoding="utf-8-sig"))
                    self.assertEqual((vault / "foundation.md").read_bytes(), b"installed")

    def test_rollback_approval_exports_and_recovery_reports(self):
        for host in self.hosts:
            with self.subTest(host=host):
                vault = self.base / host
                plan = {"operation": "repair", "targetType": "managed-kos", "items": []}
                with Transaction(vault, plan) as tx:
                    tx.write("foundation.md", b"restored by repair", None)
                args = ("--target", vault, "--operation", "rollback", "--run-id", tx.run)
                folder = self.base / (host + "-exports")
                folder.mkdir()
                taken = folder / "previous.md"
                taken.write_bytes(b"owner report")
                unused = folder / "unused.json"
                def invoke(*flags, code=0):
                    return self.command(host, ROOT, "install", *args, *flags, code=code)
                invoke(code=2)
                for first, second in ((unused, taken), (taken, unused), (unused, unused), (unused, vault / "inside.md")):
                    invoke("--approve", "--plan-output", first, "--report", second, code=2)
                    self.assertFalse(unused.exists())
                    self.assertFalse((vault / "inside.md").exists())
                    self.assertEqual(taken.read_bytes(), b"owner report")
                self.assertEqual((vault / "foundation.md").read_bytes(), b"restored by repair")
                self.assertEqual([p.name for p in (vault / RUNS).iterdir()], [tx.run])
                md = folder / "rollback.md"
                invoke("--approve", "--plan-output", unused, "--report", md)
                self.assertEqual(json.loads(unused.read_bytes())["recovery"], "complete")
                self.assertIn("Status: COMPLETE", md.read_text(encoding="utf-8-sig"))
                self.assertFalse((vault / "foundation.md").exists())
                with Transaction(vault, plan) as partial:
                    partial.write("first.md", b"created", None)
                    partial.write("second.md", b"created", None)
                (vault / "first.md").write_bytes(b"later owner edit")
                partial_md = folder / "partial.md"
                flags = ("--target", vault, "--operation", "rollback", "--run-id", partial.run)
                self.command(host, ROOT, "install", *flags, "--dry-run", code=4)
                self.command(host, ROOT, "install", *flags, "--approve", "--report", partial_md, code=4)
                self.assertEqual((vault / "first.md").read_bytes(), b"later owner edit")
                self.assertFalse((vault / "second.md").exists())
                self.assertIn("Status: INCOMPLETE", partial_md.read_text(encoding="utf-8-sig"))

    def test_validate_exports_and_core_version_guard(self):
        for host in self.hosts:
            with self.subTest(host=host):
                vault = self.base / host
                args = ("--target", vault, "--operation")
                md = self.base / (host + ".md")
                self.command(host, ROOT, "install", *args, "new", "--approve", "--report", md)
                self.assertIn("Status: COMPLETE", md.read_text(encoding="utf-8-sig"))
                plan = self.base / (host + "-validation.json")
                md = self.base / (host + "-validation.md")
                self.command(host, ROOT, "install", *args, "validate", "--plan-output", plan, "--report", md)
                self.assertEqual(json.loads(plan.read_bytes())["status"], "PASS")
                self.assertIn("Status: PASS", md.read_text(encoding="utf-8-sig"))
                # A trailing separator must preserve the same export boundary.
                inside = vault / "inside.md"
                self.command(host, ROOT, "install", "--target", vault.as_posix() + "/", "--operation",
                             "validate", "--report", inside, code=2)
                self.assertFalse(inside.exists())
                standalone = ROOT / "scripts"
                self.command(host, standalone, "validate-installation", vault, "--report", inside, code=2)
                self.assertFalse(inside.exists())
                standalone_report = self.base / (host + "-standalone.md")
                self.command(host, standalone, "validate-installation", vault, "--report", standalone_report)
                saved = standalone_report.read_bytes()
                self.assertIn(b"PASS", saved)
                self.command(host, standalone, "validate-installation", vault, "--report", standalone_report, code=2)
                self.assertEqual(saved, standalone_report.read_bytes())
                state = json.loads((vault / STATE).read_bytes())
                state["kosContractVersion"] = "99.0.0"
                (vault / STATE).write_bytes(encoded(state))
                run = self.command(host, ROOT, "install", *args, "upgrade", "--approve", code=2)
                self.assertEqual(json.loads(run.stdout.decode("utf-8-sig"))["items"][0]["rule"], "CONTRACT_DOWNGRADE")

    def test_guided_launcher_rejects_invalid_inputs_before_dispatch(self):
        client_marker = self.base / "invoked.txt"
        self.env["KOS_TEST_CLIENT_MARKER"] = str(client_marker)
        for provider in ("gemini", "claude", "codex"):
            self.shell_script(provider, 'printf "%s\\n" "' + provider + '" "$@" > "$KOS_TEST_CLIENT_MARKER"')
            if os.name == "nt":
                (self.bin / (provider + ".cmd")).write_text(
                    '@echo ' + provider + ' %* > "%KOS_TEST_CLIENT_MARKER%"\n', encoding="ascii")
        kit = self.base / "kit"
        kit.mkdir()
        for name in ("initialize.sh", "initialize.ps1", "KOS-INSTALLER.md"):
            shutil.copyfile(ROOT / name, kit / name)
        answers = kit / "answers.json"
        answers.write_text("{}", encoding="utf-8")
        for host in self.hosts:
            with self.subTest(host=host):
                for flags in (("--agent", "mistyped"), ("--agent", "gemini", "--answers", kit / "missing.json"),
                              ("--agent", "gemini", "--resume")):
                    run = self.command(host, kit, "initialize", *flags, code=None)
                    self.assertFalse(client_marker.exists())
                    if "--resume" in flags:
                        self.assertIn("RESUME_REQUIRES_JOURNAL_REVIEW", run.stderr.decode(errors="replace"))
                self.command(host, kit, "initialize", "--agent", "gemini", "--dry-run", "--answers", answers)
                output = client_marker.read_text(encoding="utf-8-sig")
                self.assertTrue(output.startswith("gemini"))
                self.assertIn("dry-run mode only", output)
                self.assertIn("answers.json", output)
                client_marker.unlink()

