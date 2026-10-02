"""Read-only validation with stable, content-redacted rule identifiers."""
import re
from safety import Blocked, STATE, RUNS, inventory, json_read, safe
from engine import CAPABILITIES, evidence, state_read
from packages import registries, verify_installed
from contracts import check


def validate_installation(root):
    findings = []
    def add(rule, path="", severity="error"):
        findings.append({"rule": rule, "path": path, "severity": severity})
    try:
        files = inventory(root)
        state = state_read(root)
        if state is None:
            add("META_MISSING", STATE)
            return findings
        by_path = {i["path"]: i for i in files}
        for rel, component in state["components"].items():
            if rel not in by_path:
                add("ASSET_MISSING", rel)
            elif by_path[rel]["kind"] == "link":
                add("ASSET_LINK_PRESERVED", rel)
            elif by_path[rel].get("hash") != component["installedHash"]:
                add("ASSET_MODIFIED", rel, "warning")
        for cap_id, entries in evidence(root, files).items():
            if any(not entry["valid"] for entry in entries):
                add("CAPABILITY_STALE", cap_id)
        caps = json_read(safe(root, CAPABILITIES))
        check("capabilities", caps)
        if set(state["capabilities"]) != {c["id"] for c in caps["capabilities"]}:
            add("CAPABILITY_STATE_MISMATCH", CAPABILITIES)
        for registry in registries(root).values():
            for entry in registry["packages"].values():
                for record in entry["versions"].values():
                    try:
                        verify_installed(root, record)
                    except (ValueError, OSError):
                        add("PACKAGE_INTEGRITY", record.get("path", ""))
        for provider in state.get("providers", []):
            matching = [c for c in caps["capabilities"] if c["id"] == "kos.provider." + provider]
            rel = matching[0]["paths"][0] if matching else provider.upper() + ".md"
            text = safe(root, rel).read_text(encoding="utf-8-sig")
            if "AGENTS.md" not in text or len(text.splitlines()) > 40:
                add("ADAPTER_ROUTING", rel)
        for item in files:
            if item["kind"] == "link":
                add("LINK_PRESERVED_NOT_TRAVERSED", item["path"], "warning")
                continue
            rel = item["path"]
            if item["kind"] != "file" or not rel.endswith((".md", ".json", ".yaml", ".yml", ".txt")):
                continue
            path = safe(root, rel)
            if path.stat().st_size > 2 * 1024 * 1024:
                add("SCAN_SIZE_LIMIT", rel, "warning")
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if re.search(r"(?i)(password|api[_-]?key|access[_-]?token)\s*[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{12,}", text) or "-----BEGIN " + "PRIVATE KEY-----" in text:
                add("SECRET_EXPOSURE", rel)
            if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:Users|home)/[^/\s]+/", text):
                add("MACHINE_PATH", rel, "warning")
        for required in ("00 - System", "06 - Inbox", "08 - Templates", "99 - Archive"):
            if required not in by_path:
                add("STRUCTURE_MISSING", required)
    except (ValueError, OSError, KeyError, TypeError):
        add("VALIDATION_UNSAFE_OR_INVALID_METADATA")
    return findings
