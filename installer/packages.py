"""Offline immutable packages. Never imports or executes package code."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path

from contracts import RELEASE, canonical_edition, check, compatible, supports_edition, version
from engine import _metadata_item, state_read
from safety import Blocked, ROOT, current_hash, digest, encoded, inventory, json_read, json_loads, relative, safe

REGISTRIES = {"skill": ".agents/registry/skills.json", "powerup": "00 - System/Power-Ups/Registry/power-ups.json"}
GENERIC = "00 - System/Config/packages.json"
HOMES = {"skill": ".agents/skills", "powerup": "00 - System/Power-Ups/Installed",
         "adapter": "00 - System/Adapters/Installed", "integration": "00 - System/Integrations/Installed", "bundle": "00 - System/Bundles/Installed"}


def signature_verify(manifest, trust):
    signature = manifest.get("signature")
    if not signature:
        if manifest.get("requiresSignature"):
            raise Blocked("SIGNATURE_REQUIRED")
        return
    if not trust:
        raise Blocked("SIGNATURE_TRUST_UNAVAILABLE")
    keys = json_read(safe(trust.parent, trust.name))
    key = keys.get("keys", {}).get(signature.get("keyId"))
    if not key or signature.get("algorithm") != "rsa-sha256":
        raise Blocked("SIGNATURE_UNTRUSTED")
    unsigned = {k: v for k, v in manifest.items() if k != "signature"}
    try:
        modulus = int.from_bytes(base64.b64decode(key["modulus"], validate=True), "big")
        exponent = int.from_bytes(base64.b64decode(key["exponent"], validate=True), "big")
        size = (modulus.bit_length() + 7) // 8
        raw = base64.b64decode(signature["value"], validate=True)
        if size < 256 or len(raw) != size or int.from_bytes(raw, "big") >= modulus or exponent < 3:
            raise ValueError()
        recovered = pow(int.from_bytes(raw, "big"), exponent, modulus).to_bytes(size, "big")
        suffix = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(encoded(unsigned)).digest()
        expected = b"\x00\x01" + b"\xff" * (size - len(suffix) - 3) + b"\x00" + suffix
        if recovered != expected:
            raise ValueError()
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise Blocked("SIGNATURE_INVALID") from exc


def read_package(path: Path, trust=None):
    safe(path.parent, path.name)
    blobs = {}
    if path.is_dir():
        total = 0
        names = set()
        for item in inventory(path):
            name = relative(item["path"])
            if name.casefold() in names or name.split("/")[0] in {".git", "00 - System"}:
                raise Blocked("PACKAGE_RESERVED_OR_DUPLICATE_PATH")
            names.add(name.casefold())
            if item["kind"] in {"link", "special"}:
                raise Blocked("PACKAGE_LINK")
            if item["kind"] == "file":
                source = safe(path, name)
                size = source.stat().st_size
                total += size
                if total > 64 * 1024 * 1024 or len(names) > 4096 or size > 16 * 1024 * 1024:
                    raise Blocked("ARCHIVE_RESOURCE_LIMIT")
                blobs[name] = source.read_bytes()
    else:
        with zipfile.ZipFile(path) as archive:
            total = 0
            names = set()
            for entry in archive.infolist():
                name = relative(entry.filename.rstrip("/"))
                if name.casefold() in names:
                    raise Blocked("ARCHIVE_DUPLICATE_PATH")
                names.add(name.casefold())
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR} or entry.flag_bits & 1:
                    raise Blocked("ARCHIVE_UNSAFE_ENTRY")
                total += entry.file_size
                if total > 64 * 1024 * 1024 or len(names) > 4096 or entry.file_size > 16 * 1024 * 1024:
                    raise Blocked("ARCHIVE_RESOURCE_LIMIT")
                if not entry.is_dir():
                    blobs[name] = archive.read(entry)
    if "manifest.json" not in blobs:
        raise Blocked("PACKAGE_MANIFEST_MISSING")
    manifest = json_loads(blobs["manifest.json"].decode("utf-8-sig"))
    check("package", manifest)
    from contracts import validate
    validate(manifest["defaults"], manifest["configurationSchema"])
    kind = manifest["type"]
    if manifest["schema"] != {"skill": "kos-skill/v1", "powerup": "kos-powerup/v1"}.get(kind, "kos-package/v1"):
        raise Blocked("PACKAGE_SCHEMA_IDENTITY")
    if not compatible(manifest["compatibility"], RELEASE["kosContractVersion"]):
        raise Blocked("PACKAGE_CONTRACT_INCOMPATIBLE")
    canonical_editions = [canonical_edition(item) for item in manifest["supportedEditions"]]
    if canonical_editions == ["pro"] and not any(d.startswith(("kos.pro.", "kos.core.")) for d in manifest.get("requiredCapabilities", [])):
        raise Blocked("PRO_ONLY_REQUIRES_CAPABILITY")
    if canonical_editions == ["enterprise"] and not any(d.startswith("kos.enterprise.") for d in manifest.get("requiredCapabilities", [])):
        raise Blocked("ENTERPRISE_ONLY_REQUIRES_CAPABILITY")
    integrity = manifest["integrity"]
    declared = list(integrity)
    if any(p.casefold() in {"manifest.json", "skill.json"} for p in declared):
        raise Blocked("PACKAGE_RESERVED_MANIFEST_PATH")
    folded = [p.casefold() for p in declared]
    if len(folded) != len(set(folded)) or any(a.startswith(b + "/") for a in folded for b in folded if a != b):
        raise Blocked("PACKAGE_PATH_CONFLICT")
    if set(blobs) != {"manifest.json"} | {"payload/" + relative(p) for p in integrity}:
        raise Blocked("PACKAGE_UNDECLARED_OR_MISSING_FILES")
    for rel, expected in integrity.items():
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(blobs["payload/" + rel]) != expected:
            raise Blocked("PACKAGE_HASH_MISMATCH")
    for entry in manifest["entrypoints"]:
        if relative(entry) not in integrity:
            raise Blocked("PACKAGE_ENTRYPOINT_MISSING")
    if kind == "skill" and (manifest.get("entrypoint") != "SKILL.md" or "SKILL.md" not in integrity):
        raise Blocked("SKILL_ENTRYPOINT_REQUIRED")
    signature_verify(manifest, trust)
    identity = digest(encoded(manifest))
    return manifest, {key[8:]: val for key, val in blobs.items() if key.startswith("payload/")}, identity


def registries(root):
    result = {}
    for rel in [*REGISTRIES.values(), GENERIC]:
        path = safe(root, rel)
        data = json_read(path) if path.exists() else {"schemaVersion": "1.0.0", "packages": {}}
        check("registry", data)
        result[rel] = data
    return result


def dependencies(manifest, all_packages):
    graph = {key: value["versions"][value["activeVersion"]]["manifest"].get("dependencies", {})
             for key, value in all_packages.items() if value.get("activeVersion") and value.get("enabled")}
    graph[manifest["id"]] = manifest["dependencies"]
    for name, required in manifest["dependencies"].items():
        item = all_packages.get(name)
        if not item or not item["enabled"] or item["activeVersion"] != required:
            raise Blocked("DEPENDENCY_MISSING_OR_VERSION")
    visiting, visited = set(), set()
    def visit(name):
        if name in visiting:
            raise Blocked("DEPENDENCY_CYCLE")
        if name in visited:
            return
        visiting.add(name)
        for child in graph.get(name, {}):
            visit(child)
        visiting.remove(name)
        visited.add(name)
    for name in graph:
        visit(name)


def verify_installed(root, record):
    base = record["path"]
    relative(base)
    manifest = record["manifest"]
    check("package", manifest)
    expected_base = HOMES[manifest["type"]] + "/" + manifest["id"] + "/" + manifest["version"]
    if base != expected_base:
        raise Blocked("PACKAGE_RESERVED_PATH")
    if digest(encoded(manifest)) != record["identity"]:
        raise Blocked("REGISTRY_IDENTITY_CHANGED")
    disk_manifest = json_read(safe(root, base + "/manifest.json"))
    if disk_manifest != manifest:
        raise Blocked("PACKAGE_MANIFEST_MODIFIED")
    if manifest["type"] == "skill" and json_read(safe(root, base + "/skill.json")) != manifest:
        raise Blocked("SKILL_MANIFEST_MODIFIED")
    for rel, expected in manifest["integrity"].items():
        if current_hash(root, base + "/" + relative(rel)) != expected:
            raise Blocked("PACKAGE_INSTALLED_MODIFIED")
    return True


def plan_package(root, command, package=None, package_id=None, selected_version=None, trust=None, permission_approval=False):
    state = state_read(root)
    if not state:
        raise Blocked("PACKAGE_REQUIRES_MANAGED_KOS")
    data = registries(root)
    all_packages = {}
    for registry in data.values():
        for key, entry in registry["packages"].items():
            if key in all_packages:
                raise Blocked("PACKAGE_DUPLICATE_ID")
            all_packages[key] = entry
    planned = {"schemaVersion": "1.0.0", "operation": "package " + command, "targetType": "managed-kos", "edition": canonical_edition(state["edition"]), "previousVersion": state["starterKitVersion"], "resultingVersion": state["starterKitVersion"], "items": [], "permissions": [], "blocked": False}
    payload = {}
    if command == "list":
        planned["packages"] = all_packages
        return planned, payload
    if command in {"install", "update", "validate"}:
        if package is None:
            raise Blocked("PACKAGE_REQUIRED")
        manifest, blobs, identity = read_package(package, trust)
        package_id = manifest["id"]
        if not supports_edition(manifest["supportedEditions"], state["edition"]):
            raise Blocked("PACKAGE_EDITION_INCOMPATIBLE")
        if not set(manifest.get("requiredCapabilities", [])) <= set(state["capabilities"]):
            raise Blocked("PACKAGE_CAPABILITY_MISSING")
        dependencies(manifest, all_packages)
        planned["permissions"] = manifest["permissions"]
        if command == "validate":
            return planned, payload
        reg_path = REGISTRIES.get(manifest["type"], GENERIC)
        reg = data[reg_path]
        existing = all_packages.get(package_id)
        if existing and package_id not in reg["packages"]:
            raise Blocked("PACKAGE_TYPE_CONFLICT")
        if command == "update" and not existing:
            raise Blocked("PACKAGE_UPDATE_NOT_INSTALLED")
        if existing and selected_version:
            raise Blocked("PACKAGE_VERSION_ARGUMENT_NOT_APPLICABLE")
        package_version = manifest["version"]
        if existing and version(package_version) < version(existing["activeVersion"]):
            raise Blocked("PACKAGE_DOWNGRADE_USE_ROLLBACK")
        if existing and package_version in existing["versions"]:
            record = existing["versions"][package_version]
            if record["identity"] != identity:
                raise Blocked("PACKAGE_SAME_VERSION_DIFFERENT_CONTENT")
            verify_installed(root, record)
            return planned, payload  # identical install never changes enabled state
        if manifest["permissions"] and not permission_approval:
            planned["blocked"] = True
            planned["requiredAction"] = "Review permissions and pass --approve-permissions"
        if existing:
            for record in existing["versions"].values():
                verify_installed(root, record)
        base = HOMES[manifest["type"]] + "/" + package_id + "/" + package_version
        if safe(root, base).exists() and any(i["kind"] != "directory" for i in inventory(safe(root, base))):
            raise Blocked("IMMUTABLE_VERSION_DIRECTORY_EXISTS")
        installed_files = {**blobs, "manifest.json": encoded(manifest)}
        if manifest["type"] == "skill":
            if "skill.json" in blobs:
                raise Blocked("PACKAGE_RESERVED_MANIFEST_PATH")
            installed_files["skill.json"] = encoded(manifest)
        for rel, blob in sorted(installed_files.items()):
            destination = base + "/" + relative(rel)
            _metadata_item(root, planned, payload, destination, blob)
            planned["items"][-1]["ownership"] = "extension-owned"
        entry = copy.deepcopy(existing) if existing else {"enabled": manifest["enabledByDefault"], "versions": {}}
        entry["versions"][package_version] = {"path": base, "identity": identity, "manifest": manifest}
        entry["previousVersion"] = entry.get("activeVersion")
        entry["activeVersion"] = package_version
        reg["packages"][package_id] = entry
        _metadata_item(root, planned, payload, reg_path, encoded(reg))
        return planned, payload
    if package_id not in all_packages:
        raise Blocked("PACKAGE_NOT_INSTALLED")
    entry = all_packages[package_id]
    reg_path = next(p for p, r in data.items() if package_id in r["packages"])
    if command in {"disable", "uninstall", "rollback"}:
        for name, dependent in all_packages.items():
            active = dependent["versions"][dependent["activeVersion"]]["manifest"]
            if name != package_id and dependent["enabled"] and package_id in active["dependencies"]:
                raise Blocked("PACKAGE_HAS_ACTIVE_DEPENDENTS")
    if command == "enable":
        record = entry["versions"][entry["activeVersion"]]
        verify_installed(root, record)
        dependencies(record["manifest"], all_packages)
        entry["enabled"] = True
    elif command == "disable":
        entry["enabled"] = False
    elif command == "rollback":
        previous = selected_version or entry.get("previousVersion")
        if previous not in entry["versions"]:
            raise Blocked("PACKAGE_PREVIOUS_VERSION_UNAVAILABLE")
        record = entry["versions"][previous]
        verify_installed(root, record)
        dependencies(record["manifest"], all_packages)
        entry["previousVersion"], entry["activeVersion"] = entry["activeVersion"], previous
    elif command == "uninstall":
        for record in entry["versions"].values():
            verify_installed(root, record)
            for rel in [*record["manifest"]["integrity"], "manifest.json"] + (["skill.json"] if record["manifest"]["type"] == "skill" else []):
                destination = record["path"] + "/" + relative(rel)
                planned["items"].append({"path": destination, "classification": "OLDER_MANAGED", "action": "REMOVE", "currentHash": current_hash(root, destination), "ownership": "extension-owned"})
                payload[destination] = None
        del data[reg_path]["packages"][package_id]
    else:
        raise Blocked("PACKAGE_COMMAND_INVALID")
    _metadata_item(root, planned, payload, reg_path, encoded(data[reg_path]))
    return planned, payload


def effective_config(defaults, global_config, project_config):
    """Defaults < global < project; object merge, arrays replaced at each layer."""
    result = copy.deepcopy(defaults)
    for layer in (global_config, project_config):
        for key, val in layer.items():
            result[key] = effective_config(result.get(key, {}), val, {}) if isinstance(val, dict) and isinstance(result.get(key, {}), dict) else copy.deepcopy(val)
    return result


def resolve_powerup(root, package_id, project=None):
    """Read-only activation/configuration resolver. Returns data; executes nothing."""
    from contracts import validate
    registry = registries(root)[REGISTRIES["powerup"]]
    entry = registry["packages"].get(package_id)
    if not entry:
        raise Blocked("PACKAGE_NOT_INSTALLED")
    override = {}
    if project is not None:
        relative(project)
        if "/" in project:
            raise Blocked("PROJECT_NAME_INVALID")
        path = safe(root, "02 - Projects/Active/" + project + "/power-ups.json")
        if path.exists():
            activation = json_read(path)
            check("project-activation", activation)
            override = activation["packages"].get(package_id, {})
    selected = override.get("version", entry["activeVersion"])
    if selected not in entry["versions"]:
        raise Blocked("PROJECT_VERSION_NOT_INSTALLED")
    record = entry["versions"][selected]
    verify_installed(root, record)
    manifest = record["manifest"]
    if project and manifest["scope"] == "global":
        raise Blocked("PACKAGE_SCOPE_CONFLICT")
    global_path = safe(root, "00 - System/Config/Power-Ups/" + package_id + ".json")
    global_config = json_read(global_path) if global_path.exists() else {}
    if not isinstance(global_config, dict):
        raise Blocked("CONFIG_TYPE_CONFLICT")
    config = effective_config(manifest["defaults"], global_config, override.get("configuration", {}))
    validate(config, manifest["configurationSchema"])
    return {"id": package_id, "version": selected, "enabled": entry["enabled"] and override.get("enabled", True),
            "entrypoints": [record["path"] + "/" + p for p in manifest["entrypoints"]], "configuration": config}
