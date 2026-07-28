#!/usr/bin/env python3
"""Dependency-free Knowledge OS starter-kit installer."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

VERSION = "1.1.0"
ROOT = Path(__file__).resolve().parent.parent
TOKEN_RE = re.compile(r"\{\{([a-z0-9_]+)\}\}")
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_-]{12,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt", ".ps1", ".sh", ".py"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return False


def ensure_safe_destination(root: Path, destination: Path) -> None:
    resolved_root = root.resolve()
    resolved_destination = destination.resolve(strict=False)
    if resolved_destination != resolved_root and resolved_root not in resolved_destination.parents:
        raise ValueError(f"Destination resolves outside installation target: {destination}")


def validate_target(target: Path, *, migration: bool, resume: bool, dry_run: bool) -> None:
    resolved_root = ROOT.resolve()
    resolved_target = target.resolve()
    filesystem_root = Path(target.anchor).resolve() if target.anchor else resolved_target
    home = Path.home().resolve()
    if resolved_target == filesystem_root:
        raise ValueError(f"Unsafe target is a filesystem root: {resolved_target}")
    if resolved_target == home:
        raise ValueError(f"Unsafe target is the user home directory: {resolved_target}")
    if resolved_target == resolved_root:
        raise ValueError(f"Unsafe target equals starter-kit root: {resolved_target}")
    if resolved_target in resolved_root.parents:
        raise ValueError(f"Unsafe target contains the starter-kit root: {resolved_target}")
    if target.exists():
        for path in [target, *target.parents]:
            if path.exists() and is_reparse_point(path):
                raise ValueError(f"Unsafe target ancestry contains a link or reparse point: {path}")
        for path in target.rglob("*"):
            if is_reparse_point(path):
                raise ValueError(f"Unsafe target contains a link or reparse point: {path}")
        if not dry_run and not migration and not resume and any(target.iterdir()):
            raise ValueError(
                "Target is not empty. Use --migration for an existing vault or "
                "--resume for an interrupted installation."
            )


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-").lower() or "user"


def defaults(answers: dict[str, Any]) -> dict[str, Any]:
    today = dt.date.today().isoformat()
    user = answers.setdefault("user", {})
    system = answers.setdefault("system", {})
    privacy = answers.setdefault("privacy", {})
    rhythm = answers.setdefault("rhythm", {})
    install = answers.setdefault("installation", {})
    preferred = str(user.get("preferred_name", "")).strip()
    if not preferred:
        raise ValueError("user.preferred_name is required")
    user.setdefault("full_name", "")
    user.setdefault("author_name", preferred)
    user.setdefault("technical_username", slug(preferred))
    user.setdefault("role", "Knowledge worker")
    user.setdefault("timezone", "UTC")
    user.setdefault("locale", "en")
    user.setdefault("language", "English")
    user.setdefault("communication_style", "Direct, concise, practical")
    system.setdefault("name", "Knowledge OS")
    system.setdefault("short_name", "KOS")
    system.setdefault("root_folder_name", system["name"])
    system.setdefault("description", "A portable operating system for durable knowledge and active work.")
    system.setdefault("motto", "")
    system.setdefault("installation_date", today)
    answers.setdefault("intended_use", ["projects", "personal-management", "research", "learning"])
    answers.setdefault("tools", ["obsidian", "vscode"])
    privacy.setdefault("default_ai_access", "internal")
    privacy.setdefault("restricted_folders", ["03 - Personal", "09 - Attachments"])
    privacy.setdefault("business_ai_access", "internal")
    privacy.setdefault("personal_ai_access", "restricted")
    privacy.setdefault("linked_source_ai_access", "restricted")
    privacy.setdefault("exclude_sensitive_automatically", True)
    rhythm.setdefault("daily_review_time", "17:00")
    rhythm.setdefault("weekly_review_day", "Friday")
    rhythm.setdefault("monthly_review", True)
    rhythm.setdefault("daily_note_generation", True)
    rhythm.setdefault("inbox_processing", True)
    rhythm.setdefault("memory_maintenance", True)
    rhythm.setdefault("handoff_maintenance", True)
    rhythm.setdefault("git_review", False)
    rhythm.setdefault("project_health_checks", True)
    install.setdefault("mode", "standard")
    install.setdefault("target_directory", system["root_folder_name"])
    install.setdefault("initialize_git", False)
    install.setdefault("create_initial_commit", False)
    install.setdefault("include_samples", False)
    install.setdefault("include_gitkeep", True)
    install.setdefault("enable_windows_scripts", True)
    install.setdefault("enable_unix_scripts", True)
    install.setdefault("configure_external_integrations", False)
    install.setdefault("allow_overwrite", False)
    install.setdefault("backup_before_migration", True)
    install.setdefault("custom_modules", [])
    return answers


def validate_answers(answers: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    access = {"public", "internal", "restricted"}
    modes = {"lean", "standard", "business", "developer", "creator", "custom", "migration"}
    if answers["installation"]["mode"] not in modes:
        errors.append("installation.mode is invalid")
    for key in ("default_ai_access", "business_ai_access", "personal_ai_access", "linked_source_ai_access"):
        if answers["privacy"][key] not in access:
            errors.append(f"privacy.{key} is invalid")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", answers["rhythm"]["daily_review_time"]):
        errors.append("rhythm.daily_review_time must use HH:mm")
    try:
        dt.date.fromisoformat(answers["system"]["installation_date"])
    except ValueError:
        errors.append("system.installation_date must use YYYY-MM-DD")
    return errors


def flatten(answers: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for section in ("user", "system", "privacy", "rhythm"):
        for key, value in answers.get(section, {}).items():
            if isinstance(value, bool):
                merged[key] = str(value).lower()
            elif isinstance(value, list):
                merged[key] = ", ".join(map(str, value))
            else:
                merged[key] = str(value)
    merged.update({
        "system_name": str(answers["system"]["name"]),
        "system_short_name": str(answers["system"]["short_name"]),
        "system_description": str(answers["system"]["description"]),
    })
    return merged


def render(text: str, values: dict[str, str]) -> str:
    return TOKEN_RE.sub(lambda match: values.get(match.group(1), match.group(0)), text)


def enabled_modules(answers: dict[str, Any]) -> set[str]:
    mode = answers["installation"]["mode"]
    core = {"system", "projects", "inbox", "daily", "templates", "attachments", "archive"}
    if mode == "lean":
        return core
    if mode == "custom":
        return core | set(answers["installation"].get("custom_modules", []))
    return core | {"business", "personal", "hobbies", "knowledge"}


def selected_directories(manifest: dict[str, Any], modules: set[str]) -> list[str]:
    prefixes = {
        "system": "00 - System", "business": "01 - Business", "projects": "02 - Projects",
        "personal": "03 - Personal", "hobbies": "04 - Hobbies", "knowledge": "05 - Knowledge",
        "inbox": "06 - Inbox", "daily": "07 - Daily", "templates": "08 - Templates",
        "attachments": "09 - Attachments", "archive": "99 - Archive",
    }
    allowed = tuple(prefixes[module] for module in modules)
    return [item for item in manifest["standard_directories"] if item.startswith(allowed)]


def template_plan(modules: set[str]) -> list[tuple[Path, Path]]:
    plan: list[tuple[Path, Path]] = []
    for source in sorted((ROOT / "templates" / "root").iterdir()):
        if source.is_file():
            plan.append((source, Path(source.name)))
    mappings = {
        "system": ("system", Path("00 - System")),
        "business": ("business", Path("01 - Business")),
        "projects": ("projects", Path("02 - Projects")),
        "personal": ("personal", Path("03 - Personal")),
        "hobbies": ("hobbies", Path("04 - Hobbies")),
        "knowledge": ("knowledge", Path("05 - Knowledge")),
        "inbox": ("inbox", Path("06 - Inbox")),
        "daily": ("daily", Path("07 - Daily")),
        "attachments": ("attachments", Path("09 - Attachments")),
        "archive": ("archive", Path("99 - Archive")),
        "automations": ("automations", Path("00 - System") / "Automations"),
    }
    for module in modules | {"automations"}:
        if module not in mappings:
            continue
        source_name, destination = mappings[module]
        source_root = ROOT / "templates" / source_name
        for source in sorted(source_root.rglob("*")):
            if source.is_file():
                relative = source.relative_to(source_root)
                target = destination / relative
                if source_name == "system" and source.name == "ai-context-manifest.yaml":
                    target = Path("00 - System/Config/ai-context-manifest.yaml")
                plan.append((source, target))
    asset_mappings = {
        "projects": Path("08 - Templates/Project/Project-Folder-Template"),
        "daily": Path("08 - Templates/Reviews"),
    }
    for module, destination in asset_mappings.items():
        if module in modules:
            source_root = ROOT / "templates" / module
            for source in sorted(source_root.iterdir()):
                if source.is_file() and source.name not in {"Projects-MOC.md"}:
                    plan.append((source, destination / source.name))
    return plan


def safe_write(target: Path, content: str, allow_overwrite: bool, state: dict[str, Any]) -> None:
    ensure_safe_destination(Path(state["target_path"]), target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(content, encoding="utf-8")
        state["created_files"].append(str(target))
        return
    current = target.read_text(encoding="utf-8", errors="replace")
    if current == content:
        state["skipped_files"].append(str(target))
        return
    if allow_overwrite:
        target.write_text(content, encoding="utf-8")
        state["created_files"].append(str(target))
        return
    proposal = target.with_name(target.stem + ".new" + target.suffix) if target.suffix else target.with_name(target.name + ".new")
    proposal.write_text(content, encoding="utf-8")
    state["conflicts"].append({"existing": str(target), "proposed": str(proposal)})


def backup_existing(target: Path) -> Path | None:
    existing = [path for path in target.rglob("*") if path.is_file() and "00 - System/Installation/backups" not in path.as_posix()]
    if not existing:
        return None
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target / "00 - System" / "Installation" / "backups" / stamp
    for source in existing:
        relative = source.relative_to(target)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return backup


def validate_install(target: Path) -> dict[str, Any]:
    required_files = ["README.md", "AGENTS.md", "CLAUDE.md", "CODEX.md", "memory.md", "handoff.md", "CONTEXT-POLICY.md", "TOKEN-OPTIMIZATION.md"]
    required_dirs = ["00 - System", "02 - Projects", "06 - Inbox", "07 - Daily", "08 - Templates", "09 - Attachments", "99 - Archive"]
    errors = [f"Missing file: {name}" for name in required_files if not (target / name).is_file()]
    errors += [f"Missing directory: {name}" for name in required_dirs if not (target / name).is_dir()]
    unresolved: list[str] = []
    for path in target.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".json"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if TOKEN_RE.search(text):
                unresolved.append(str(path.relative_to(target)))
    if unresolved:
        errors.append("Unresolved template tokens: " + ", ".join(unresolved))
    agents = (target / "AGENTS.md").read_text(encoding="utf-8", errors="replace") if (target / "AGENTS.md").exists() else ""
    for adapter in ("CLAUDE.md", "CODEX.md"):
        path = target / adapter
        if path.exists() and len(path.read_text(encoding="utf-8").splitlines()) > 40:
            errors.append(f"Adapter is not thin: {adapter}")
    if "AGENTS.md" not in agents or "Default Exclusions" not in agents:
        errors.append("Canonical router contract is incomplete")
    registry = target / "00 - System/Automations/AUTOMATION-REGISTRY.md"
    if not registry.exists():
        errors.append("Automation registry is missing")
    elif "Status: Not configured" not in registry.read_text(encoding="utf-8"):
        errors.append("External automation status is not explicit")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "unresolved_tokens": unresolved}


def privacy_scan(target: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for path in target.rglob("*"):
        if not path.is_file() or any(part in {".git", "backups"} for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append({"path": str(path.relative_to(target)), "finding": "Potential secret-like value"})
                break
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def report_markdown(answers: dict[str, Any], state: dict[str, Any], validation: dict[str, Any], privacy: dict[str, Any]) -> str:
    return f"""# Installation Report

## Result

- Installer version: {VERSION}
- Mode: {answers['installation']['mode']}
- Target: {state['target_path']}
- Created: {len(state['created_files'])}
- Skipped: {len(state['skipped_files'])}
- Conflicts: {len(state['conflicts'])}
- Validation: {validation['status']}
- Privacy scan: {privacy['status']}

## First-Day Checklist

- [ ] Review `me.md` and remove unwanted profile fields.
- [ ] Review and approve or revise privacy classifications.
- [ ] Review `memory.md` and `handoff.md`; both start as drafts.
- [ ] Open `00 - System/Home.md` in Obsidian.
- [ ] Process one synthetic or real Inbox item.
- [ ] Review automation definitions; external integrations remain unconfigured.
- [ ] Initialize or commit Git only after reviewing generated content.
- [ ] Keep any remote private unless every personal, business, project, daily, and attachment file is approved for publication.

## Conflicts

{json.dumps(state['conflicts'], indent=2)}

## Validation Findings

{json.dumps(validation['errors'], indent=2)}

## Exact Next Action

Review the first-day checklist, then change generated context from draft only after human approval.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a Knowledge OS from starter-kit templates.")
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--mode")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--migration", action="store_true")
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args()
    answer_path = (args.answers or (ROOT / "installer/answers.example.json")).resolve()
    answers = defaults(load_json(answer_path))
    if args.mode:
        answers["installation"]["mode"] = args.mode
    if args.migration:
        answers["installation"]["mode"] = "migration"
    if args.target:
        answers["installation"]["target_directory"] = str(args.target)
    errors = validate_answers(answers)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    raw_target = Path(answers["installation"]["target_directory"])
    target = (raw_target if raw_target.is_absolute() else ROOT / raw_target).resolve()
    validate_target(
        target,
        migration=answers["installation"]["mode"] == "migration",
        resume=args.resume,
        dry_run=args.dry_run,
    )
    protected: list[Path] = []
    local_config = ROOT / "installer/local-config.json"
    if local_config.exists():
        protected += [Path(item).resolve() for item in load_json(local_config).get("protected_paths", [])]
        protected += [Path(item).resolve() for item in load_json(local_config).get("reference_paths", [])]
    for item in protected:
        if target == item or item in target.parents:
            raise ValueError(f"Unsafe target resolves inside protected path: {target}")
    modules = enabled_modules(answers)
    manifest = load_json(ROOT / "installer/structure.manifest.json")
    directories = selected_directories(manifest, modules)
    plan = template_plan(modules)
    dry_manifest = {
        "installer_version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "target": str(target),
        "mode": answers["installation"]["mode"],
        "directories": directories,
        "files": [str(destination) for _, destination in plan],
    }
    if args.dry_run:
        output = ROOT / "build/dry-run-manifest.json"
        write_json(output, dry_manifest)
        print(f"Dry run complete: {output}")
        return 0
    state_path = target / "00 - System/Installation/installer-state.json"
    if args.resume and not state_path.exists():
        raise ValueError(f"Resume requested but installer state was not found: {state_path}")
    if args.resume and state_path.exists():
        state = load_json(state_path)
        if Path(state["target_path"]).resolve() != target:
            raise ValueError("Resume state target does not match requested target")
    else:
        state = {
            "installer_version": VERSION,
            "start_time": dt.datetime.now(dt.timezone.utc).isoformat(),
            "last_completed_phase": 0,
            "selected_mode": answers["installation"]["mode"],
            "target_path": str(target),
            "answer_file": str(answer_path),
            "created_files": [], "skipped_files": [], "conflicts": [], "errors": [],
            "validation_results": {}, "completion_status": "in-progress",
        }
    target.mkdir(parents=True, exist_ok=True)
    if answers["installation"]["mode"] == "migration" and answers["installation"]["backup_before_migration"]:
        backup = backup_existing(target)
        if backup:
            state["backup_path"] = str(backup)
    for relative in directories:
        directory = target / relative
        ensure_safe_destination(target, directory)
        directory.mkdir(parents=True, exist_ok=True)
        if answers["installation"]["include_gitkeep"]:
            keep = directory / ".gitkeep"
            if not keep.exists():
                keep.write_text("", encoding="utf-8")
                state["created_files"].append(str(keep))
    state["last_completed_phase"] = 1
    values = flatten(answers)
    allow = args.allow_overwrite or bool(answers["installation"]["allow_overwrite"])
    for source, relative in plan:
        safe_write(target / relative, render(source.read_text(encoding="utf-8"), values), allow, state)
    state["last_completed_phase"] = 2
    if answers["installation"]["include_samples"]:
        samples = {
            ROOT / "examples/sample-project": target / "02 - Projects/Incubating/Sample Project",
            ROOT / "examples/sample-company": target / "01 - Business/Companies/Example Company",
        }
        for source_root, destination_root in samples.items():
            if destination_root.parts[-3].startswith("01") and "business" not in modules:
                continue
            for source in source_root.rglob("*"):
                if source.is_file():
                    safe_write(destination_root / source.relative_to(source_root), source.read_text(encoding="utf-8"), allow, state)
        safe_write(target / "07 - Daily/sample-daily-workflow.md", (ROOT / "examples/sample-daily-workflow.md").read_text(encoding="utf-8"), allow, state)
    state["last_completed_phase"] = 3
    if answers["installation"]["initialize_git"] and not (target / ".git").exists():
        subprocess.run(["git", "init", "-b", "main"], cwd=target, check=True)
    if answers["installation"]["create_initial_commit"] and not (target / ".git").exists():
        raise ValueError("create_initial_commit requires initialize_git or an existing Git repository")
    state["last_completed_phase"] = 4
    validation = validate_install(target)
    privacy = privacy_scan(target)
    state["validation_results"] = {"validation": validation, "privacy": privacy}
    state["last_completed_phase"] = 5
    state["completion_status"] = "complete" if validation["status"] == privacy["status"] == "PASS" else "failed"
    report = report_markdown(answers, state, validation, privacy)
    report_path = target / "00 - System/Installation/INSTALLATION-REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    write_json(state_path, state)
    if answers["installation"]["create_initial_commit"]:
        subprocess.run(["git", "add", "--all"], cwd=target, check=True)
        subprocess.run(["git", "commit", "-m", "Initialize Knowledge OS"], cwd=target, check=True)
    print(f"Installation {state['completion_status']}: {target}")
    return 0 if state["completion_status"] == "complete" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(3)
