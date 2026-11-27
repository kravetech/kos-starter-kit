"""Run a single operation using the engine and catalog from the pinned distribution."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import re
import sys


def check_last_run(root, runs_rel, safe, read, blocked):
    runs = safe(root, runs_rel)
    if not runs.is_dir():
        return
    journals = []
    for path in runs.iterdir():
        if re.fullmatch("[0-9a-f]{32}", path.name):
            journal = safe(root, runs_rel + "/" + path.name + "/journal.json")
            if not journal.is_file():
                raise blocked("RUN_JOURNAL_MISSING: " + str(journal))
            journals.append((journal.stat().st_mtime_ns, journal))
    if journals:
        journal = max(journals)[1]
        if read(journal).get("status") != "complete":
            raise blocked("REVIEW_PREVIOUS_RUN: " + str(journal))
        summary = safe(root, runs_rel + "/" + journal.parent.name + "/setup-summary.json")
        if summary.is_file() and read(summary).get("status") != "complete":
            raise blocked("REVIEW_PREVIOUS_RUN: " + str(summary))


def execute(request):
    # Isolated interpreter: only the verified distribution supplies engine modules.
    sys.path.insert(0, str(Path(request["package"]) / "installer"))
    from contracts import RELEASE, canonical_edition, version
    from engine import answers_read, apply, detect, plan, state_read
    from safety import Blocked, RUNS, STATE, encoded, json_read, safe, target_root
    from validation import validate_installation

    root = target_root(Path(request["vault"]))
    mode = request["mode"]
    if mode == "identify":
        if not root.exists() or not any(root.iterdir()):
            return {"state": "new"}
        marker = "00 - System/Core/version.json"
        if safe(root, marker).is_file() and detect(root, [{"path": marker, "kind": "file"}]) == "pro-kos":
            return {"state": "pro"}
        receipt = safe(root, STATE)
        legacy = safe(root, "00 - System/Installation/installer-state.json")
        if safe(root, "00 - System/Installation/operation.lock").exists():
            raise Blocked("OPERATION_LOCKED: inspect the previous run journal")
        managed = receipt.is_file()
        if managed:
            raw = json_read(receipt)
            if canonical_edition(raw["edition"]) == "pro":
                return {"state": "pro"}
            record = state_read(root)
            previous = record["starterKitVersion"]
            for key in ("starterKitVersion", "installerVersion", "kosContractVersion", "communityVersion"):
                if key in record and version(record[key]) > version(RELEASE[key]):
                    raise Blocked("VERSION_UNSUPPORTED_OR_DOWNGRADE: " + key)
        elif legacy.is_file():
            raw = json_read(legacy)
            if canonical_edition(raw.get("edition")) == "pro":
                return {"state": "pro"}
            previous = raw.get("installer_version")
        else:
            if all(safe(root, rel).exists() for rel in ("00 - System", "AGENTS.md", "CONTEXT-POLICY.md")):
                raise Blocked("LEGACY_VERSION_UNKNOWN: locate the original installer record")
            return {"state": "obsidian" if safe(root, ".obsidian").is_dir() else "unrecognized"}
        if not previous:
            raise Blocked("LEGACY_VERSION_UNKNOWN: locate the original installer record")
        if previous not in RELEASE["supportedUpgradeVersions"]:
            raise Blocked("VERSION_UNSUPPORTED_OR_DOWNGRADE")
        current = managed and previous == RELEASE["starterKitVersion"]
        if current:
            for key in ("installerVersion", "kosContractVersion", "communityVersion"):
                if key == "communityVersion" and key not in record and version(previous) < (1, 3, 1):
                    continue  # This field was optional on historical managed receipts.
                if record.get(key) != RELEASE[key]:
                    raise Blocked("VERSION_RECORD_INCONSISTENT: " + key)
        check_last_run(root, RUNS, safe, json_read, Blocked)
        return {"state": "current" if current else "upgrade", "previous": previous,
                "previousCommunity": record.get("communityVersion") if managed else None}

    if mode == "validate":
        findings = validate_installation(root)
        return {"status": "FAIL" if any(f["severity"] == "error" for f in findings) else "PASS",
                "findings": findings}

    supplied = request["answers"]
    answers = answers_read(supplied)
    profile = answers["installation"].get("mode", "standard")
    args = (root, request["operation"], answers, profile, {})
    if "supplied_answers" in inspect.signature(plan).parameters:
        planned, payload = plan(*args, supplied_answers=supplied)
    else:
        planned, payload = plan(*args)
    if mode == "plan":
        return {"plan": planned}
    if mode != "apply" or hashlib.sha256(encoded(planned)).hexdigest() != request.get("approvedPlan"):
        raise Blocked("PLAN_CHANGED: review a fresh preview")
    # Only attribute a journal after this process acquires the transaction lock.
    own_run = []
    try:
        if "on_run" in inspect.signature(apply).parameters:
            run = apply(root, planned, payload, on_run=own_run.append)
        else:
            run = apply(root, planned, payload)
    except (OSError, ValueError, KeyError) as error:
        return {"error": str(error), "runId": own_run[0] if own_run else None}
    return {"runId": run}


if __name__ == "__main__":
    try:
        response = execute(json.load(sys.stdin.buffer))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError) as error:
        response = {"error": str(error)}
    sys.stdout.buffer.write(json.dumps(response, ensure_ascii=True).encode("ascii"))
