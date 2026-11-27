import importlib.util
import io
import json
import os
import re
import subprocess
import sys
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
    def test_archived_release_example_stays_verbatim_in_a_custom_readme(self):
        from community_documents import community_document_update
        meta = json.loads((ROOT / "installer/release.json").read_bytes())
        block = ("## KOS Distribution\r\n\r\n- Edition: KOS Community `1.0.0`\r\n"
                 "- Bootstrap distribution: KOS Starter Kit `1.2.0`\r\n"
                 "- Architecture: KOS Core contract `1.0.0`\r\n").encode()
        archived = b"# Archived example\r\n\r\n~~~~md\r\n" + block + b"~~~~\r\n"
        self.assertEqual(community_document_update("README.md", archived, meta), archived)
        updated = community_document_update("README.md", archived + block, meta)
        self.assertTrue(updated.startswith(archived))
        self.assertIn(meta["communityVersion"].encode(), updated[len(archived):])

    def test_enrolled_build_requires_matching_external_privacy_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            (repo / ".git").mkdir(parents=True)
            receipt = base / "receipt.json"
            setting = mock.Mock(returncode=0, stdout=str(receipt).encode())
            with mock.patch.object(release.subprocess, "run", return_value=setting):
                with self.assertRaisesRegex(ValueError, "RECEIPT_REQUIRED"):
                    release.verify_privacy_receipt(repo, "source", "archive", "release.zip")
                record = {"result": "PASS", "source_fingerprint": "source", "zip_sha256": "archive",
                          "review_day_utc": release.datetime.now(release.timezone.utc).date().isoformat()}
                receipt.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, "REVIEW_REQUIRED"):
                    release.verify_privacy_receipt(repo, "source", "archive", "release.zip")
                record["zip_name"] = "release.zip"
                receipt.write_text(json.dumps(record))
                release.verify_privacy_receipt(repo, "source", "archive", "release.zip")
                for source, archive, name in (("changed", "archive", "release.zip"),
                                              ("source", "changed", "release.zip"),
                                              ("source", "archive", "renamed.zip")):
                    with self.assertRaisesRegex(ValueError, "REVIEW_REQUIRED"):
                        release.verify_privacy_receipt(repo, source, archive, name)
                record["review_day_utc"] = "2000-01-01"
                receipt.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, "REVIEW_REQUIRED"):
                    release.verify_privacy_receipt(repo, "source", "archive", "release.zip")

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
        self.assertEqual(meta["starterKitVersion"], "1.4.0")
        self.assertEqual(meta["installerVersion"], "1.4.0")
        self.assertEqual(meta["edition"], "community")
        self.assertEqual(meta["kosContractVersion"], "1.0.0")
        self.assertEqual(meta["communityVersion"], meta["installerVersion"])
        for rel in ("ARCHITECTURE.md", "CHANGELOG.md", "README.md"):
            template = (ROOT / "templates/root" / rel).read_text(encoding="utf-8")
            self.assertIn("{{community_version}}", template)
            self.assertIn("{{installer_version}}", template)
        architecture = (ROOT / "templates/root/ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn("\nversion: {{starter_kit_version}}\n", architecture)

    def test_declared_versions_agree_with_release_metadata(self):
        self.assertEqual([], release.version_findings())

    def test_current_release_identity_is_unified_and_contract_is_independent(self):
        current = {"communityVersion": "2.4.0", "installerVersion": "2.4.0",
                   "starterKitVersion": "2.4.0", "kosContractVersion": "1.0.0"}
        self.assertEqual("kos-community-v2.4.0.zip", release.customer_archive_name(current))
        for field in ("communityVersion", "installerVersion", "starterKitVersion"):
            with self.subTest(field=field), self.assertRaisesRegex(release.Blocked, "RELEASE_VERSION_DRIFT"):
                release.customer_archive_name(dict(current, **{field: "2.4.1"}))
        for invalid in ("02.4.0", "2.4.0-preview", "v2.4.0", None):
            with self.subTest(value=invalid), self.assertRaisesRegex(release.Blocked, "VERSION_INVALID"):
                release.release_version(dict(current, communityVersion=invalid))

    def test_github_tag_event_requires_the_canonical_full_ref(self):
        tag = "v2.4.0"
        event = {"GITHUB_ACTIONS": "true", "GITHUB_REF_TYPE": "tag", "GITHUB_REF": "refs/tags/" + tag,
                 "GITHUB_REF_NAME": tag, "GITHUB_EVENT_NAME": "push"}
        for kind in ("push", "workflow_dispatch", "release"):
            self.assertTrue(release.github_tag_context(tag, dict(event, GITHUB_EVENT_NAME=kind)))
        for overrides in ({"GITHUB_REF": "refs/tags/v0.1.0"}, {"GITHUB_REF": ""},
                          {"GITHUB_REF_NAME": "v0.1.0"}, {"GITHUB_REF_TYPE": "branch"},
                          {"GITHUB_REF": "refs/heads/main"}):
            with self.subTest(overrides=overrides), self.assertRaisesRegex(release.Blocked, "RELEASE_GITHUB"):
                release.github_tag_context(tag, dict(event, **overrides))
        for kind, ref in (("push", "refs/heads/main"), ("workflow_dispatch", "refs/heads/review"),
                          ("pull_request", "refs/pull/5/merge")):
            self.assertFalse(release.github_tag_context(tag, {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": kind,
                                                              "GITHUB_REF": ref, "GITHUB_REF_TYPE": "branch"}))
        self.assertFalse(release.github_tag_context(tag, {}))

    def test_tag_verifies_real_commit_and_all_release_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            def git(*args):
                return subprocess.check_output(["git", "-C", str(root), "-c", "user.name=Release Test",
                    "-c", "user.email=fixture@localhost", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false",
                    "-c", "core.hooksPath=" + str(root / "unused-hooks"), *args]).decode().strip()
            git("init", "--quiet")
            version = "2.4.0"
            tag = "v" + version
            files = [".gitattributes", "CHANGELOG.md", "an example.ps1",
                     "installer/release-files.json", "installer/release.json"]
            (root / "installer").mkdir()
            (root / files[0]).write_bytes(b"* text eol=lf\n*.ps1 text eol=crlf\n")
            changelog = root / "CHANGELOG.md"
            changelog.write_bytes(b"## KOS Community 2.4.0 (unreleased)\n")
            script = root / "an example.ps1"
            script.write_bytes(b"Write-Output ok\r\n")
            (root / files[-2]).write_text(json.dumps({"files": files}), encoding="utf-8")
            (root / files[-1]).write_text(json.dumps({"starterKitVersion": version}), encoding="utf-8")
            git("add", "--", *files)
            git("commit", "--quiet", "-m", "Candidate")
            with mock.patch.object(release, "checked_files", return_value=files):
                with self.assertRaisesRegex(release.Blocked, "RELEASE_TAG_MISSING"):
                    release.verify_release_tag(root, version)
                git("tag", tag)
                with self.assertRaisesRegex(release.Blocked, "RELEASE_CHANGELOG_NOT_FINAL"):
                    release.verify_release_tag(root, version)
                first = git("rev-parse", "HEAD")
                changelog.write_bytes(b"## KOS Community 2.4.0\n")
                git("commit", "--quiet", "-am", "Ready")
                with self.assertRaisesRegex(release.Blocked, "RELEASE_TAG_COMMIT_MISMATCH"):
                    release.verify_release_tag(root, version)
                for options in ((), ("-a", "-m", "Release test")):
                    git("tag", "-f", *options, tag)
                    oid = git("rev-parse", "refs/tags/" + tag)
                    self.assertEqual(release.candidate_manifest(root, files)["fingerprint"],
                                     release.verify_release_tag(root, version, oid))
                with self.assertRaisesRegex(release.Blocked, "RELEASE_GITHUB_COMMIT_MISMATCH"):
                    release.verify_release_tag(root, version, first)
                git("update-index", "--assume-unchanged", "--", script.name)
                script.write_bytes(b"Write-Output changed\r\n")
                with self.assertRaisesRegex(release.Blocked, "RELEASE_TAG_SOURCE_MISMATCH"):
                    release.verify_release_tag(root, version)
                script.write_bytes(b"Write-Output ok\r\n")
                (root / "untracked.md").write_text("extra", encoding="utf-8")
                self.assertTrue(release.verify_release_tag(root, version))
                with mock.patch.object(release, "checked_files", return_value=files + ["untracked.md"]):
                    with self.assertRaisesRegex(release.Blocked, "RELEASE_TAG_SOURCE_MISMATCH"):
                        release.verify_release_tag(root, version)

    def test_tagged_cli_rejects_an_explicit_candidate_from_another_source(self):
        meta = json.loads((ROOT / "installer/release.json").read_bytes())
        tag = "v" + meta["communityVersion"]
        env = {"GITHUB_REF_TYPE": "tag", "GITHUB_REF": "refs/tags/" + tag, "GITHUB_REF_NAME": tag}
        # Keep the native process environment intact, including empty Git settings on Windows.
        with mock.patch.object(os, "environ", env), mock.patch.object(sys, "argv", [
                "release.py", "--stage", "--candidate", "another-candidate"]), \
                mock.patch.object(release, "verify_release_tag", return_value="tagged"), \
                mock.patch.object(release, "verify_candidate", return_value=([], {"fingerprint": "other"})), \
                self.assertRaisesRegex(release.Blocked, "RELEASE_TAG_CANDIDATE_MISMATCH"):
            release.main()

    def test_current_power_up_guidance_does_not_pin_an_obsolete_installer(self):
        for name in ("POWER-UP-INSTALLATION-GUIDE.md", "PACKAGES-V1.md", "POWER-UP-MANIFEST-SPECIFICATION.md"):
            with self.subTest(name=name):
                guide = (ROOT / "docs" / name).read_text(encoding="utf-8")
                self.assertNotRegex(guide.lower(), r"\bv1\.2\s+(?:installer|engine|lifecycle)\b")

    def test_legacy_yaml_scaffold_directs_installation_to_shipped_package_guide(self):
        guide = ROOT / "templates/power-up-template/docs/installation.md"
        content = guide.read_text(encoding="utf-8")
        self.assertNotRegex(content, r"powerups\.(?:sh|ps1)\s+register\b")
        install_guide = "../../../docs/POWER-UP-INSTALLATION-GUIDE.md"
        self.assertIn(f"]({install_guide})", content)
        archive_files = json.loads((ROOT / "installer/archive-files.json").read_bytes())["files"]
        self.assertIn((guide.parent / install_guide).resolve().relative_to(ROOT.resolve()).as_posix(), archive_files)

    def test_customer_release_labels_are_checked_in_the_current_section(self):
        meta = json.loads((ROOT / "installer/release.json").read_bytes())
        tag = "v" + meta["starterKitVersion"]
        label = "KOS Community " + meta["communityVersion"]
        asset = release.customer_archive_name(meta)
        read_text = Path.read_text

        def mislabel(path, *args, **kwargs):
            text = read_text(path, *args, **kwargs)
            if path == ROOT / "README.md":
                return text.replace(label, label + "9") + "\n## Earlier releases\n" + label
            if path == ROOT / "INSTALL.md":
                return text.replace(asset, "incorrect.zip") + f"\n## Earlier releases\n`{asset}`"
            if path == ROOT / "CHANGELOG.md":
                tag_line = f"Distribution tag `{tag}`"
                current = text.replace(tag_line, "Incorrect distribution tag", 1).replace(asset, "incorrect.zip")
                return current + f"\n{tag_line}\n`{asset}`"
            return text

        with mock.patch.object(Path, "read_text", mislabel):
            issues = release.version_findings()
        self.assertIn("README.md release identity is missing " + label, issues)
        self.assertIn("CHANGELOG.md current release must identify distribution tag " + tag, issues)
        self.assertIn("INSTALL.md must name the current customer archive " + asset, issues)
        self.assertIn("CHANGELOG.md current release must name the customer archive " + asset, issues)

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
            metadata = {"communityVersion": "2.4.0", "installerVersion": "2.4.0", "starterKitVersion": "2.4.0"}
            (root / "installer/release.json").write_text(json.dumps(metadata), encoding="utf-8")
            (root / "NOTICE").write_text("reviewed", encoding="utf-8")
            files = ["NOTICE", "installer/release.json"]
            output = root / "build/kos-community-v2.4.0.zip"
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
                    with self.assertRaisesRegex(release.Blocked, "RELEASE_TAG_PAYLOAD_MISMATCH"):
                        release.build_archive(payload, root=root, tagged_source="different-source")
                    for name in ("cosmetic.zip", "kos-community-v1.3.1.zip", "KOS-Community-v2.4.0.ZIP"):
                        bad = root / "build" / name
                        with self.assertRaisesRegex(release.Blocked, "RELEASE_OUTPUT_NAME_MISMATCH"):
                            release.build_archive(payload, bad, root)
                        self.assertFalse(bad.exists())
                    prior_asset = root / "build/kos-starter-kit-v3.1.1.zip"
                    prior_asset.write_bytes(b"Earlier download")
                    release.build_archive(payload, root=root)
                    self.assertEqual(prior_asset.read_bytes(), b"Earlier download")
                    with self.assertRaisesRegex(release.Blocked, "RELEASE_ARCHIVE_ALREADY_EXISTS"):
                        release.build_archive(payload, root=root)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(["NOTICE", "installer/release.json"], archive.namelist())
                self.assertEqual(b"reviewed", archive.read("NOTICE"))


if __name__ == "__main__":
    unittest.main()
