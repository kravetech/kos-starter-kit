"""Recovery fixtures use ordinary user-owned files and never operate on a live vault."""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT / "installer"))
import setup_backup as recovery
from safety import Blocked


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        output = ROOT / "test-output"
        output.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.vault = self.base / "my vault"
        self.vault.mkdir()
        (self.vault / "notes.md").write_text("one", encoding="utf-8")
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "workspace.json").write_text("{}", encoding="utf-8")
        (self.vault / ".empty").mkdir()

    def test_no_write_proposal_and_independent_verified_copies(self):
        before = recovery.snapshot(self.vault)
        run = recovery.propose_recovery(self.vault)
        self.assertEqual(run.parent.name, "my vault-recovery")
        self.assertFalse(run.parent.exists())
        backup, copy = recovery.create_recovery(self.vault, run, before)
        self.assertEqual(recovery.snapshot(backup), before)
        self.assertEqual(recovery.snapshot(copy), before)
        self.assertNotEqual((copy / "notes.md").stat().st_ino, (backup / "notes.md").stat().st_ino)
        (copy / "notes.md").write_text("two", encoding="utf-8")
        self.assertEqual(recovery.snapshot(backup), before)
        self.assertEqual(recovery.snapshot(self.vault), before)
        self.assertNotEqual(recovery.snapshot(copy), before)
        self.assertNotEqual(recovery.propose_recovery(self.vault), run)
        with self.assertRaisesRegex(Blocked, "OVERLAPS_OR_EXISTS"):
            recovery.create_recovery(self.vault, run, before)
        self.assertEqual(recovery.snapshot(backup), before)

    def test_absent_and_empty_targets_are_distinct(self):
        self.assertEqual(recovery.snapshot(self.base / "absent"), {})
        self.assertEqual(list(recovery.snapshot(self.vault / ".empty")), ["."])

    def test_drift_declines_before_creating_any_destination(self):
        before = recovery.snapshot(self.vault)
        (self.vault / "notes.md").write_text("new", encoding="utf-8")
        run = recovery.propose_recovery(self.vault)
        with self.assertRaisesRegex(Blocked, "SOURCE_CHANGED"):
            recovery.create_recovery(self.vault, run, before)
        self.assertFalse(run.parent.exists())

    def test_full_backup_detects_hidden_drift_and_retains_older_snapshot(self):
        baseline = recovery.snapshot(self.vault)
        first = recovery.propose_recovery(self.vault)
        backup, _ = recovery.create_recovery(self.vault, first, baseline)
        run = recovery.propose_recovery(self.vault)
        copy_tree = recovery._copy_tree

        def during_copy(src, dst, expected):
            copy_tree(src, dst, expected)
            (self.vault / ".obsidian" / "workspace.json").write_text("new", encoding="utf-8")

        with mock.patch.object(recovery, "_copy_tree", side_effect=during_copy):
            with self.assertRaisesRegex(Blocked, "SOURCE_CHANGED"):
                recovery.create_recovery(self.vault, run, baseline)
        self.assertEqual(recovery.snapshot(backup), baseline)
        self.assertFalse((run / "backup").exists())
        self.assertFalse((run / "test-copy").exists())

    def test_detects_corrupt_copy(self):
        before = recovery.snapshot(self.vault)
        run = recovery.propose_recovery(self.vault)
        with mock.patch.object(shutil, "copyfileobj", side_effect=lambda src, dst, length: dst.write(b"x")):
            with self.assertRaisesRegex(Blocked, "COPY_VERIFICATION_FAILED"):
                recovery.create_recovery(self.vault, run, before)
        self.assertFalse((run / "backup").exists())
        self.assertTrue((run / "backup.incomplete").exists())
        self.assertEqual(recovery.snapshot(self.vault), before)

    def test_overlap_and_synced_locations(self):
        with self.assertRaisesRegex(Blocked, "OVERLAPS"):
            recovery.propose_recovery(self.vault, self.vault / "backups")
        synced = self.base / "OneDrive - Example"
        with self.assertRaisesRegex(Blocked, "PRIVATE_LOCAL_LOCATION"):
            recovery.propose_recovery(self.vault, synced)
        other = self.base / "custom sync path"
        with mock.patch.object(os, "environ", dict(os.environ, OneDrive=str(other))):
            with self.assertRaisesRegex(Blocked, "PRIVATE_LOCAL_LOCATION"):
                recovery.propose_recovery(self.vault, other)
    def test_symlinked_parent(self):
        linked = self.base / "linked"
        try:
            os.symlink(self.base, linked, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"OS denied symlink fixture: {exc}")
        with self.assertRaisesRegex(Blocked, "PATH_LINK"):
            recovery.propose_recovery(self.vault, linked)

    def test_fallback_for_vault_under_sync(self):
        private_home = self.base / "private home"
        private_home.mkdir()
        with mock.patch.object(os, "environ", dict(os.environ, OneDrive=str(self.base / "synced"))):
            synced = self.base / "synced" / "my vault"
            synced.mkdir(parents=True)
            with mock.patch.object(Path, "home", return_value=private_home):
                run = recovery.propose_recovery(synced)
        self.assertTrue(run.is_relative_to(private_home))
        self.assertFalse(run.exists())

    def test_no_space_does_not_write(self):
        before = recovery.snapshot(self.vault)
        run = recovery.propose_recovery(self.vault)
        with mock.patch.object(shutil, "disk_usage", return_value=mock.Mock(free=0)):
            with self.assertRaisesRegex(Blocked, "INSUFFICIENT_SPACE"):
                recovery.create_recovery(self.vault, run, before)
        self.assertFalse(run.parent.exists())

    def test_symlink_targets_preserved_without_traversal(self):
        outside = self.base / "external"
        outside.mkdir()
        (outside / "out.md").write_text("elsewhere")
        try:
            (self.vault / "linked").symlink_to(outside, target_is_directory=True)
            (self.vault / "missing").symlink_to("absent-file")
        except OSError as exc:
            self.skipTest(f"OS denied symlink fixture: {exc}")
        baseline = recovery.snapshot(self.vault)
        self.assertNotIn("linked/out.md", baseline)
        backup, copy = recovery.create_recovery(self.vault, recovery.propose_recovery(self.vault), baseline)
        for tree in (backup, copy):
            self.assertTrue((tree / "missing").is_symlink())
            self.assertEqual(os.readlink(tree / "linked"), os.readlink(self.vault / "linked"))
            self.assertEqual(os.readlink(tree / "missing"), os.readlink(self.vault / "missing"))

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_windows_junction_targets_preserved_without_traversal(self):
        outside = self.base / "external"
        outside.mkdir()
        (outside / "out.md").write_text("elsewhere")
        # Constant fixture names only. mklink /J needs no symbolic-link privilege.
        fixture = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe"),
                                  "/d", "/c", "mklink", "/J", "linked", r"..\external"],
                                 cwd=self.vault, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if fixture.returncode:
            message = fixture.stderr.decode(errors="replace")
            if "denied" in message.lower() or "privilege" in message.lower():
                self.skipTest("Windows denied creation of the disposable junction fixture")
            self.fail(message)
        baseline = recovery.snapshot(self.vault)
        self.assertEqual(baseline["linked"].kind, "junction")
        self.assertNotIn("linked/out.md", baseline)
        backup, copy = recovery.create_recovery(self.vault, recovery.propose_recovery(self.vault), baseline)
        for tree in (backup, copy):
            self.assertEqual(os.readlink(tree / "linked"), os.readlink(self.vault / "linked"))

    @unittest.skipUnless(os.name == "nt", "Windows DACL")
    def test_run_directory_blocks_inherited_access_before_copy(self):
        import ctypes
        from ctypes import wintypes

        path = self.base / "new recovery"
        recovery._make_private_run(path)
        security = ctypes.WinDLL("advapi32", use_last_error=True)
        required = wintypes.DWORD()
        security.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(required))
        descriptor = ctypes.create_string_buffer(required.value)
        self.assertTrue(security.GetFileSecurityW(str(path), 4, descriptor, len(descriptor), ctypes.byref(required)))
        text = wintypes.LPWSTR()
        self.assertTrue(security.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 4, ctypes.byref(text), None))
        try:
            self.assertTrue(text.value.startswith("D:P"), text.value)
            self.assertEqual(set(text.value[text.value.index("("):].strip("()").split(")(")),
                             {"A;OICI;FA;;;SY", "A;OICI;FA;;;BA", "A;OICI;FA;;;OW"})
        finally:
            ctypes.windll.kernel32.LocalFree(ctypes.cast(text, ctypes.c_void_p))

    @unittest.skipUnless(os.name == "posix", "POSIX special modes")
    def test_executable_modes_preserved_and_special_files_block(self):
        (self.vault / "notes.md").chmod(0o750)
        baseline = recovery.snapshot(self.vault)
        backup, copy = recovery.create_recovery(self.vault, recovery.propose_recovery(self.vault), baseline)
        self.assertTrue(all(stat.S_IMODE((tree / "notes.md").stat().st_mode) == 0o750 for tree in (backup, copy)))
        os.mkfifo(self.vault / "nonregular")
        with self.assertRaisesRegex(Blocked, "UNSUPPORTED_FILE_TYPE"):
            recovery.snapshot(self.vault)
