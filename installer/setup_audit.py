"""Read-only preservation and link checks for Community setup rehearsals."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import csv
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote

from contracts import check, compatible, supports_edition
from engine import (CAPABILITIES, LINK_SCAN_MAX_BYTES, LINK_SCAN_MAX_FILES,
                    LINK_SCAN_MAX_MARKDOWN, LINK_SCAN_MAX_REFERENCES, _link_index)
from packages import GENERIC, HOMES, REGISTRIES, verify_installed
from safety import Blocked, ROOT, STATE, digest, encoded, inventory, json_read, safe


PACKAGE_REGISTRIES = (*REGISTRIES.values(), GENERIC)
# Wiki display aliases are stripped separately. For Markdown accept angle-wrapped
# paths, balanced parentheses one level deep, and optional quoted link titles.
REFERENCE = re.compile(
    r'(?<!\\)!?\[\[([^\]\n]+)\]\]|(?<!\\)!?\[[^\]\n]*\]\(\s*'
    r'(<[^>\n]+>|(?:\\.|[^()\s\\]|\((?:\\.|[^()\\\n])*\))+)(?:\s+["\'][^)\n]*["\'])?\s*\)')
FENCE = re.compile(r"^ {0,3}(\x60{3,}|~{3,})(.*)$")
INLINE_CODE = re.compile(r"(\x60+)(?!\x60).*?(?<!\x60)\1(?!\x60)")
REMOTE = re.compile(r"^[a-zA-Z][a-zA-Z\d+.-]*:|^//")
CHANGING = {"CREATE", "UPDATE_SAFE", "UPDATE_APPROVED", "MERGE", "REMOVE"}


@dataclass
class Audit:
    files: dict
    components: dict
    protected: dict
    settings: dict
    capabilities: dict
    packages: dict
    portable: dict
    issues: set
    warnings: set
    links: dict
    markdown_count: int


def _aliases(lines):
    aliases = []
    collecting = False
    for row in lines:
        match = re.match(r"^(?:alias|aliases):\s*(.*)$", row, re.I)
        if match:
            value = match[1].strip()
            collecting = not value
            if value.startswith("[") and value.endswith("]"):
                aliases.extend(next(csv.reader([value[1:-1]], skipinitialspace=True)))
            elif value:
                aliases.append(value)
        elif collecting and re.match(r"^\s*-\s+", row):
            aliases.append(re.sub(r"^\s*-\s+", "", row))
        else:
            collecting = False
    return [value.strip().strip("\"'").casefold() for value in aliases if value.strip()]


def _slug(heading):
    return re.sub(r"[^\w -]", "", heading.casefold()).replace(" ", "-")


def _note(path):
    if path.stat().st_size > LINK_SCAN_MAX_BYTES:
        raise Blocked("LINK_SCAN_LIMIT: " + path.name)
    try:
        rows = path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        raise Blocked("LINK_SCAN_ENCODING: " + path.name) from None
    aliases, anchors, refs, warnings = [], defaultdict(set), [], set()
    start = 0
    if rows and rows[0].strip() == "---":
        stop = next((i for i in range(1, len(rows)) if rows[i].strip() in {"---", "..."}), None)
        if stop is not None:
            aliases = _aliases(rows[1:stop])
            start = stop + 1
    fence = None
    occurrences = Counter()
    previous_text = ""
    for i in range(start, len(rows)):
        row = rows[i]
        marker = FENCE.match(row)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            previous_text = ""
            fence = marker[1]
            if marker[2].strip().casefold() in {"dataview", "dataviewjs", "tasks"}:
                warnings.add("dynamic plugin references")
            continue
        # Preserve inline code text in headings (it is part of the rendered ID).
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+)$", row)
        setext = bool(previous_text.strip() and re.fullmatch(r" {0,3}(?:=+|-+)\s*", row))
        if heading or setext:
            label = (heading[1] if heading else previous_text).strip()
            label = re.sub(r"\s+#+\s*$", "", label).replace(chr(96), "").strip().casefold()
            slug = _slug(label)
            sequence = occurrences[slug]
            occurrences[slug] += 1
            anchor_id = slug if sequence == 0 else f"{slug}-{sequence}"
            anchors[anchor_id].add(anchor_id)
            anchors[label].add(anchor_id)
        previous_text = "" if heading or setext else row
        row = INLINE_CODE.sub("", row)
        block = re.search(r"(?:^|\s)\^([\w-]+)\s*$", row)
        if block:
            key = "^" + block[1].casefold()
            count = len(anchors[key])
            anchors[key].add(key if count == 0 else f"{key}~{count}")
        if re.search(r"(?<!\\)\[[^\]]+\]\[[^\]]*\]", row) or re.search(r"<(?:a|img)\s", row, re.I):
            warnings.add("reference-style Markdown or HTML links")
        for match in REFERENCE.finditer(row):
            kind = "wiki" if match[1] is not None else "markdown"
            dest = match[1].split("|", 1)[0].strip() if kind == "wiki" else match[2].strip("<>")
            dest = re.sub(r"\\([()# ])", r"\1", dest)
            if dest and not REMOTE.match(dest):
                refs.append((kind, dest, i + 1))
    return aliases, anchors, refs, warnings


def _destinations(source, kind, dest, index, aliases, anchors, linked_paths):
    path, _, fragment = dest.partition("#")
    path = unquote(path.split("?", 1)[0] if kind == "markdown" else path)
    fragment = unquote(fragment).strip().casefold()
    if not path:
        targets = [source]
    elif kind == "wiki" and "/" not in path:
        name = path[:-3] if path.casefold().endswith(".md") else path
        targets = index[1].get(name.casefold()) or aliases.get(name.casefold(), [])
    else:
        directory = posixpath.dirname(source)
        if path.startswith("/") or kind == "wiki" and not path.startswith(("./", "../")):
            directory = ""
        rel = posixpath.normpath(posixpath.join(directory, path.lstrip("/")))
        if any(parent.as_posix().casefold() in linked_paths for parent in PurePosixPath(rel).parents):
            return "unverified", (rel,)
        targets = index[0].get(rel.casefold(), [])
        if not targets and not PurePosixPath(rel).suffix:
            targets = index[0].get((rel + ".md").casefold(), [])
    if len(targets) != 1:
        return ("ambiguous" if targets else "missing", tuple(sorted(targets)))
    target = targets[0]
    if target.casefold() in linked_paths:
        return "unverified", (target,)
    if not fragment:
        return "resolved", (target,)
    if not target.casefold().endswith(".md") or "#" in fragment:
        return "unverified", (target,)
    hits = anchors.get(target, {}).get(fragment, set())
    result = tuple(sorted(target + "#" + anchor for anchor in hits))
    return ("resolved" if len(hits) == 1 else "ambiguous" if hits else "missing"), result


def _link_snapshot(vault, files, symlinks, warnings):
    if len(files) + len(symlinks) > LINK_SCAN_MAX_FILES:
        raise Blocked("LINK_SCAN_LIMIT")
    index = _link_index(files.keys() | symlinks.keys())
    linked_paths = {rel.casefold() for rel in symlinks}
    aliases, anchors, references = defaultdict(list), {}, {}
    count = 0
    for rel in files:
        if not rel.casefold().endswith(".md"):
            continue
        if len(anchors) >= LINK_SCAN_MAX_MARKDOWN:
            raise Blocked("LINK_SCAN_LIMIT")
        names, anchors[rel], references[rel], limitations = _note(safe(vault, rel))
        warnings.update(f"Unverified {limitation} in {rel}" for limitation in limitations)
        for name in set(names):
            aliases[name].append(rel)
        count += len(references[rel])
        if count > LINK_SCAN_MAX_REFERENCES:
            raise Blocked("LINK_SCAN_LIMIT")
    links = {}
    for source, refs in references.items():
        seen = Counter()
        for kind, dest, line in refs:
            key = (source, kind, dest)
            seen[key] += 1
            status, targets = _destinations(source, kind, dest, index, aliases, anchors, linked_paths)
            links[(*key, seen[key])] = (status, targets, line)
    return links, len(anchors)


def _portable_ids(vault, rel, warnings):
    leaf = PurePosixPath(rel)
    ids = {leaf.parent.name.casefold()} if leaf.parent.name else set()
    declared = None
    path = safe(vault, rel)
    if path.stat().st_size <= LINK_SCAN_MAX_BYTES:
        try:
            if leaf.name.casefold() == "module.json":
                metadata = json_read(path)
                declared = metadata.get("id") if isinstance(metadata, dict) else None
            else:
                rows = path.read_text(encoding="utf-8-sig").splitlines()
                if rows and rows[0].strip() == "---":
                    for row in rows[1:]:
                        if row.strip() in {"---", "..."}:
                            break
                        field = re.fullmatch(r"name:\s*(['\"]?)([\w.-]+)\1\s*(?:#.*)?", row)
                        if field:
                            declared = field[2]
                            break
        except (ValueError, UnicodeError):
            pass
    if isinstance(declared, str) and re.fullmatch(r"[\w.-]+", declared):
        ids.add(declared.casefold())
    else:
        warnings.add("Portable extension declared identity unverified: " + rel)
    return frozenset(ids)


def _extension_snapshot(vault, state, files, issues, warnings):
    packages, records, owned_skill_paths = {}, {}, set()
    project_versions = set()
    for rel in files:
        if re.fullmatch(r"02 - Projects/Active/[^/]+/power-ups\.json", rel):
            activation = json_read(safe(vault, rel))
            check("project-activation", activation)
            for name, choice in activation["packages"].items():
                if "version" in choice:
                    project_versions.add((name, choice["version"]))
    for registry in PACKAGE_REGISTRIES:
        if registry not in files:
            continue
        data = json_read(safe(vault, registry))
        check("registry", data)
        for name, entry in data["packages"].items():
            if name.casefold() in records:
                issues.add("PACKAGE_ID_COLLISION: " + name)
            records[name.casefold()] = entry
            packages[(registry, name)] = digest(encoded(entry))
            for ver, record in entry["versions"].items():
                try:
                    manifest = record["manifest"]
                    if manifest["id"] != name or manifest["version"] != ver:
                        raise Blocked("PACKAGE_IDENTITY_MISMATCH")
                    verify_installed(vault, record)
                    owned_skill_paths.add(record["path"] + "/SKILL.md")
                    if ver == entry["activeVersion"] or (name, ver) in project_versions:
                        if not compatible(manifest["compatibility"], state["kosContractVersion"]):
                            raise Blocked("HOST_CONTRACT_INCOMPATIBLE")
                        if not supports_edition(manifest["supportedEditions"], state["edition"]):
                            raise Blocked("HOST_EDITION_INCOMPATIBLE")
                        if set(manifest.get("requiredCapabilities", [])) - set(state["capabilities"]):
                            raise Blocked("REQUIRED_CAPABILITY_MISSING")
                except (Blocked, KeyError, TypeError, FileNotFoundError):
                    issues.add(f"PACKAGE_INTEGRITY_OR_COMPATIBILITY: {registry} / {name} @ {ver}")
            if entry["activeVersion"] not in entry["versions"]:
                issues.add("PACKAGE_ACTIVE_VERSION_MISSING: " + name)
    for name, ver in project_versions:
        if ver not in records.get(name.casefold(), {}).get("versions", {}):
            issues.add(f"PROJECT_PACKAGE_VERSION_MISSING: {name} @ {ver}")
    for name, entry in records.items():
        if not entry["enabled"]:
            continue
        active = entry["versions"].get(entry["activeVersion"], {})
        for dependency, version in active.get("manifest", {}).get("dependencies", {}).items():
            other = records.get(dependency.casefold(), {})
            if not other.get("enabled") or other.get("activeVersion") != version:
                issues.add(f"PACKAGE_DEPENDENCY_UNAVAILABLE: {name} requires {dependency} @ {version}")
    # A loose portable Skill has no package receipt. Keep its path, bytes and
    # discovery ID; execution or API compatibility cannot be inferred from it.
    portable = {}
    for rel in files:
        leaf = PurePosixPath(rel)
        if leaf.name.casefold() not in {"skill.md", "module.json"} or rel in owned_skill_paths:
            continue
        ids = _portable_ids(vault, rel, warnings)
        portable[rel] = ids
        for name in ids.intersection(records):
            issues.add(f"PACKAGE_ID_COLLISION: {name} at {rel}")
        warnings.add("Unversioned extension compatibility unverified: " + rel)
    return packages, portable


def capture_audit(vault: Path) -> Audit:
    """Capture hashes, semantic extension state and local Markdown resolution."""
    entries = inventory(vault)
    files = {e["path"]: e["hash"] for e in entries if e["kind"] == "file"}
    state = json_read(safe(vault, STATE)) if STATE in files else {}
    components = state.get("components", {})
    released = {a["path"]: a.get("releasedDefaults", {}) for a in
                json_read(ROOT / "installer/assets.json")["assets"]}
    protected = {}
    for rel, file_hash in files.items():
        if rel in {STATE, CAPABILITIES}:
            continue
        record = components.get(rel, {})
        pristine = file_hash == record.get("installedHash")
        owner = record.get("ownership")
        managed = owner in {"managed", "managed-customizable", "generated"}
        if pristine and (managed or file_hash == released.get(rel, {}).get(record.get("sourceVersion"))):
            continue
        protected[rel] = file_hash
    link_signatures = {}
    for e in entries:
        if e["kind"] == "link":
            link_signatures[e["path"]] = ("link", os.readlink(vault / e["path"]))
    protected.update(link_signatures)
    caps = json_read(safe(vault, CAPABILITIES)) if CAPABILITIES in files else {"capabilities": []}
    warnings, issues = set(), set()
    capability_paths = {}
    for cap in caps["capabilities"]:
        if cap["id"] in capability_paths:
            issues.add("CAPABILITY_ID_COLLISION: " + cap["id"])
        paths = set(cap["paths"])
        capability_paths[cap["id"]] = {
            "paths": paths,
            "available": paths.intersection(files),
            "metadata": {key: digest(encoded(value)) for key, value in cap.items()
                         if key not in {"id", "version", "paths"}},
        }
    settings = {k: state[k] for k in ("providers", "profile", "privacy", "customModules", "installationDate") if k in state}
    packages, portable = _extension_snapshot(vault, state, files, issues, warnings)
    links, count = _link_snapshot(vault, files, link_signatures, warnings)
    inventory_hashes = {**files, **link_signatures}
    return Audit(inventory_hashes, components, protected, settings, capability_paths, packages,
                 portable, issues, warnings, links, count)


def _historical_replacements(plan, snapshot):
    # The verified release recognizes exact rendered 1.1.0 template hashes
    # even though that installer did not write per-file ownership receipts.
    if not plan or plan.get("targetType") != "legacy-kos" or plan.get("previousVersion") != "1.1.0":
        return {}
    return {item["path"]: item["desiredHash"] for item in plan["items"]
            if item.get("classification") == "OLDER_MANAGED" and item.get("action") == "UPDATE_SAFE"
            and item.get("currentHash") and snapshot.files.get(item["path"]) == item["currentHash"]}


def plan_guard(vault: Path, plan: dict, snapshot: Audit) -> list[str]:
    """Return occupied identity/path findings before authorizing an upgrade."""
    blockers = set(snapshot.issues)
    historical = _historical_replacements(plan, snapshot)
    ids = {name.casefold() for _, name in snapshot.packages}.union(*snapshot.portable.values())
    occupied = defaultdict(set)
    for existing in snapshot.files:
        occupied[existing.casefold()].add(existing)
    for item in plan.get("items", []):
        rel = item["path"]
        action = item["action"]
        if occupied.get(rel.casefold(), set()) - {rel}:
            blockers.add("OCCUPIED_COMPONENT_PATH: " + rel)
        for home in HOMES.values():
            prefix = home + "/"
            if rel.startswith(prefix) and action in {"CREATE", "CREATE_DIRECTORY"}:
                name = rel[len(prefix):].split("/", 1)[0].casefold()
                if name in ids:
                    blockers.add(f"PACKAGE_ID_COLLISION: {name} at {rel}")
        if rel not in snapshot.files or rel in {STATE, CAPABILITIES}:
            continue
        unowned_claim = (item.get("componentId") and rel not in snapshot.components and
                         plan.get("targetType") == "managed-kos" and action not in {"PRESERVE", "SKIP"})
        if unowned_claim:
            blockers.add("OCCUPIED_COMPONENT_PATH: " + rel)
        if rel in snapshot.protected and action in CHANGING and rel not in historical:
            blockers.add("PROTECTED_FILE_WRITE: " + rel)
    return sorted(blockers)


def compare_audits(before: Audit, after: Audit, approved_plan=None) -> dict:
    """Report relative path/line diagnostics. Do not return note text or configuration."""
    blockers, warnings = set(after.issues), before.warnings | after.warnings
    historical = _historical_replacements(approved_plan, before)
    for rel, signature in before.protected.items():
        if after.files.get(rel) != historical.get(rel, signature):
            blockers.add("PROTECTED_FILE_CHANGED: " + rel)
    for key, value in before.settings.items():
        if after.settings.get(key) != value:
            blockers.add("VAULT_SETTING_CHANGED: " + key)
    for name, old in before.capabilities.items():
        new = after.capabilities.get(name)
        if (new is None or not old["paths"] <= new["paths"] or not old["available"] <= new["available"]
                or any(new["metadata"].get(key) != value for key, value in old["metadata"].items())):
            blockers.add("CAPABILITY_BINDING_CHANGED: " + name)
    for key, value in before.packages.items():
        if value != after.packages.get(key):
            blockers.add(f"PACKAGE_REGISTRATION_CHANGED: {key[0]} / {key[1]}")
    for rel, ids in before.portable.items():
        if after.portable.get(rel) != ids:
            blockers.add("PORTABLE_EXTENSION_MISSING: " + rel)
    # Additional discovery roots with the same portable ID could shadow an
    # original. Keep previously coexisting provider aliases as baseline.
    previous_ids = set().union(*before.portable.values())
    for rel, ids in after.portable.items():
        for name in (ids - before.portable.get(rel, set())).intersection(previous_ids):
            blockers.add(f"PORTABLE_ID_COLLISION: {name} at {rel}")

    regressions, preexisting, unverified = [], [], []
    for key, (status, targets, line) in after.links.items():
        old = before.links.get(key)
        location = f"{key[0]}:{line}"
        if status == "unverified":
            unverified.append(location)
        if old and old[0] == "resolved" and (status != "resolved" or targets != old[1]):
            regressions.append({"source": location, "status": "redirected" if status == "resolved" else status})
        elif status in {"ambiguous", "missing"}:
            if old and old[0] in {"ambiguous", "missing"}:
                preexisting.append({"source": location, "status": status})
            else:
                regressions.append({"source": location, "status": status})
    for issue in regressions:
        blockers.add(f"LINK_{issue['status'].upper()}: {issue['source']}")
    return {"blockers": sorted(blockers), "warnings": sorted(warnings),
            "links": {"scannedNotes": after.markdown_count, "references": len(after.links),
                      "regressions": regressions, "preexisting": preexisting, "unverified": unverified},
            "extensions": {
                "registered": len(after.packages), "portable": len(after.portable),
                "registeredIds": sorted({name for _, name in after.packages}),
                "preservedRegisteredIds": sorted({key[1] for key, entry in before.packages.items()
                                                  if after.packages.get(key) == entry}),
                "portablePaths": sorted(after.portable),
                "preservedPortablePaths": sorted(rel for rel, ids in before.portable.items()
                                                 if after.portable.get(rel) == ids and
                                                 before.files[rel] == after.files.get(rel)),
            },
            "protectedFilesChecked": len(before.protected)}
