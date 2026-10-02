#!/usr/bin/env python3
"""Dependency-free KOS Power-Up domain logic: a constrained YAML-lite reader plus
registry/manifest validation and read-only discovery.

The parser here intentionally supports only the subset of YAML that KOS
generates and that Power-Up authors are asked to write: block mappings, block
sequences (including sequences of mappings), flow lists (``[a, b]``/``[]``),
quoted or bare scalars, and ``#`` comments. It does not support anchors,
tags, multi-line scalars, or flow mappings. That scope is sufficient for
``registry.yaml``, ``settings.yaml``, and Power-Up ``manifest.yaml`` files and
keeps the starter kit dependency-free.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from safety import Blocked, link, safe

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class YamlLiteError(ValueError):
    """Raised when text falls outside the supported YAML-lite subset."""


def _strip_comment(line: str) -> str:
    result: list[str] = []
    in_quote: str | None = None
    for ch in line:
        if in_quote:
            result.append(ch)
            if ch == in_quote:
                in_quote = None
            continue
        if ch in "\"'":
            in_quote = ch
            result.append(ch)
            continue
        if ch == "#":
            break
        result.append(ch)
    return "".join(result).rstrip()


def _split_flow(inner: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current = ""
    in_quote: str | None = None
    for ch in inner:
        if in_quote:
            current += ch
            if ch == in_quote:
                in_quote = None
            continue
        if ch in "\"'":
            in_quote = ch
            current += ch
            continue
        if ch in "[{":
            depth += 1
            current += ch
            continue
        if ch in "]}":
            depth -= 1
            current += ch
            continue
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


def _parse_scalar(token: str) -> Any:
    token = token.strip()
    if token in ("", "~") or token.lower() == "null":
        return None
    if token.lower() == "true":
        return True
    if token.lower() == "false":
        return False
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    if token == "[]":
        return []
    if token == "{}":
        return {}
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        return [] if not inner else [_parse_scalar(part) for part in _split_flow(inner)]
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"-?\d+\.\d+", token):
        return float(token)
    return token


class _Cursor:
    def __init__(self, items: list[tuple[int, str]]) -> None:
        self.items = items
        self.pos = 0

    def peek(self) -> tuple[int, str] | None:
        return self.items[self.pos] if self.pos < len(self.items) else None

    def next(self) -> tuple[int, str]:
        item = self.items[self.pos]
        self.pos += 1
        return item


def _parse_nodes(cursor: _Cursor, min_indent: int) -> Any:
    peek = cursor.peek()
    if peek is None or peek[0] < min_indent:
        return None
    indent, content = peek
    if content == "-" or content.startswith("- "):
        return _parse_seq(cursor, indent)
    return _parse_map(cursor, indent)


def _parse_map(cursor: _Cursor, indent: int, first_key: str | None = None, first_value: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if first_key is not None:
        result[first_key] = first_value
    while True:
        peek = cursor.peek()
        if peek is None or peek[0] != indent:
            break
        _, content = peek
        if content == "-" or content.startswith("- "):
            break
        if ":" not in content:
            break
        key, _, rest = content.partition(":")
        key = key.strip().strip("\"'")
        if not _KEY_RE.match(key):
            break
        cursor.next()
        rest = rest.strip()
        if rest == "":
            value = _parse_nodes(cursor, indent + 1)
            result[key] = value if value is not None else {}
        else:
            result[key] = _parse_scalar(rest)
    return result


def _parse_seq(cursor: _Cursor, indent: int) -> list[Any]:
    result: list[Any] = []
    while True:
        peek = cursor.peek()
        if peek is None or peek[0] != indent or not (peek[1] == "-" or peek[1].startswith("- ")):
            break
        _, content = cursor.next()
        rest = "" if content == "-" else content[2:]
        if rest == "":
            result.append(_parse_nodes(cursor, indent + 1))
            continue
        if ":" in rest:
            key, sep, value_part = rest.partition(":")
            candidate_key = key.strip().strip("\"'")
            if sep and _KEY_RE.match(candidate_key):
                value_part = value_part.strip()
                first_value = _parse_scalar(value_part) if value_part else _parse_nodes(cursor, indent + 3)
                result.append(_parse_map(cursor, indent + 2, first_key=candidate_key, first_value=first_value))
                continue
        result.append(_parse_scalar(rest))
    return result


def load_yaml_lite(text: str) -> Any:
    """Parse the constrained YAML-lite subset described in this module's docstring."""
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw)
        if stripped.strip() in ("", "---"):
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip()))
    cursor = _Cursor(lines)
    first = cursor.peek()
    if first is None:
        return {}
    return _parse_nodes(cursor, first[0])


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or text in ("true", "false", "null") or re.search(r"[:#\[\]{}]|^\s|\s$", text):
        return json.dumps(text)
    return text


def format_registry_entry(entry: dict[str, Any]) -> str:
    """Render a single registry entry as an indented YAML-lite block-sequence item."""
    order = [
        "id", "name", "version", "status", "installation_mode", "install_path",
        "manifest", "initialized_targets", "installed_at", "updated_at",
    ]
    lines: list[str] = []
    first = True
    for key in order:
        if key not in entry:
            continue
        prefix = "  - " if first else "    "
        first = False
        value = entry[key]
        if key == "initialized_targets":
            items = value or []
            if not items:
                lines.append(f"{prefix}{key}: []")
            else:
                lines.append(f"{prefix}{key}:")
                lines.extend(f"      - {_yaml_scalar(item)}" for item in items)
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return "\n".join(lines) + "\n"


def register_power_up(registry_path: Path, entry: dict[str, Any]) -> None:
    """Append ``entry`` to ``registry.yaml``. Never overwrites an existing id."""
    text = registry_path.read_text(encoding="utf-8")
    registry = load_yaml_lite(text)
    existing_ids = {item.get("id") for item in (registry.get("power_ups") or []) if isinstance(item, dict)}
    if entry["id"] in existing_ids:
        raise ValueError(f"Power-Up '{entry['id']}' is already registered; registration does not overwrite entries")
    block = format_registry_entry(entry)
    match = re.search(r"(?m)^power_ups:\s*\[\]\s*$", text)
    if match:
        # Manual slicing (not re.sub's replacement string) avoids re.sub treating
        # a literal backslash in `block` as a backreference escape.
        new_text = text[: match.start()] + "power_ups:\n" + block.rstrip("\n") + text[match.end() :]
    else:
        new_text = text.rstrip("\n") + "\n" + block
    registry_path.write_text(new_text, encoding="utf-8")


def _semver_tuple(value: str) -> tuple[int, int, int]:
    core = str(value).split("-")[0].split("+")[0]
    a, b, c = core.split(".")[:3]
    return int(a), int(b), int(c)


def validate_registry_dict(registry: Any) -> tuple[list[str], list[str]]:
    """Validate a parsed ``registry.yaml``. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(registry, dict):
        return ["registry.yaml did not parse to a mapping"], warnings
    if not registry.get("schema_version"):
        errors.append("registry.schema_version is required")
    entries = registry.get("power_ups")
    if entries is None:
        errors.append("registry.power_ups must be present (use [] when empty)")
        entries = []
    if not isinstance(entries, list):
        errors.append("registry.power_ups must be a list")
        entries = []
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("registry entry is not a mapping")
            continue
        entry_id = entry.get("id")
        if not entry_id or not ID_RE.match(str(entry_id)):
            errors.append(f"registry entry has an invalid id: {entry_id!r}")
        elif entry_id in seen_ids:
            errors.append(f"duplicate Power-Up id in registry: {entry_id}")
        else:
            seen_ids.add(str(entry_id))
        version = entry.get("version")
        if not version or not SEMVER_RE.match(str(version)):
            errors.append(f"registry entry '{entry_id}' has an invalid version: {version!r}")
        if entry.get("status") not in ("enabled", "disabled"):
            errors.append(f"registry entry '{entry_id}' has an invalid status: {entry.get('status')!r}")
        if entry.get("installation_mode") not in ("external", "embedded"):
            errors.append(f"registry entry '{entry_id}' has an invalid installation_mode: {entry.get('installation_mode')!r}")
        if not entry.get("manifest"):
            errors.append(f"registry entry '{entry_id}' is missing a manifest path")
        if not entry.get("install_path"):
            warnings.append(f"registry entry '{entry_id}' has no install_path recorded")
    return errors, warnings


def validate_manifest_dict(manifest: Any, kos_version: str | None = None) -> tuple[list[str], list[str]]:
    """Validate a parsed Power-Up ``manifest.yaml``. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest.yaml did not parse to a mapping"], warnings
    if not manifest.get("schema_version"):
        errors.append("manifest.schema_version is required")
    manifest_id = manifest.get("id")
    if not manifest_id or not ID_RE.match(str(manifest_id)):
        errors.append("manifest.id must be a lowercase, hyphenated identifier")
    version = manifest.get("version")
    if not version or not SEMVER_RE.match(str(version)):
        errors.append("manifest.version must be a semantic version (MAJOR.MINOR.PATCH)")
    compat = manifest.get("kos_compatibility") or {}
    minimum = compat.get("minimum_version")
    if not minimum or not SEMVER_RE.match(str(minimum)):
        errors.append("manifest.kos_compatibility.minimum_version must be a semantic version")
    maximum = compat.get("maximum_version")
    if maximum not in (None, "null") and not SEMVER_RE.match(str(maximum)):
        errors.append("manifest.kos_compatibility.maximum_version must be null or a semantic version")
    if kos_version and SEMVER_RE.match(str(kos_version)) and minimum and SEMVER_RE.match(str(minimum)):
        if _semver_tuple(kos_version) < _semver_tuple(minimum):
            errors.append(f"installed KOS {kos_version} is older than the Power-Up's minimum {minimum}")
        if maximum and SEMVER_RE.match(str(maximum)) and _semver_tuple(kos_version) > _semver_tuple(maximum):
            errors.append(f"installed KOS {kos_version} is newer than the Power-Up's maximum {maximum}")
    installation = manifest.get("installation") or {}
    supported_modes = installation.get("supported_modes") or []
    if not supported_modes:
        errors.append("manifest.installation.supported_modes must declare at least one mode")
    for mode in supported_modes:
        if mode not in ("external", "embedded"):
            errors.append(f"manifest.installation.supported_modes has an unsupported mode: {mode}")
    default_mode = installation.get("default_mode")
    if default_mode and supported_modes and default_mode not in supported_modes:
        errors.append("manifest.installation.default_mode must be one of supported_modes")
    agents = manifest.get("agents") or {}
    if not agents.get("canonical_skill"):
        warnings.append("manifest.agents.canonical_skill is not declared")
    permissions = manifest.get("permissions")
    if not isinstance(permissions, dict) or "read" not in permissions or "write" not in permissions:
        errors.append("manifest.permissions must declare read and write locations")
    else:
        canonical_writes = permissions.get("canonical_kos_writes") or {}
        if canonical_writes.get("allowed") and not canonical_writes.get("requires_explicit_approval", True):
            errors.append("manifest.permissions.canonical_kos_writes.allowed requires requires_explicit_approval: true")
    lifecycle = manifest.get("lifecycle") or {}
    for command in ("install_command", "initialize_command", "upgrade_command", "uninstall_command"):
        if not lifecycle.get(command):
            warnings.append(f"manifest.lifecycle.{command} is not declared")
    return errors, warnings


def discover(power_ups_home: Path, registered_ids: set[str], kos_version: str | None = None) -> list[dict[str, Any]]:
    """Scan ``power_ups_home`` for directories containing ``manifest.yaml``.

    Never executes anything found in a candidate directory; only reads and
    validates ``manifest.yaml`` and checks referenced lifecycle files exist.
    """
    candidates: list[dict[str, Any]] = []
    if not power_ups_home or link(power_ups_home) or not power_ups_home.is_dir():
        return candidates
    seen_ids: dict[str, str] = {}
    for entry in sorted(power_ups_home.iterdir()):
        if link(entry) or not entry.is_dir():
            continue
        manifest_path = entry / "manifest.yaml"
        if link(manifest_path) or not manifest_path.is_file():
            continue
        report: dict[str, Any] = {"path": str(entry), "manifest_path": str(manifest_path)}
        try:
            manifest = load_yaml_lite(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - surfaced as a discovery finding, not raised
            report.update(status="ERROR", errors=[f"manifest.yaml failed to parse: {exc}"], warnings=[], manifest=None, id=None, version=None)
            candidates.append(report)
            continue
        errors, warnings = validate_manifest_dict(manifest, kos_version)
        power_up_id = manifest.get("id") if isinstance(manifest, dict) else None
        lifecycle = (manifest.get("lifecycle") or {}) if isinstance(manifest, dict) else {}
        for command_name, command_path in lifecycle.items():
            if command_path:
                try:
                    command_file = safe(entry, str(command_path))
                    if not command_file.is_file():
                        warnings.append(f"lifecycle.{command_name} points to a missing file: {command_path}")
                except Blocked:
                    errors.append(f"lifecycle.{command_name} has an unsafe path")
        if power_up_id and power_up_id in seen_ids:
            errors.append(f"duplicate Power-Up id discovered at '{entry}' and '{seen_ids[power_up_id]}'")
        elif power_up_id:
            seen_ids[power_up_id] = str(entry)
        if power_up_id and power_up_id in registered_ids:
            warnings.append(f"'{power_up_id}' is already registered; discovery will not overwrite it")
        report.update(
            manifest=manifest,
            id=power_up_id,
            version=manifest.get("version") if isinstance(manifest, dict) else None,
            permissions=manifest.get("permissions") if isinstance(manifest, dict) else None,
            errors=errors,
            warnings=warnings,
            status="ERROR" if errors else ("WARNING" if warnings else "PASS"),
        )
        candidates.append(report)
    return candidates
