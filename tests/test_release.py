import importlib.util
import io
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).absolute().parents[1]
spec = importlib.util.spec_from_file_location("release", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_privacy_path_scan_ignores_escaped_fixture_text(self):
        spec = importlib.util.spec_from_file_location("tooling", ROOT / "scripts/tooling.py")
        tooling = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tooling)
        fixture = "power_ups:" + chr(92) + "n  home_environment_variable"
        self.assertIsNone(tooling.ABSOLUTE_PATH.search(fixture))
        windows_path = "C:" + chr(92) + "Users" + chr(92) + "Example" + chr(92) + "file.txt"
        self.assertIsNotNone(tooling.ABSOLUTE_PATH.search(windows_path))
        self.assertIsNotNone(tooling.ABSOLUTE_PATH.search("/" + "home/example/file.txt"))

    def test_archive_preserves_unix_execute_permissions_on_every_host(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(release.archive_entry("install.sh"), b"#!/bin/sh\n")
            archive.writestr(release.archive_entry("README.md"), b"Example\n")
        with zipfile.ZipFile(buffer) as archive:
            script, document = archive.getinfo("install.sh"), archive.getinfo("README.md")
            self.assertEqual(3, script.create_system)
            self.assertEqual(0o100755, script.external_attr >> 16)
            self.assertEqual(0o100644, document.external_attr >> 16)

    def test_positive_allowlist(self):
        files = release.checked_files()
        for required in ("NOTICE", "LICENSE", "installer/release.json", "installer/engine.py", "installer/engine.ps1", "installer/packages.py", "installer/packages-v1.ps1"):
            self.assertIn(required, files)
        self.assertFalse(any(p.startswith(("reports/", "output/", ".claude/", "test-output/")) for p in files))

    def test_client_payload_excludes_maintainer_material(self):
        source = release.checked_files()
        payload = release.checked_archive_files(ROOT, source)
        self.assertLess(len(payload), len(source))
        self.assertTrue(set(payload).issubset(source))
        for rel in ("ARCHITECTURE.md", "PUBLICATION.md", "scripts/release.py", "tests/test_release.py", ".github/workflows/ci.yml"):
            self.assertNotIn(rel, payload)
        for rel in ("README.md", "INSTALL.md", "LICENSE", "NOTICE", "installer/install.py"):
            self.assertIn(rel, payload)

    def test_document_links(self):
        failures = []
        included = set(release.checked_files())
        for rel in included:
            if not rel.endswith(".md") or rel.startswith(("templates/", "examples/")):
                continue
            path = ROOT / rel
            text = path.read_text(encoding="utf-8-sig")
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#") or "<" in target:
                    continue
                destination = target.split("#")[0]
                if destination and not (path.parent / destination).exists():
                    failures.append(rel + " -> " + destination)
                elif destination:
                    resolved = (path.parent / destination).resolve().relative_to(ROOT).as_posix()
                    if resolved not in included and not any(f.startswith(resolved + "/") for f in included):
                        failures.append(rel + " -> excluded release asset " + destination)
        self.assertEqual([], failures)

    def test_schema_and_template_versions(self):
        meta = json.loads((ROOT / "installer/release.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["starterKitVersion"], "1.2.0")
        self.assertEqual(meta["edition"], "community")
        self.assertEqual(meta["kosContractVersion"], "1.0.0")
        self.assertEqual(meta["communityVersion"], "1.0.0")
        for rel in ("ARCHITECTURE.md", "CHANGELOG.md"):
            self.assertIn("{{starter_kit_version}}", (ROOT / "templates/root" / rel).read_text(encoding="utf-8"))
        for rel in ("ARCHITECTURE.md", "README.md"):
            self.assertIn("{{community_version}}", (ROOT / "templates/root" / rel).read_text(encoding="utf-8"))

    def test_declared_versions_agree_with_release_metadata(self):
        self.assertEqual([], release.version_findings())

    def test_freeze_preserves_exact_source_and_detects_later_edit(self):
        test_output = ROOT / "test-output"
        test_output.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_output) as directory:
            root = Path(directory)
            (root / "installer").mkdir()
            (root / "installer/release.json").write_text('{"starterKitVersion":"1.2.0"}', encoding="utf-8")
            (root / "NOTICE").write_text("reviewed", encoding="utf-8")
            files = ["NOTICE", "installer/release.json"]
            with mock.patch.object(release, "checked_files", return_value=files):
                candidate = release.freeze_source(root)
                self.assertEqual("reviewed", (candidate / "NOTICE").read_text(encoding="utf-8"))
                self.assertEqual((candidate / "NOTICE").read_bytes(), (root / "NOTICE").read_bytes())
                self.assertEqual(files, release.verify_candidate(candidate, root)[0])
                (candidate / "NOTICE").write_text("changed", encoding="utf-8")
                with self.assertRaisesRegex(release.Blocked, "RELEASE_CANDIDATE_CHANGED"):
                    release.verify_candidate(candidate, root)

    def test_build_rejects_payload_edit_after_staging_without_zip(self):
        test_output = ROOT / "test-output"
        test_output.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_output) as directory:
            root = Path(directory)
            (root / "installer").mkdir()
            (root / "installer/release.json").write_text('{"starterKitVersion":"1.2.0"}', encoding="utf-8")
            (root / "NOTICE").write_text("reviewed", encoding="utf-8")
            files = ["NOTICE", "installer/release.json"]
            output = root / "build/product.zip"
            with mock.patch.object(release, "checked_files", return_value=files):
                candidate = release.freeze_source(root)
                with mock.patch.object(release, "checked_archive_files", return_value=["NOTICE", "installer/release.json"]):
                    with mock.patch.object(release, "run_tests"), mock.patch.object(release, "run_payload_tests"):
                        payload = release.stage_payload(candidate, root)
                    (payload / "NOTICE").write_text("changed", encoding="utf-8")
                    with self.assertRaisesRegex(release.Blocked, "RELEASE_PAYLOAD_CHANGED"):
                        release.build_archive(payload, output, root)
            self.assertFalse(output.exists())

    def test_build_archives_only_staged_and_tested_client_bytes(self):
        test_output = ROOT / "test-output"
        test_output.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_output) as directory:
            root = Path(directory)
            (root / "installer").mkdir()
            (root / "installer/release.json").write_text('{"starterKitVersion":"1.2.0"}', encoding="utf-8")
            (root / "NOTICE").write_text("reviewed", encoding="utf-8")
            files = ["NOTICE", "installer/release.json"]
            output = root / "build/product.zip"
            def test_gate(payload, workspace, fingerprint):
                self.assertTrue((payload / ".release-payload.json").is_file())
                self.assertFalse(output.exists())
            with mock.patch.object(release, "checked_files", return_value=files):
                candidate = release.freeze_source(root)
                with mock.patch.object(release, "checked_archive_files", return_value=["NOTICE", "installer/release.json"]):
                    with mock.patch.object(release, "run_tests"), mock.patch.object(release, "run_payload_tests", side_effect=test_gate) as gate:
                        payload = release.stage_payload(candidate, root)
                    self.assertTrue((payload / ".release-tested.json").is_file())
                    gate.assert_called_once()
                    release.build_archive(payload, output, root)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(["NOTICE", "installer/release.json"], archive.namelist())
                self.assertEqual(b"reviewed", archive.read("NOTICE"))


if __name__ == "__main__":
    unittest.main()
