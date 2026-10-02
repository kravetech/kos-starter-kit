"""Deterministic reconciliation. Planning does not write to the target."""
from __future__ import annotations

import copy
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from contracts import RELEASE, canonical_edition, check, version
from safety import (Blocked, ROOT, STATE, RUNS, current_hash, digest, encoded,
                    inventory, json_read, merge_existing, relative, safe, target_root)
from transaction import Transaction

CAPABILITIES = "00 - System/Config/capabilities.json"
LINK_PATTERN = re.compile(r"!?\[\[([^\]\r\n]+)\]\]|!?\[[^\]\r\n]*\]\((<[^>\r\n]*>|[^)\r\n]+)\)")
LINK_SCAN_MAX_FILES = 20000
LINK_SCAN_MAX_MARKDOWN = 10000
LINK_SCAN_MAX_BYTES = 1024 * 1024
LINK_SCAN_MAX_REFERENCES = 50000


def _link_index(paths):
    by_path, by_name = {}, {}
    for rel in sorted(paths):
        path = Path(rel)
        by_path.setdefault(rel.casefold(), []).append(rel)
        name = path.stem if path.suffix.lower() == ".md" else path.name
        by_name.setdefault(name.casefold(), []).append(rel)
    return by_path, by_name


def _link_path(raw, source=""):
    parts = []
    for part in (source + "/" + raw if source else raw).split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def _link_candidates(index, source, raw, kind):
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if kind == "markdown":
        target = target.strip("<>")
        target = unquote(target.split("?", 1)[0])
    if not target or "\\" in target or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:|^//", target):
        return []
    by_path, by_name = index
    explicit = "/" in target
    suffix = "" if Path(target).suffix else ".md"
    if kind == "wiki" and not explicit:
        return sorted(by_name.get(target.removesuffix(".md").casefold(), []))
    source_dir = source.rpartition("/")[0]
    candidates = ([target.lstrip("/")] if target.startswith("/") else
                  [target, source_dir + "/" + target] if explicit and not target.startswith(("./", "../")) else
                  [source_dir + "/" + target, target])
    if kind == "wiki":
        candidates = [target.lstrip("/")]
    for candidate in candidates:
        normalized = _link_path(candidate + suffix)
        if normalized is not None:
            matches = by_path.get(normalized.casefold(), [])
            if matches:
                return sorted(matches)
    return []


def link_audit(root, files, items):
    """Compare bounded existing Markdown links with the proposed additive file set."""
    existing = {item["path"] for item in files if item["kind"] == "file"}
    if len(existing) > LINK_SCAN_MAX_FILES:
        raise Blocked("LINK_SCAN_LIMIT")
    added = {item["path"] for item in items if item.get("action") == "CREATE" and item["path"] not in existing}
    before, after = _link_index(existing), _link_index(existing | added)
    rewritten = {item["path"] for item in items if item.get("action") in {"UPDATE_SAFE", "UPDATE_APPROVED", "MERGE"}}
    notes = sorted(rel for rel in existing - rewritten if rel.lower().endswith(".md"))
    if len(notes) > LINK_SCAN_MAX_MARKDOWN:
        raise Blocked("LINK_SCAN_LIMIT")
    collisions = sorted(name for name, paths in after[1].items()
                        if len(paths) > 1 and len(before[1].get(name, [])) <= 1)
    audit = {"scannedMarkdownFiles": len(notes), "references": 0,
             "preexistingUnresolved": 0, "preexistingAmbiguous": 0,
             "newBasenameCollisions": collisions, "regressions": []}
    for rel in notes:
        path = safe(root, rel)
        if path.stat().st_size > LINK_SCAN_MAX_BYTES:
            raise Blocked("LINK_SCAN_LIMIT")
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        content = re.sub(r"(?ms)^```.*?^```[^\r\n]*", "", content)
        content = re.sub(r"`+[^`\r\n]*`+", "", content)
        for match in LINK_PATTERN.finditer(content):
            kind = "wiki" if match.group(1) is not None else "markdown"
            target = match.group(1) if kind == "wiki" else match.group(2)
            old = _link_candidates(before, rel, target, kind)
            new = _link_candidates(after, rel, target, kind)
            audit["references"] += 1
            if audit["references"] > LINK_SCAN_MAX_REFERENCES:
                raise Blocked("LINK_SCAN_LIMIT")
            if not old:
                audit["preexistingUnresolved"] += 1
            elif len(old) > 1:
                audit["preexistingAmbiguous"] += 1
            elif new != old:
                audit["regressions"].append({"source": rel, "kind": kind, "target": target})
    audit["regressions"] = sorted({(r["source"], r["kind"], r["target"]) for r in audit["regressions"]})
    audit["regressions"] = [{"source": source, "kind": kind, "target": target}
                            for source, kind, target in audit["regressions"]]
    return audit


def text_hashes(text):
    """Exact encodings emitted by the historical Python and PowerShell writers."""
    result = set()
    for ending in ("\n", "\r\n"):
        for extra in ("", "\n", "\r\n"):
            raw = (text.replace("\r\n", "\n").replace("\n", ending) + extra).encode("utf-8")
            result.update((digest(raw), digest(b"\xef\xbb\xbf" + raw)))
    return result


def detect(root: Path, files=None):
    root = target_root(root)
    if not root.exists():
        return "new-target"
    files = inventory(root) if files is None else files
    if not files:
        return "empty-directory"
    names = {i["path"] for i in files if i["kind"] != "link"}
    pro_version = "00 - System/Core/version.json"
    if pro_version in names:
        record = json_read(safe(root, pro_version))
        if not isinstance(record, dict):
            raise Blocked("VERSION_RECORD_INVALID")
        if record.get("product_id") == "kos-pro" or canonical_edition(record.get("edition")) == "pro":
            return "pro-kos"
    if STATE in names:
        return "managed-kos"
    if "00 - System/Installation/installer-state.json" in names or {"AGENTS.md", "CONTEXT-POLICY.md", "00 - System"} <= names:
        return "legacy-kos"
    if ".obsidian" in names:
        return "obsidian-vault"
    return "ambiguous-mixed"


def state_read(root):
    path = safe(root, STATE)
    if not path.exists():
        return None
    data = json_read(path)
    check("installation", data)
    if canonical_edition(data["edition"]) != "community":
        raise Blocked("EDITION_UNSUPPORTED")
    for rel, asset in data["components"].items():
        relative(rel)
        check("asset", asset)
        if asset["path"] != rel:
            raise Blocked("ASSET_PATH_MISMATCH")
    if data["starterKitVersion"] not in RELEASE["supportedUpgradeVersions"]:
        raise Blocked("VERSION_UNSUPPORTED_OR_DOWNGRADE")
    if version(data["kosContractVersion"]) > version(RELEASE["kosContractVersion"]):
        raise Blocked("CONTRACT_DOWNGRADE")
    if data.get("communityVersion") and version(data["communityVersion"]) > version(RELEASE["communityVersion"]):
        raise Blocked("COMMUNITY_DOWNGRADE")
    return data


def answers_read(value):
    if isinstance(value, dict) and isinstance(value.get("installation"), dict) and "backup_before_migration" in value["installation"]:
        raise Blocked("BACKUP_SETTING_UNSUPPORTED: create and verify a complete vault snapshot outside the target before migration")
    defaults = json_read(ROOT / "installer/defaults.json")
    answers = merge_existing(defaults, value)
    if answers["installation"].get("allow_overwrite"):
        raise Blocked("GLOBAL_OVERWRITE_FORBIDDEN")
    check("answers", answers)
    return answers


def contents(answers, profile, old=None):
    catalog = json_read(ROOT / "installer/assets.json")
    historical = json_read(ROOT / "installer/historical-templates.json")["templates"]
    providers = answers["installation"].get("providers", ["codex", "claude"])
    values = {}
    for section in ("user", "system", "privacy", "rhythm"):
        for key, val in answers[section].items():
            values[key] = str(val).lower() if isinstance(val, bool) else ", ".join(map(str, val)) if isinstance(val, list) else str(val)
    values.update(system_name=answers["system"]["name"], system_short_name=answers["system"]["short_name"], system_description=answers["system"]["description"])
    values.update(starter_kit_version=RELEASE["starterKitVersion"], community_version=RELEASE["communityVersion"], kos_contract_version=RELEASE["kosContractVersion"])
    result = {}
    for asset in catalog["assets"]:
        asset = dict(asset)
        if asset.get("sample") and not answers["installation"].get("include_samples", False):
            continue
        if profile in {"lean", "custom"} and asset.get("module") in {"business", "personal", "hobbies", "knowledge"}:
            if profile == "lean" or asset["module"] not in answers["installation"].get("custom_modules", []):
                continue
        if asset.get("provider") and asset["provider"] not in providers:
            continue
        if profile == "minimal" and not asset.get("minimal", False):
            continue
        source = safe(ROOT, asset["source"])
        text = source.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        tokens = set(re.findall(r"\{\{([a-z0-9_]+)\}\}", text)) - {"starter_kit_version", "community_version", "kos_contract_version"}
        if tokens:
            asset["renderFingerprint"] = digest(encoded({key: values.get(key, "") for key in tokens}))
        text = re.sub(r"\{\{([a-z0-9_]+)\}\}", lambda m: values.get(m[1], m[0]), text)
        hashes = []
        for snapshot in historical:
            if snapshot["path"] == asset["path"]:
                prior = re.sub(r"\{\{([a-z0-9_]+)\}\}", lambda m: values.get(m[1], m[0]), snapshot["text"])
                hashes.extend(text_hashes(prior))
        asset["historicalHashes"] = hashes
        asset["compatibleHashes"] = text_hashes(text)
        if re.search(r"\{\{[a-z0-9_]+\}\}", text):
            raise Blocked("TEMPLATE_UNRESOLVED")
        result[asset["path"]] = (text.encode("utf-8"), asset)
    return result


def evidence(root, files):
    """Declared capability IDs plus existing implementation paths, never names alone."""
    found = {}
    for item in files:
        rel = item["path"]
        if item["kind"] != "file" or not rel.endswith(".json") or rel == STATE:
            continue
        path = safe(root, rel)
        if path.stat().st_size > 1024 * 1024:
            continue
        try:
            data = json_read(path)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(data, dict):
            continue
        # Manifest identity is evidence even when directories/files use other names.
        declared_schema = data.get("schema")
        manifest_cap = {"kos-skill/v1": "kos.skills.runtime", "kos-powerup/v1": "kos.powerups.runtime"}.get(declared_schema) if isinstance(declared_schema, str) else None
        if manifest_cap:
            entries = data.get("entrypoints", [data.get("entrypoint", "SKILL.md")])
            paths = [str(Path(rel).parent / entry).replace("\\", "/") for entry in entries if isinstance(entry, str)] if isinstance(entries, list) else []
            try:
                valid = bool(paths) and all(safe(root, p).is_file() for p in paths)
            except (ValueError, TypeError):
                valid = False
            found.setdefault(manifest_cap, []).append({"source": rel, "paths": paths, "valid": valid})
        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list):
            continue
        for cap in capabilities:
            if not isinstance(cap, dict) or not isinstance(cap.get("id"), str):
                continue
            paths = cap.get("paths", [])
            valid = isinstance(paths, list) and bool(paths)
            try:
                valid = valid and all(safe(root, p).is_file() for p in paths)
            except (ValueError, TypeError):
                valid = False
            found.setdefault(cap["id"], []).append({"source": rel, "paths": paths, "valid": valid})
    return found


def plan(root: Path, operation: str, answers: dict, profile="standard", decisions=None):
    root = target_root(root)
    files = inventory(root)
    kind = detect(root, files)
    state = state_read(root)
    decisions = decisions or {}
    if operation == "new" and kind not in {"new-target", "empty-directory"}:
        raise Blocked("NEW_REQUIRES_EMPTY: select upgrade or enhance")
    if operation in {"upgrade", "repair"} and kind not in {"managed-kos", "legacy-kos"}:
        raise Blocked("KOS_NOT_DETECTED")
    if operation == "enhance" and kind not in {"obsidian-vault", "managed-kos"}:
        raise Blocked("OBSIDIAN_NOT_DETECTED")
    if operation == "enhance" and kind == "managed-kos" and state.get("origin") != "enhance":
        raise Blocked("USE_UPGRADE_FOR_MANAGED_KOS")
    # Existing profile/provider choices are configuration, not new defaults.
    if state:
        profile = state["profile"]
        answers = copy.deepcopy(answers)
        answers["installation"]["providers"] = state.get("providers", ["codex", "claude"])
        answers["installation"]["include_samples"] = state.get("includeSamples", False)
        answers["installation"]["custom_modules"] = state.get("customModules", [])
    old_assets = state.get("components", {}) if state else {}
    desired = contents(answers, profile, state)
    plan_data = {"schemaVersion": "1.0.0", "operation": operation, "targetType": kind,
                 "previousVersion": state["starterKitVersion"] if state else None,
                 "resultingVersion": RELEASE["starterKitVersion"], "edition": canonical_edition(state.get("edition", RELEASE["edition"])) if state else RELEASE["edition"],
                 "profile": profile, "items": [], "links": [f["path"] for f in files if f["kind"] == "link"],
                 "decisions": decisions, "folderMappings": []}
    plan_data["inventorySummary"] = {"files": sum(f["kind"] == "file" for f in files), "directories": sum(f["kind"] == "directory" for f in files), "links": len(plan_data["links"])}
    plan_data["postActions"] = ["INITIALIZE_GIT"] if operation == "new" and answers["installation"].get("initialize_git") else []
    if answers["installation"].get("create_initial_commit"):
        raise Blocked("INITIAL_COMMIT_REQUIRES_MANUAL_CONTENT_REVIEW")
    if kind == "legacy-kos":
        legacy = safe(root, "00 - System/Installation/installer-state.json")
        if legacy.is_file():
            old_version = json_read(legacy).get("installer_version")
            if old_version and old_version not in RELEASE["supportedUpgradeVersions"]:
                raise Blocked("VERSION_UNSUPPORTED_OR_DOWNGRADE")
            plan_data["previousVersion"] = old_version
    if operation == "enhance":
        plan_data["folderMappings"] = [{"existing": f["path"], "recommendation": "retain in place; map explicitly in context policy"} for f in files if f["kind"] == "directory" and "/" not in f["path"] and not f["path"].startswith(".")]
    found = evidence(root, files)
    components = copy.deepcopy(old_assets)
    payload = {}
    installed_caps = []
    for rel, (data, asset) in sorted(desired.items()):
        current = None
        owner = old_assets.get(rel, {}).get("ownership", asset["ownership"])
        cap = asset.get("capability")
        classification, action = "MISSING", "CREATE"
        try:
            path = safe(root, rel, write=True)
            if path.exists() and not path.is_file():
                classification, action = "PATH_CONFLICT", "BLOCK"
            else:
                current = current_hash(root, rel)
                if current == digest(data):
                    classification, action = "IDENTICAL", "UNCHANGED"
                elif current in asset.get("compatibleHashes", []):
                    classification, action = "COMPATIBLE_EXISTING", "UNCHANGED"
                elif current is not None:
                    old = old_assets.get(rel)
                    if asset.get("merge") == "existing-priority":
                        try:
                            existing = json_read(path)
                            if asset.get("schema"):
                                check(asset["schema"], existing)
                            merged = merge_existing(__import__('json').loads(data), existing)
                            data = path.read_bytes() if merged == existing else encoded(merged)
                            classification, action = ("COMPATIBLE_EXISTING", "UNCHANGED") if digest(data) == current else ("CONFIG_CONFLICT", "MERGE")
                        except (ValueError, UnicodeError):
                            classification, action = "CONFIG_CONFLICT", "BLOCK"
                    elif not old and plan_data["previousVersion"] == "1.1.0" and current in asset.get("historicalHashes", []):
                        classification, action = "OLDER_MANAGED", "UPDATE_SAFE"
                    elif old and current == old["installedHash"] and owner in {"managed", "managed-customizable"}:
                        if asset.get("renderFingerprint") and old.get("renderFingerprint") != asset["renderFingerprint"]:
                            classification, action = "CONFIG_CONFLICT", "PROPOSE"
                        else:
                            classification, action = "OLDER_MANAGED", "UPDATE_SAFE"
                    else:
                        classification, action = "USER_MODIFIED", "PROPOSE"
                        if not old:
                            owner = "user-owned"
                if cap and current is None:
                    equivalent = [e for e in found.get(cap, []) if rel not in e["paths"]]
                    if equivalent:
                        classification, action = "SEMANTIC_DUPLICATE", "BLOCK"
                        if decisions.get(rel) == "adopt" and all(e["valid"] for e in equivalent):
                            action = "ADOPT"
                if asset.get("registry") and current is None:
                    # Legacy manifests/registries outside canonical paths need review.
                    legacy_candidates = [f for f in files if f["kind"] == "file" and
                                         f["path"].lower().endswith(("skill.json", "registry.yaml", "skills.json", "power-ups.json")) and f["path"] != rel]
                    if any((asset["registry"] == "skill" and "skill" in f["path"].lower()) or
                           (asset["registry"] == "powerup" and "power" in f["path"].lower()) for f in legacy_candidates):
                        classification, action = "SEMANTIC_DUPLICATE", "BLOCK"
        except Blocked:
            classification, action = "SECURITY_CONFLICT", "BLOCK"
        choice = decisions.get(rel)
        if choice in {"keep", "skip"} and classification not in {"SECURITY_CONFLICT", "RESERVED_PATH_CONFLICT"}:
            action = "PRESERVE" if choice == "keep" else "SKIP"
        elif choice == "replace" and classification == "USER_MODIFIED" and owner in {"managed", "managed-customizable"}:
            action = "UPDATE_APPROVED"
        elif choice == "propose" and classification == "USER_MODIFIED":
            action = "PROPOSE"
        elif choice and choice not in {"keep", "skip", "replace", "propose", "adopt"}:
            raise Blocked("DECISION_INVALID")
        if action == "PROPOSE" and old_assets.get(rel, {}).get("proposalHash") == digest(data):
            action = "PRESERVE"
        item = {"path": rel, "classification": classification, "action": action,
                "currentHash": current, "desiredHash": digest(data), "ownership": owner,
                "componentId": asset["componentId"]}
        plan_data["items"].append(item)
        payload[rel] = data
        if action in {"CREATE", "UPDATE_SAFE", "UPDATE_APPROVED", "MERGE", "UNCHANGED"}:
            previous = old_assets.get(rel)
            record = {"path": rel, "componentId": asset["componentId"], "ownership": owner,
                      "sourceVersion": RELEASE["starterKitVersion"], "installedHash": current if action == "UNCHANGED" else digest(data),
                      "lastInstallerAction": action}
            if asset.get("renderFingerprint"):
                record["renderFingerprint"] = asset["renderFingerprint"]
            # Identical legacy bytes can be adopted with exact template evidence.
            if previous and action == "UNCHANGED" and previous["installedHash"] == current:
                record = previous
            components[rel] = record
            if cap:
                installed_caps.append({"id": cap, "version": RELEASE["adapterVersion"] if asset.get("provider") else RELEASE["kosContractVersion"], "paths": [rel]})
        elif action == "PROPOSE":
            components[rel] = {**old_assets.get(rel, {"path": rel, "componentId": asset["componentId"], "ownership": "user-owned", "sourceVersion": "unknown", "installedHash": current, "lastInstallerAction": "PRESERVE"}), "proposalHash": digest(data)}
        elif action == "ADOPT":
            for e in found.get(cap, []):
                installed_caps.append({"id": cap, "version": RELEASE["kosContractVersion"], "paths": e["paths"]})
    # Preserve foreign capability records; duplicate identity is a conflict.
    caps_path = safe(root, CAPABILITIES, write=True)
    cap_data = json_read(caps_path) if caps_path.exists() else {"schemaVersion": "1.0.0", "capabilities": []}
    check("capabilities", cap_data)
    merged_caps = {c["id"]: c for c in cap_data["capabilities"]}
    if len(merged_caps) != len(cap_data["capabilities"]):
        raise Blocked("CAPABILITY_DUPLICATE")
    for cap in installed_caps:
        if cap["id"] not in merged_caps:
            merged_caps[cap["id"]] = cap
    cap_data["capabilities"] = sorted(merged_caps.values(), key=lambda x: x["id"])
    _metadata_item(root, plan_data, payload, CAPABILITIES, encoded(cap_data))
    next_state = copy.deepcopy(state) if state else {"schemaVersion": "1.0.0", "edition": RELEASE["edition"], "origin": operation}
    next_state["edition"] = canonical_edition(next_state.get("edition", RELEASE["edition"]))
    next_state.update({k: RELEASE[k] for k in ("starterKitVersion", "installerVersion", "communityVersion", "kosContractVersion")})
    next_state.update(profile=profile, providers=answers["installation"]["providers"], components=components,
                      capabilities=sorted(merged_caps), includeSamples=answers["installation"].get("include_samples", False), customModules=answers["installation"].get("custom_modules", []))
    _metadata_item(root, plan_data, payload, STATE, encoded(next_state))
    # Directory foundations are explicit plan items; no silently created domains.
    catalog = json_read(ROOT / "installer/assets.json")
    for rel in sorted(catalog["directories"]):
        domain = {"01 - Business": "business", "03 - Personal": "personal", "04 - Hobbies": "hobbies", "05 - Knowledge": "knowledge"}.get(rel.split("/")[0])
        if domain and profile in {"lean", "custom"} and (profile == "lean" or domain not in answers["installation"].get("custom_modules", [])):
            continue
        if profile == "minimal" and not rel.startswith(("00 - System", ".agents", "06 - Inbox", "08 - Templates", "99 - Archive")):
            continue
        try:
            path = safe(root, rel, write=True)
            action = "UNCHANGED" if path.is_dir() else "BLOCK" if path.exists() else "CREATE_DIRECTORY"
            classification = "IDENTICAL" if action == "UNCHANGED" else "PATH_CONFLICT" if action == "BLOCK" else "MISSING"
        except Blocked:
            action, classification = "BLOCK", "SECURITY_CONFLICT"
        plan_data["items"].append({"path": rel, "action": action, "classification": classification, "kind": "directory"})
    plan_data["items"].sort(key=lambda x: (x["path"], x.get("kind", "file")))
    if operation in {"upgrade", "enhance", "repair"}:
        plan_data["linkAudit"] = link_audit(root, files, plan_data["items"])
        for source in sorted({item["source"] for item in plan_data["linkAudit"]["regressions"]}):
            plan_data["items"].append({"path": source, "classification": "DEPENDENCY_CONFLICT",
                                       "action": "BLOCK", "rule": "LINK_RESOLUTION_REGRESSION"})
        plan_data["items"].sort(key=lambda x: (x["path"], x.get("kind", "file")))
    plan_data["blocked"] = any(i["action"] == "BLOCK" for i in plan_data["items"])
    return plan_data, payload


def _metadata_item(root, plan, payload, rel, data):
    current = current_hash(root, rel)
    action = "UNCHANGED" if current == digest(data) else "CREATE" if current is None else "MERGE"
    plan["items"].append({"path": rel, "classification": "IDENTICAL" if action == "UNCHANGED" else "MISSING" if current is None else "CONFIG_CONFLICT", "action": action, "currentHash": current, "desiredHash": digest(data), "ownership": "managed"})
    payload[rel] = data


def apply(root, planned, payload):
    if planned.get("blocked"):
        raise Blocked("PLAN_HAS_BLOCKING_CONFLICTS")
    changes = [i for i in planned["items"] if i["action"] in {"CREATE", "MERGE", "UPDATE_SAFE", "UPDATE_APPROVED", "PROPOSE", "CREATE_DIRECTORY", "REMOVE"}]
    if not changes:
        return None
    # Validate all paths/hashes before opening a transaction.
    for item in changes:
        safe(root, item["path"], write=True)
        if item.get("kind") != "directory" and current_hash(root, item["path"]) != item.get("currentHash"):
            raise Blocked("TARGET_CHANGED_SINCE_PLAN")
    with Transaction(root, planned) as tx:
        for item in sorted(changes, key=lambda i: (i["path"] in {STATE, CAPABILITIES} or i["path"].endswith(("skills.json", "power-ups.json", "packages.json")), i["path"])):
            rel = item["path"]
            if rel in {STATE, CAPABILITIES} or rel.endswith(("skills.json", "power-ups.json", "packages.json")):
                for entry in tx.journal["entries"]:
                    if entry.get("kind") != "directory" and current_hash(root, entry["path"]) != entry["afterHash"]:
                        raise Blocked("PRE_ACTIVATION_INTEGRITY_FAILURE")
            if item["action"] == "CREATE_DIRECTORY":
                tx.directory(rel)
            elif item["action"] == "PROPOSE":
                tx.write(tx.rel + "/proposals/" + rel, payload[rel], None)
            else:
                tx.write(rel, payload[rel], item.get("currentHash"), ownership=item.get("ownership", "managed"))
        tx.journal["validation"] = "written hashes and paths verified before metadata activation"
        if "INITIALIZE_GIT" in planned.get("postActions", []):
            entry = {"path": ".git", "kind": "git", "ownership": "runtime", "status": "intent"}
            tx.journal["entries"].append(entry)
            tx.save()
            safe(root, ".git", write=True)
            subprocess.run(["git", "-C", str(root), "init", "-b", "main"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            entry["status"] = "written"
            tx.save()
    return tx.run
