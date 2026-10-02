#!/usr/bin/env python3
"""Freeze source, stage and test client payload, then package those exact bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import os
import shutil
import uuid
from datetime import datetime, timezone
from urllib.parse import unquote

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT / "installer"))
from safety import Blocked, digest, encoded, json_read, relative, safe

SOURCE_ONLY = {
    ".github/workflows/ci.yml", "ARCHITECTURE.md", "MANIFEST.md", "PUBLICATION.md",
    "docs/POWER-UP-DEVELOPER-GUIDE.md", "docs/POWER-UP-MANIFEST-SPECIFICATION.md",
    "installer/archive-files.json", "installer/release-files.json",
    "installer/migration-guide.md", "installer/validation-checklist.md",
    "scripts/public-release-audit.ps1", "scripts/release.py",
    "scripts/validate-starter-kit.ps1", "scripts/validate-starter-kit.sh",
}


def archive_entry(rel):
    entry = zipfile.ZipInfo(rel, (2026, 9, 18, 0, 0, 0))
    # Preserve POSIX execute permissions even when the producer is Windows.
    entry.create_system = 3
    entry.external_attr = (0o100755 if rel.endswith(".sh") else 0o100644) << 16
    entry.compress_type = zipfile.ZIP_DEFLATED
    return entry


def checked_files(root=ROOT):
    files = json_read(root / "installer/release-files.json")["files"]
    if len(files) != len(set(files)):
        raise Blocked("RELEASE_DUPLICATE")
    forbidden = {"reports", "logs", "build", "output", "test-output", "tmp", ".claude", ".git", "__pycache__"}
    for rel in files:
        relative(rel)
        if any(p in forbidden for p in Path(rel).parts) or Path(rel).name in {"answers.json", "local-config.json", "private-terms.txt"} or Path(rel).suffix in {".pdf", ".html", ".pyc"}:
            raise Blocked("RELEASE_FORBIDDEN_PATH")
        path = safe(root, rel)
        if not path.is_file():
            raise Blocked("RELEASE_MISSING_FILE:" + rel)
        if rel.endswith(".sh") and b"\r" in path.read_bytes():
            raise Blocked("RELEASE_SHELL_REQUIRES_LF:" + rel)
        text = path.read_text(encoding="utf-8-sig")
        if re.search(r"(?i)(password|api[_-]?key|access[_-]?token)\s*[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{12,}", text):
            raise Blocked("RELEASE_SECRET:" + rel)
        if re.search(r"(?i)[A-Z]:\\[A-Za-z0-9][A-Za-z0-9 _.-]+\\|/(?:Users|home)/[^/\s]+/", text):
            raise Blocked("RELEASE_MACHINE_PATH:" + rel)
    for asset in json_read(root / "installer/assets.json")["assets"]:
        if asset["source"] not in files:
            raise Blocked("RELEASE_ASSET_OMITTED")
    for test in (root / "tests").glob("test_*.py"):
        if "tests/" + test.name not in files:
            raise Blocked("RELEASE_TEST_OMITTED:" + test.name)
    findings = version_findings(root)
    if findings:
        raise Blocked("RELEASE_VERSION_DRIFT: " + "; ".join(findings))
    source_files = sorted(files)
    checked_archive_files(root, source_files)
    return source_files


def checked_archive_files(root, source_files):
    """Audit the client payload separately from the tested source candidate."""
    if "installer/archive-files.json" not in source_files:
        raise Blocked("RELEASE_ARCHIVE_SPEC_NOT_FROZEN")
    manifest = json_read(safe(root, "installer/archive-files.json"))
    files = manifest.get("files")
    if manifest.get("schemaVersion") != "1.0.0" or not isinstance(files, list) or any(not isinstance(rel, str) for rel in files):
        raise Blocked("RELEASE_ARCHIVE_SPEC_INVALID")
    if files != sorted(set(files)):
        raise Blocked("RELEASE_ARCHIVE_DUPLICATE_OR_UNSORTED")
    if set(files) - set(source_files):
        raise Blocked("RELEASE_ARCHIVE_NOT_FROZEN")
    if set(files) & SOURCE_ONLY or any(rel.startswith("tests/") for rel in files):
        raise Blocked("RELEASE_ARCHIVE_INTERNAL_FILE")
    required = {"README.md", "INSTALL.md", "LICENSE", "NOTICE", "install.ps1", "install.sh",
                "installer/install.py", "installer/engine.ps1", "installer/release.json"}
    if required - set(files):
        raise Blocked("RELEASE_ARCHIVE_REQUIRED_FILE")
    for asset in json_read(root / "installer/assets.json")["assets"]:
        if asset["source"] not in files:
            raise Blocked("RELEASE_ARCHIVE_ASSET_OMITTED:" + asset["source"])
    included = set(files)
    for rel in files:
        if not rel.endswith(".md") or rel.startswith(("templates/", "examples/")):
            continue
        content = safe(root, rel).read_text(encoding="utf-8-sig")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            target = target.strip().strip("<>")
            if not target or target.startswith("#") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            destination = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not destination:
                continue
            try:
                resolved = (root / Path(rel).parent / destination).resolve().relative_to(root.resolve()).as_posix()
            except ValueError as error:
                raise Blocked("RELEASE_ARCHIVE_DOC_LINK_OUTSIDE:" + rel) from error
            if resolved not in included and not any(item.startswith(resolved.rstrip("/") + "/") for item in included):
                raise Blocked("RELEASE_ARCHIVE_DOC_LINK_MISSING:" + rel + " -> " + destination)
    return files


def version_findings(root=ROOT):
    """Every declared version must agree with installer/release.json, the single version source."""
    release = json_read(root / "installer/release.json")
    semver = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
    keys = ("starterKitVersion", "installerVersion", "communityVersion", "kosContractVersion", "schemaVersion", "adapterVersion")
    findings = ["installer/release.json " + key + " is missing or not MAJOR.MINOR.PATCH" for key in keys if not semver.match(str(release.get(key, "")))]
    if findings:
        return findings
    kit, community, contract = release["starterKitVersion"], release["communityVersion"], release["kosContractVersion"]
    if release.get("edition") != "community":
        findings.append("installer/release.json edition must be community")
    if kit not in release.get("supportedUpgradeVersions", []):
        findings.append("installer/release.json supportedUpgradeVersions must include " + kit)
    state = json_read(root / "installer/installer-state.template.json")
    for key in ("starterKitVersion", "installerVersion", "communityVersion", "kosContractVersion", "schemaVersion"):
        if state.get(key) != release[key]:
            findings.append("installer/installer-state.template.json " + key + " != " + release[key])
    architecture = (root / "ARCHITECTURE.md").read_text(encoding="utf-8-sig")
    for field, expected in (("version", kit), ("community_version", community), ("kos_contract_version", contract)):
        match = re.search(r"(?m)^" + field + r":\s*(\S+)\s*$", architecture)
        if not match or match[1] != expected:
            findings.append("ARCHITECTURE.md front matter " + field + " != " + expected)
    for label, expected in (("Version", "v" + kit), ("Community version", community), ("KOS Core contract", contract)):
        if "| " + label + " | `" + expected + "` |" not in architecture:
            findings.append("ARCHITECTURE.md table row '" + label + "' != " + expected)
    heading = re.search(r"(?m)^## \[([^\]]+)\]", (root / "CHANGELOG.md").read_text(encoding="utf-8-sig"))
    if not heading or heading[1] != kit:
        findings.append("CHANGELOG.md latest release heading != " + kit)
    publication_file = root / "PUBLICATION.md"
    if publication_file.is_file():
        publication = publication_file.read_text(encoding="utf-8-sig")
        for phrase in ("Starter Kit " + kit, "Community " + community, "contract " + contract):
            if phrase not in publication:
                findings.append("PUBLICATION.md does not state '" + phrase + "'")
    for rel in ("templates/root/README.md", "templates/root/ARCHITECTURE.md"):
        text = (root / rel).read_text(encoding="utf-8-sig")
        for token in ("{{starter_kit_version}}", "{{community_version}}", "{{kos_contract_version}}"):
            if token not in text:
                findings.append(rel + " is missing " + token)
    workflow = root / ".github/workflows/ci.yml"
    if workflow.is_file() and re.search(r"kos-starter-kit-v[0-9]", workflow.read_text(encoding="utf-8-sig")):
        findings.append(".github/workflows/ci.yml hard-codes a release archive version")
    return findings


def file_hashes(root, files):
    return {rel: digest(safe(root, rel).read_bytes()) for rel in files}


def candidate_manifest(root, files):
    hashes = file_hashes(root, files)
    release = json_read(root / "installer/release.json")
    return {
        "schemaVersion": "1.0.0",
        "hashAlgorithm": "sha256",
        "starterKitVersion": release["starterKitVersion"],
        "fileHashes": hashes,
        "fingerprint": digest(encoded(hashes)),
    }


def candidate_path(root, manifest):
    name = "kos-starter-kit-v{}-source-{}".format(manifest["starterKitVersion"], manifest["fingerprint"][:16])
    return safe(root, "build/candidates/" + name)


def verify_candidate(candidate, root=ROOT):
    """Require a complete frozen source tree and reject edits to shipped bytes."""
    candidate = Path(os.path.abspath(candidate))
    candidates = Path(os.path.abspath(root / "build/candidates"))
    if candidate.parent != candidates or not candidate.name.startswith("kos-starter-kit-v"):
        raise Blocked("RELEASE_CANDIDATE_OUTSIDE_BUILD")
    safe(root, candidate.relative_to(root).as_posix())
    if not candidate.is_dir():
        raise Blocked("RELEASE_CANDIDATE_MISSING")
    manifest = json_read(safe(candidate, ".release-candidate.json"))
    files = checked_files(candidate)
    expected = candidate_manifest(candidate, files)
    if manifest != expected or candidate_path(root, expected) != candidate:
        raise Blocked("RELEASE_CANDIDATE_CHANGED")
    allowed = set(files) | {".release-candidate.json"}
    for path in candidate.rglob("*"):
        rel = path.relative_to(candidate)
        if "__pycache__" in rel.parts or rel.parts[0] == "test-output":
            continue
        safe(candidate, rel.as_posix())
        if path.is_file() and rel.as_posix() not in allowed:
            raise Blocked("RELEASE_CANDIDATE_EXTRA_FILE:" + rel.as_posix())
    return files, expected


def freeze_source(root=ROOT):
    """Publish a reviewable source folder only after a stable byte-for-byte copy."""
    files = checked_files(root)
    manifest = candidate_manifest(root, files)
    candidate = candidate_path(root, manifest)
    if candidate.exists():
        verify_candidate(candidate, root)
        return candidate
    candidates = safe(root, "build/candidates")
    candidates.mkdir(parents=True, exist_ok=True)
    temporary = safe(root, "build/candidates/.freeze-" + uuid.uuid4().hex)
    temporary.mkdir()
    try:
        for rel in files:
            destination = safe(temporary, rel, write=True)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(safe(root, rel).read_bytes())
        if candidate_manifest(root, files) != manifest or checked_files(temporary) != files or candidate_manifest(temporary, files) != manifest:
            raise Blocked("RELEASE_SOURCE_CHANGED_DURING_FREEZE")
        safe(temporary, ".release-candidate.json", write=True).write_bytes(encoded(manifest))
        if candidate.exists():
            raise Blocked("RELEASE_CANDIDATE_ALREADY_EXISTS")
        temporary.rename(candidate)
    finally:
        if temporary.exists():
            # This directory was created here; verify its parent before recursive cleanup.
            if temporary.resolve().parent != candidates.resolve() or not temporary.name.startswith(".freeze-"):
                raise Blocked("RELEASE_TEMP_CLEANUP_UNSAFE")
            shutil.rmtree(temporary)
    verify_candidate(candidate, root)
    return candidate


def run_tests(candidate, root=ROOT):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=candidate, env=env, check=True)
    if os.name == "nt":
        for shell in ("pwsh", "powershell"):
            executable = shutil.which(shell)
            if not executable:
                raise Blocked("RELEASE_NATIVE_TEST_HOST_UNAVAILABLE")
            # Keep disposable Windows paths short; nested vault paths may exceed
            # the host's legacy path limit even when the tested source is valid.
            fixture = safe(root, "test-output/rn-" + uuid.uuid4().hex[:10] + "/vault", write=True)
            subprocess.run([executable, "-NoProfile", "-File", str(candidate / "tests/native-lifecycle.ps1"), "-FixtureRoot", str(fixture)], cwd=candidate, env=env, check=True)


def payload_manifest(candidate, files, source_manifest):
    hashes = file_hashes(candidate, files)
    release = json_read(candidate / "installer/release.json")
    return {
        "schemaVersion": "1.0.0",
        "hashAlgorithm": "sha256",
        "starterKitVersion": release["starterKitVersion"],
        "sourceFingerprint": source_manifest["fingerprint"],
        "fileHashes": hashes,
        "fingerprint": digest(encoded(hashes)),
    }


def payload_path(root, manifest):
    name = "kos-starter-kit-v{}-payload-{}-source-{}".format(
        manifest["starterKitVersion"], manifest["fingerprint"][:16], manifest["sourceFingerprint"][:12])
    return safe(root, "build/payloads/" + name)


def verify_payload(payload, root=ROOT, *, require_tested=False):
    """Tie a staged client folder and its test evidence to the frozen source."""
    payload = Path(os.path.abspath(payload))
    payloads = Path(os.path.abspath(root / "build/payloads"))
    if payload.parent != payloads or not payload.name.startswith("kos-starter-kit-v"):
        raise Blocked("RELEASE_PAYLOAD_OUTSIDE_BUILD")
    safe(root, payload.relative_to(root).as_posix())
    if not payload.is_dir():
        raise Blocked("RELEASE_PAYLOAD_MISSING")
    manifest = json_read(safe(payload, ".release-payload.json"))
    if manifest.get("schemaVersion") != "1.0.0" or manifest.get("hashAlgorithm") != "sha256":
        raise Blocked("RELEASE_PAYLOAD_MANIFEST_INVALID")
    source = candidate_path(root, {"starterKitVersion": manifest["starterKitVersion"],
                                   "fingerprint": manifest["sourceFingerprint"]})
    source_files, source_manifest = verify_candidate(source, root)
    files = checked_archive_files(source, source_files)
    expected = payload_manifest(source, files, source_manifest)
    if manifest != expected or payload_path(root, expected) != payload or file_hashes(payload, files) != expected["fileHashes"]:
        raise Blocked("RELEASE_PAYLOAD_CHANGED")
    allowed = set(files) | {".release-payload.json", ".release-tested.json"}
    for path in payload.rglob("*"):
        rel = path.relative_to(payload).as_posix()
        safe(payload, rel)
        if path.is_file() and rel not in allowed:
            raise Blocked("RELEASE_PAYLOAD_EXTRA_FILE:" + rel)
    if require_tested:
        proof_path = safe(payload, ".release-tested.json")
        if not proof_path.is_file():
            raise Blocked("RELEASE_PAYLOAD_UNTESTED")
        proof = json_read(proof_path)
        if (proof.get("schemaVersion") != "1.0.0" or proof.get("payloadFingerprint") != manifest["fingerprint"] or
                proof.get("sourceFingerprint") != manifest["sourceFingerprint"] or
                proof.get("validatedOperations") != ["new", "upgrade-1.1.0", "enhance-obsidian"]):
            raise Blocked("RELEASE_PAYLOAD_TEST_PROOF_INVALID")
    return files, manifest


def run_payload_tests(payload, root, fingerprint):
    """Install and validate directly from the client folder; never extract a ZIP."""
    # Installer fixtures can contain deeply nested numbered paths on Windows.
    test_root = safe(root, "test-output/pv-" + fingerprint[:4] + "-" + uuid.uuid4().hex[:8])
    test_root.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    installer = str(payload / "installer/install.py")
    answers = str(payload / "installer/answers.example.json")

    def call(operation, target, *options):
        command = [sys.executable, installer, "--answers", answers, "--target", str(target),
                   "--operation", operation, *options]
        subprocess.run(command, cwd=payload, env=env, stdout=subprocess.DEVNULL, check=True)

    fresh = test_root / "new"
    call("new", fresh, "--approve")
    call("validate", fresh)

    legacy = test_root / "legacy-1.1.0"
    state = safe(legacy, "00 - System/Installation/installer-state.json", write=True)
    state.parent.mkdir(parents=True)
    state.write_bytes(encoded({"installer_version": "1.1.0"}))
    original = {
        "AGENTS.md": b"Customized legacy router\n",
        "notes/project.md": b"Preserved user knowledge\n",
    }
    for rel, content in original.items():
        path = safe(legacy, rel, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    call("upgrade", legacy, "--approve")
    call("validate", legacy)
    if any(safe(legacy, rel).read_bytes() != content for rel, content in original.items()):
        raise Blocked("RELEASE_PAYLOAD_LEGACY_BYTES_CHANGED")

    obsidian = test_root / "obsidian"
    original = {
        ".obsidian/app.json": b'{"userChoice":true}\n',
        "Notes/Start.md": b"[[Alpha]] [guide](../Docs/Guide%20One.md)\n",
        "Notes/Alpha.md": b"# Alpha\n",
        "Docs/Guide One.md": b"# Guide\n",
        "Media/diagram.png": b"synthetic image bytes",
    }
    for rel, content in original.items():
        path = safe(obsidian, rel, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    call("enhance", obsidian, "--mode", "minimal", "--approve")
    call("validate", obsidian)
    if any(safe(obsidian, rel).read_bytes() != content for rel, content in original.items()):
        raise Blocked("RELEASE_PAYLOAD_OBSIDIAN_BYTES_CHANGED")

    if os.name == "nt":
        for shell in ("pwsh", "powershell"):
            executable = shutil.which(shell)
            if not executable:
                raise Blocked("RELEASE_NATIVE_TEST_HOST_UNAVAILABLE")
            target = test_root / ("native-" + shell)
            base = [executable, "-NoProfile", "-File", str(payload / "install.ps1"),
                    "-Answers", answers, "-Target", str(target)]
            subprocess.run([*base, "-Operation", "new", "-Approve"], cwd=payload, env=env, stdout=subprocess.DEVNULL, check=True)
            subprocess.run([*base, "-Operation", "validate"], cwd=payload, env=env, stdout=subprocess.DEVNULL, check=True)
    else:
        target = test_root / "bash"
        base = ["bash", str(payload / "install.sh"), "--answers", answers, "--target", str(target)]
        subprocess.run([*base, "--operation", "new", "--approve"], cwd=payload, env=env, stdout=subprocess.DEVNULL, check=True)
        subprocess.run([*base, "--operation", "validate"], cwd=payload, env=env, stdout=subprocess.DEVNULL, check=True)


def stage_payload(candidate, root=ROOT):
    """Copy, test, and retain the exact client files that a later ZIP may contain."""
    candidate = Path(os.path.abspath(candidate))
    files, source_manifest = verify_candidate(candidate, root)
    run_tests(candidate, root)
    if verify_candidate(candidate, root) != (files, source_manifest):
        raise Blocked("RELEASE_SOURCE_CHANGED_DURING_TESTS")
    payload_files = checked_archive_files(candidate, files)
    manifest = payload_manifest(candidate, payload_files, source_manifest)
    payload = payload_path(root, manifest)
    if not payload.exists():
        payloads = safe(root, "build/payloads")
        payloads.mkdir(parents=True, exist_ok=True)
        temporary = safe(root, "build/payloads/.stage-" + uuid.uuid4().hex)
        temporary.mkdir()
        try:
            for rel in payload_files:
                destination = safe(temporary, rel, write=True)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(safe(candidate, rel).read_bytes())
            if payload_manifest(candidate, payload_files, source_manifest) != manifest or file_hashes(temporary, payload_files) != manifest["fileHashes"]:
                raise Blocked("RELEASE_SOURCE_CHANGED_DURING_STAGE")
            safe(temporary, ".release-payload.json", write=True).write_bytes(encoded(manifest))
            if payload.exists():
                raise Blocked("RELEASE_PAYLOAD_ALREADY_EXISTS")
            temporary.rename(payload)
        finally:
            if temporary.exists():
                if temporary.resolve().parent != payloads.resolve() or not temporary.name.startswith(".stage-"):
                    raise Blocked("RELEASE_TEMP_CLEANUP_UNSAFE")
                shutil.rmtree(temporary)
    verify_payload(payload, root)
    proof_path = safe(payload, ".release-tested.json", write=True)
    if not proof_path.exists():
        run_payload_tests(payload, root, manifest["fingerprint"])
        verify_payload(payload, root)
        proof = {"schemaVersion": "1.0.0", "payloadFingerprint": manifest["fingerprint"],
                 "sourceFingerprint": manifest["sourceFingerprint"],
                 "validatedOperations": ["new", "upgrade-1.1.0", "enhance-obsidian"],
                 "validatedAt": datetime.now(timezone.utc).isoformat()}
        with proof_path.open("xb") as stream:
            stream.write(encoded(proof))
    verify_payload(payload, root, require_tested=True)
    return payload


def build_archive(payload, output, root=ROOT):
    payload = Path(os.path.abspath(payload))
    payload_files, manifest = verify_payload(payload, root, require_tested=True)
    output = Path(os.path.abspath(output))
    if output.parent != Path(os.path.abspath(root / "build")) or output.suffix.lower() != ".zip":
        raise Blocked("RELEASE_OUTPUT_MUST_BE_BUILD_ZIP")
    safe(root, "build/" + output.name, write=True)
    if output.exists():
        raise Blocked("RELEASE_ARCHIVE_ALREADY_EXISTS")
    temporary = safe(root, "build/." + output.name + "." + uuid.uuid4().hex + ".tmp", write=True)
    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for rel in payload_files:
                archive.writestr(archive_entry(rel), safe(payload, rel).read_bytes())
        with zipfile.ZipFile(temporary) as archive:
            if (archive.namelist() != payload_files or archive.testzip() is not None or
                    any(digest(archive.read(rel)) != manifest["fileHashes"][rel] for rel in payload_files)):
                raise Blocked("RELEASE_ARCHIVE_MISMATCH")
        verify_payload(payload, root, require_tested=True)
        # A hard link publishes the verified ZIP atomically and cannot overwrite one.
        os.link(temporary, output)
        print("Archive verified: " + output.name + " sha256=" + digest(output.read_bytes()))
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--freeze", action="store_true", help="copy the audited release tree to build/candidates")
    action.add_argument("--stage", action="store_true", help="stage and test the exact client payload folder")
    action.add_argument("--build", action="store_true", help="ZIP only a staged and tested payload folder")
    parser.add_argument("--candidate", type=str, help="frozen source folder for --stage, or 'auto'")
    parser.add_argument("--payload", type=str, help="tested client folder for --build, or 'auto'")
    parser.add_argument("--output", type=Path, help="ZIP path under build/; existing files are never replaced")
    args = parser.parse_args()
    if args.freeze:
        if args.candidate or args.payload or args.output:
            raise Blocked("RELEASE_FREEZE_OPTIONS_INVALID")
        candidate = freeze_source()
        print("Frozen source: " + str(candidate))
        return
    if args.stage:
        if args.payload or args.output:
            raise Blocked("RELEASE_STAGE_OPTIONS_INVALID")
        if not args.candidate:
            raise Blocked("RELEASE_CANDIDATE_REQUIRED")
        if args.candidate == "auto":
            files = checked_files()
            candidate = candidate_path(ROOT, candidate_manifest(ROOT, files))
        else:
            candidate = Path(args.candidate)
        payload = stage_payload(candidate)
        print("Tested client payload: " + str(payload))
        return
    if args.build:
        if args.candidate or not args.payload:
            raise Blocked("RELEASE_TESTED_PAYLOAD_REQUIRED")
        if args.payload == "auto":
            files = checked_files()
            candidate = candidate_path(ROOT, candidate_manifest(ROOT, files))
            source_files, source_manifest = verify_candidate(candidate)
            client_files = checked_archive_files(candidate, source_files)
            payload = payload_path(ROOT, payload_manifest(candidate, client_files, source_manifest))
        else:
            payload = Path(args.payload)
        release = json_read(payload / "installer/release.json")
        output = args.output or ROOT / ("build/kos-starter-kit-v" + release["starterKitVersion"] + ".zip")
        build_archive(payload, output)
        return
    if args.candidate or args.payload or args.output:
        raise Blocked("RELEASE_AUDIT_OPTIONS_INVALID")
    files = checked_files()
    payload_files = checked_archive_files(ROOT, files)
    print("Release source audit passed: " + str(len(files)) + " files; client payload: " + str(len(payload_files)) + " files")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
