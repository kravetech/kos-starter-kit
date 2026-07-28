#!/usr/bin/env python3
"""Validation, privacy, and manifest utilities for the starter kit."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_PROJECT_FILES = [
    "README.md", "INSTALL.md", "INITIALIZE.md", "KOS-INSTALLER.md", "QUESTIONNAIRE.md",
    "MANIFEST.md", "PRIVACY.md", "LICENSE", "LICENSE-NOTICE.md", "SECURITY.md",
    "PUBLICATION.md", "CHANGELOG.md", "install.ps1",
    "install.sh", "initialize.ps1", "initialize.sh", ".gitignore", ".gitattributes",
    "installer/answers.example.json", "installer/questionnaire.schema.json",
    "installer/structure.manifest.json", "installer/installer-state.template.json",
    "installer/private-terms.example.txt",
    "scripts/validate-starter-kit.ps1", "scripts/validate-starter-kit.sh",
    "scripts/validate-installation.ps1", "scripts/validate-installation.sh",
    "scripts/privacy-scan.ps1", "scripts/privacy-scan.sh",
    "scripts/public-release-audit.ps1", "scripts/generate-manifest.ps1", "scripts/generate-manifest.sh",
    ".github/workflows/ci.yml",
]
REQUIRED_PROJECT_DIRS = [
    "installer", "templates/root", "templates/system", "templates/business", "templates/projects",
    "templates/personal", "templates/hobbies", "templates/knowledge", "templates/inbox",
    "templates/daily", "templates/attachments", "templates/archive", "templates/automations",
    "scripts", "reports", "examples", "logs", "build", "test-output",
]
INSTALL_HEADINGS = [
    "Role", "Objective", "Inputs", "Constraints", "Privacy Rules", "Questionnaire",
    "Installation Modes", "Dry Run", "File Generation", "Template Processing",
    "Context Bootstrap", "Automation Setup", "Git Initialization", "Validation",
    "Conflict Handling", "Resume Behavior", "Rollback", "Installation Report",
]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_-]{12,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
ABSOLUTE_PATH = re.compile(
    r"(?i)(?:[A-Z]:\\[A-Za-z0-9][A-Za-z0-9 _.-]+(?:\\[A-Za-z0-9][A-Za-z0-9 _.-]*)*|/(?:Users|home)/[^/\s]+/)"
)
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".ps1", ".sh", ".py", ".txt", ".gitignore"}
FORBIDDEN_RELEASE_PATHS = {
    "installer/answers.json",
    "installer/local-config.json",
    "installer/private-terms.txt",
}
FORBIDDEN_RELEASE_PREFIXES = ("logs/", "build/", "test-output/")
ALLOWED_RELEASE_KEEP_FILES = {"logs/.gitkeep", "build/.gitkeep", "test-output/.gitkeep"}


def text_files(root: Path, include_generated: bool = False):
    excluded = {".git", "__pycache__", ".claude"}
    if not include_generated:
        excluded |= {"logs", "build", "test-output"}
    for path in root.rglob("*"):
        if path == root / "installer" / "private-terms.txt":
            continue
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == ".gitignore":
            yield path


def load_sensitive_terms(root: Path) -> list[str]:
    denylist = root / "installer" / "private-terms.txt"
    if not denylist.is_file():
        return []
    return [
        line.strip()
        for line in denylist.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def write_report(path: Path, title: str, status: str, findings: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}", "", f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}",
        f"Status: **{status}**", "", "## Findings", "",
    ]
    lines += [f"- {item}" for item in findings] if findings else ["- None."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_starter(root: Path, report: Path) -> int:
    findings: list[str] = []
    for relative in REQUIRED_PROJECT_FILES:
        if not (root / relative).is_file():
            findings.append(f"ERROR missing required file: `{relative}`")
    for relative in REQUIRED_PROJECT_DIRS:
        if not (root / relative).is_dir():
            findings.append(f"ERROR missing required directory: `{relative}`")
    for relative in ("installer/answers.example.json", "installer/questionnaire.schema.json", "installer/structure.manifest.json", "installer/installer-state.template.json"):
        try:
            json.loads((root / relative).read_text(encoding="utf-8-sig"))
        except Exception as exc:
            findings.append(f"ERROR invalid JSON `{relative}`: {exc}")
    installer = (root / "KOS-INSTALLER.md").read_text(encoding="utf-8", errors="replace")
    for heading in INSTALL_HEADINGS:
        if f"## {heading}" not in installer:
            findings.append(f"ERROR installer heading missing: `{heading}`")
    for adapter in ("templates/root/CLAUDE.md", "templates/root/CODEX.md"):
        if (root / adapter).exists() and len((root / adapter).read_text(encoding="utf-8").splitlines()) > 40:
            findings.append(f"ERROR adapter is not thin: `{adapter}`")
    template_tokens: set[str] = set()
    for path in (root / "templates").rglob("*"):
        if path.is_file():
            template_tokens.update(re.findall(r"\{\{([a-z0-9_]+)\}\}", path.read_text(encoding="utf-8", errors="replace")))
    example = json.loads((root / "installer/answers.example.json").read_text(encoding="utf-8"))
    available = set()
    for section in ("user", "system", "privacy", "rhythm"):
        available.update(example.get(section, {}).keys())
    available |= {"system_name", "system_short_name", "system_description"}
    for token in sorted(template_tokens - available):
        findings.append(f"ERROR template token has no answer mapping: `{{{{{token}}}}}`")
    for script in ("install.ps1", "initialize.ps1"):
        content = (root / script).read_text(encoding="utf-8", errors="replace")
        if "$ErrorActionPreference" not in content or "exit" not in content:
            findings.append(f"ERROR unsafe PowerShell error handling: `{script}`")
    status = "PASS" if not any(item.startswith("ERROR") for item in findings) else "FAIL"
    write_report(report, "Starter-Kit Validation Report", status, findings)
    return 0 if status == "PASS" else 2


def validate_install(root: Path, report: Path) -> int:
    findings: list[str] = []
    required_files = ["README.md", "AGENTS.md", "CLAUDE.md", "CODEX.md", "ARCHITECTURE.md", "CONTEXT-POLICY.md", "TOKEN-OPTIMIZATION.md", "memory.md", "handoff.md", "00 - System/Installation/installer-state.json", "00 - System/Installation/INSTALLATION-REPORT.md", "00 - System/Automations/AUTOMATION-REGISTRY.md"]
    required_dirs = ["00 - System", "01 - Business", "02 - Projects", "03 - Personal", "04 - Hobbies", "05 - Knowledge", "06 - Inbox", "07 - Daily", "08 - Templates", "09 - Attachments", "99 - Archive"]
    for relative in required_files:
        if not (root / relative).is_file():
            findings.append(f"ERROR missing installation file: `{relative}`")
    for relative in required_dirs:
        if not (root / relative).is_dir():
            findings.append(f"ERROR missing installation directory: `{relative}`")
    for path in text_files(root, include_generated=True):
        if "{{" in path.read_text(encoding="utf-8", errors="replace"):
            findings.append(f"ERROR unresolved template token: `{path.relative_to(root)}`")
    for adapter in ("CLAUDE.md", "CODEX.md"):
        if (root / adapter).exists() and len((root / adapter).read_text(encoding="utf-8").splitlines()) > 40:
            findings.append(f"ERROR adapter is not thin: `{adapter}`")
    registry = root / "00 - System/Automations/AUTOMATION-REGISTRY.md"
    if registry.exists() and "Status: Not configured" not in registry.read_text(encoding="utf-8"):
        findings.append("ERROR external automations are not explicitly unconfigured")
    status = "PASS" if not any(item.startswith("ERROR") for item in findings) else "FAIL"
    write_report(report, "Installation Validation Report", status, findings)
    return 0 if status == "PASS" else 2


def scan_privacy_files(root: Path, paths: list[Path], sensitive_terms: list[str]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        relative = path.relative_to(root)
        text = path.read_text(encoding="utf-8", errors="replace")
        for term in sensitive_terms:
            if term.lower() in text.lower():
                findings.append(f"ERROR private reference term `{term}` in `{relative}`")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"ERROR potential secret-like value in `{relative}`")
                break
        if ABSOLUTE_PATH.search(text):
            findings.append(f"ERROR absolute machine path in `{relative}`")
    return findings


def privacy(root: Path, report: Path, include_generated: bool = False) -> int:
    sensitive_terms = load_sensitive_terms(root)
    findings = scan_privacy_files(root, list(text_files(root, include_generated)), sensitive_terms)
    if not sensitive_terms:
        findings.append("WARN no local private-term denylist configured; copy `installer/private-terms.example.txt` to ignored `installer/private-terms.txt`")
    status = "PASS" if not any(item.startswith("ERROR") for item in findings) else "FAIL"
    write_report(report, "Privacy Scan", status, findings)
    return 0 if status == "PASS" else 2


def release_audit(root: Path, report: Path) -> int:
    findings: list[str] = []
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        findings.append(f"ERROR unable to enumerate tracked Git files: {exc}")
        write_report(report, "Public Release Audit", "FAIL", findings)
        return 2
    tracked = [item for item in result.stdout.decode("utf-8", errors="replace").split("\0") if item]
    if not tracked:
        findings.append("ERROR Git index contains no tracked files; stage the intended release before running this audit")
    for relative in tracked:
        normalized = relative.replace("\\", "/")
        if (
            normalized in FORBIDDEN_RELEASE_PATHS
            or (
                normalized.startswith(FORBIDDEN_RELEASE_PREFIXES)
                and normalized not in ALLOWED_RELEASE_KEEP_FILES
            )
        ):
            findings.append(f"ERROR forbidden release path is tracked: `{normalized}`")
    source_paths = [
        root / relative
        for relative in tracked
        if (root / relative).is_file()
        and ((root / relative).suffix.lower() in TEXT_SUFFIXES or (root / relative).name == ".gitignore")
    ]
    findings.extend(scan_privacy_files(root, source_paths, load_sensitive_terms(root)))
    staged = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8", errors="replace")
    modes = {}
    for entry in staged.split("\0"):
        if not entry or "\t" not in entry:
            continue
        metadata, relative = entry.split("\t", 1)
        modes[relative.replace("\\", "/")] = metadata.split()[0]
    for relative in (item.replace("\\", "/") for item in tracked if item.endswith(".sh")):
        if modes.get(relative) != "100755":
            findings.append(f"ERROR `{relative}` is not staged as executable; run `git update-index --chmod=+x {relative}`")
    for relative in tracked:
        normalized = relative.replace("\\", "/")
        if not normalized.startswith(".github/workflows/"):
            continue
        workflow = (root / relative).read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"(?m)^\s*-\s+uses:\s*[^@\s]+@([^\s#]+)", workflow):
            if not re.fullmatch(r"[0-9a-fA-F]{40}", match.group(1)):
                findings.append(f"ERROR GitHub Action is not pinned to a full commit SHA in `{normalized}`: `{match.group(0).strip()}`")
    if not (root / "LICENSE").is_file():
        findings.append("ERROR `LICENSE` is missing")
    versions = {
        "architecture": re.search(r"(?m)^version:\s*([0-9]+\.[0-9]+\.[0-9]+)", (root / "ARCHITECTURE.md").read_text(encoding="utf-8")),
        "python": re.search(r'(?m)^VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', (root / "installer/install.py").read_text(encoding="utf-8")),
        "powershell": re.search(r'(?m)^\$script:InstallerVersion\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', (root / "install.ps1").read_text(encoding="utf-8")),
    }
    resolved_versions = {name: match.group(1) if match else None for name, match in versions.items()}
    if None in resolved_versions.values() or len(set(resolved_versions.values())) != 1:
        findings.append(f"ERROR release versions are inconsistent: {resolved_versions}")
    status = "PASS" if not any(item.startswith("ERROR") for item in findings) else "FAIL"
    if not findings:
        findings.append("Tracked release content passed path, privacy, license, and version checks.")
    write_report(report, "Public Release Audit", status, findings)
    return 0 if status == "PASS" else 2


def manifest(root: Path, output: Path) -> int:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            data = path.read_bytes()
            files.append({
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "files": files}, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate-starter", "validate-install", "privacy", "release-audit", "manifest"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-generated", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "validate-starter":
        return validate_starter(root, (args.report or root / "reports/VALIDATION-REPORT.md").resolve())
    if args.command == "validate-install":
        return validate_install(root, (args.report or root / "VALIDATION-REPORT.md").resolve())
    if args.command == "privacy":
        return privacy(root, (args.report or root / "PRIVACY-SCAN.md").resolve(), args.include_generated)
    if args.command == "release-audit":
        return release_audit(root, (args.report or root / "reports/RELEASE-AUDIT.md").resolve())
    return manifest(root, (args.output or root / "build/file-manifest.json").resolve())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(3)
