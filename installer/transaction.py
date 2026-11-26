"""Journaled, hash-guarded writes and conservative recoverable rollback."""
from __future__ import annotations

import os
import stat
import uuid
from pathlib import Path

from safety import (Blocked, INSTALLATION, RUNS, current_hash, digest, durable,
                    encoded, inventory, json_read, relative, safe)


def markdown(plan: dict, status="PLANNED", run=None) -> str:
    if plan.get("recovery") == "incomplete" and status in {"COMPLETE", "UNCHANGED"}:
        status = "INCOMPLETE"
    counts = {}
    for item in plan.get("items", []):
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    lines = ["# KOS Community operation report", "", f"Status: {status}",
             f"Operation: {plan['operation']}", f"Target type: {plan['targetType']}"]
    legacy = plan["targetType"] == "legacy-kos"
    previous_label = "Previous legacy installer version" if legacy else "Previous distribution version"
    for key, label in (("communityVersion", "KOS Community"),
                       ("previousCommunityVersion", "Previous KOS Community"),
                       ("installerVersion", "Installer version"),
                       ("previousVersion", previous_label),
                       ("resultingVersion", "Resulting distribution version"),
                       ("edition", "Edition")):
        if plan.get(key):
            lines.append(f"{label}: {plan[key]}")
        elif key in plan and (key == "communityVersion" or
                              key == "previousCommunityVersion" and plan.get("previousVersion")):
            lines.append(f"{label}: not recorded")
    lines.extend(["",
             f"Recovery: {plan.get('recovery', 'not requested')}",
             "Counts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), ""])
    for item in plan.get("items", []):
        summary = f"- `{item['path']}`: {item['classification']} / {item['action']}"
        if item.get("reason"):
            summary += ". " + item["reason"]
        lines.append(summary)
    for item in plan.get("links", []):
        lines.append(f"- Preserved link (not traversed): `{item}`")
    audit = plan.get("linkAudit")
    if audit:
        lines.append("Link audit: " + ", ".join(
            f"{label}={audit[key]}" for label, key in
            (("Markdown files", "scannedMarkdownFiles"), ("references", "references"),
             ("preexisting unresolved", "preexistingUnresolved"),
             ("preexisting ambiguous", "preexistingAmbiguous"))))
        lines.append(f"New basename collisions: {len(audit['newBasenameCollisions'])}; resolution regressions: {len(audit['regressions'])}")
        for item in audit["regressions"]:
            lines.append(f"- Link resolution regression: `{item['source']}` -> `{item['target']}`")
    if "findings" in plan:
        lines.append(f"Validation findings: {len(plan['findings'])}")
        for finding in plan["findings"]:
            lines.append(f"{finding['severity']} {finding['rule']}: {finding['path']}")
    if run:
        lines.extend(["", f"Backup: {RUNS}/{run}/backup", f"Rollback: --operation rollback --run-id {run}"])
    if status == "FAILED":
        lines.append("Inspect the operation journal before retrying.")
    if plan.get("requiredAction"):
        lines.append(plan["requiredAction"])
    lines.extend(["",
                  "User action: review preserved files, proposals and any BLOCK items before proceeding.",
                  "Diagnostics contain relative paths and rule identifiers; file contents are omitted."])
    return "\n".join(lines) + "\n"


class Transaction:
    def __init__(self, root: Path, plan: dict):
        self.root, self.plan = root, plan
        self.run = uuid.uuid4().hex
        self.rel = RUNS + "/" + self.run
        self.journal = {"schemaVersion": "1.0.0", "runId": self.run,
                        "status": "in-progress", "operation": plan["operation"],
                        "decisions": plan.get("decisions", {}), "entries": []}
        self.lock = None

    def save(self):
        path = safe(self.root, self.rel + "/journal.json", write=True)
        temp = safe(self.root, self.rel + "/journal.next", write=True)
        durable(temp, encoded(self.journal))
        os.replace(temp, path)

    def __enter__(self):
        control = safe(self.root, INSTALLATION, write=True)
        # Administrative bootstrap is the only write before the durable journal.
        # It creates directories, never changes existing content.
        control.mkdir(parents=True, exist_ok=True)
        self.lock = safe(self.root, INSTALLATION + "/operation.lock", write=True)
        try:
            durable(self.lock, encoded({"runId": self.run}), exclusive=True)
        except FileExistsError as exc:
            raise Blocked("OPERATION_LOCKED: inspect interrupted journal before recovery") from exc
        try:
            safe(self.root, self.rel).mkdir(parents=True, exist_ok=False)
            self.save()
            durable(safe(self.root, self.rel + "/plan.json"), encoded(self.plan), exclusive=True)
            return self
        except BaseException:
            self.lock.unlink()
            raise

    def write(self, rel: str, data: bytes | None, expected, *, ownership="managed"):
        relative(rel)
        path = safe(self.root, rel, write=True)
        if current_hash(self.root, rel) != expected:
            raise Blocked("TARGET_CHANGED_SINCE_PLAN")
        after = digest(data) if data is not None else None
        if expected == after:
            return
        entry = {"path": rel, "beforeHash": expected, "afterHash": after,
                 "ownership": ownership, "status": "intent"}
        self.journal["entries"].append(entry)
        self.save()  # Intent precedes backup AND destination write.
        if expected is not None:
            backup_rel = self.rel + "/backup/" + rel
            backup = safe(self.root, backup_rel, write=True)
            backup.parent.mkdir(parents=True, exist_ok=True)
            original = path.read_bytes()
            if digest(original) != expected:
                raise Blocked("TARGET_CHANGED_DURING_BACKUP")
            durable(backup, original, exclusive=True)
            entry["backup"] = backup_rel
            self.save()
        self.directory(path.parent.relative_to(self.root).as_posix())
        if current_hash(self.root, rel) != expected:
            raise Blocked("TARGET_CHANGED_BEFORE_WRITE")
        if data is None:
            path.unlink()
        elif expected is None:
            durable(path, data, exclusive=True)
        else:
            temp = safe(self.root, self.rel + "/replacement", write=True)
            durable(temp, data)
            safe(self.root, rel, write=True)
            os.replace(temp, path)
        entry["status"] = "written"
        self.save()

    def directory(self, rel: str):
        if rel == ".":
            return
        path = safe(self.root, rel, write=True)
        if path.exists():
            if not path.is_dir():
                raise Blocked("PATH_NOT_DIRECTORY")
            return
        self.directory(path.parent.relative_to(self.root).as_posix())
        entry = {"path": rel, "kind": "directory", "status": "intent"}
        self.journal["entries"].append(entry)
        self.save()
        path.mkdir()
        entry["status"] = "written"
        self.save()

    def __exit__(self, kind, error, trace):
        self.journal["status"] = "failed" if kind else "incomplete" if self.journal.get("recovery") == "incomplete" else "complete"
        self.save()
        report = markdown(self.plan, self.journal["status"].upper(), self.run)
        durable(safe(self.root, self.rel + "/report.md"), report.encode("utf-8"))
        if self.lock and self.lock.exists() and json_read(self.lock).get("runId") == self.run:
            self.lock.unlink()


def plan_rollback(root: Path, run: str):
    if not isinstance(run, str) or len(run) != 32 or any(c not in "0123456789abcdef" for c in run):
        raise Blocked("RUN_ID_INVALID")
    run_rel = RUNS + "/" + run
    run_dir = safe(root, run_rel)
    try:
        mode = run_dir.stat().st_mode
    except FileNotFoundError as error:
        raise Blocked("ROLLBACK_RUN_NOT_FOUND") from error
    if not stat.S_ISDIR(mode):
        raise Blocked("ROLLBACK_RUN_INVALID")
    journal_path = safe(root, run_rel + "/journal.json")
    try:
        journal = json_read(journal_path)
    except FileNotFoundError as error:
        raise Blocked("ROLLBACK_JOURNAL_MISSING") from error
    except OSError as error:
        raise Blocked("ROLLBACK_JOURNAL_UNREADABLE") from error
    except (UnicodeError, ValueError) as error:
        raise Blocked("ROLLBACK_JOURNAL_INVALID") from error
    if not isinstance(journal, dict) or not isinstance(journal.get("entries"), list):
        raise Blocked("ROLLBACK_JOURNAL_INVALID")
    if journal.get("runId") != run:
        raise Blocked("JOURNAL_ID_MISMATCH")
    plan = {"schemaVersion": "1.0.0", "operation": "rollback", "targetType": "managed-kos", "items": []}
    payload = {}
    # Preflight EVERY entry before restoring any. Evidence cannot redirect writes.
    for entry in reversed(journal["entries"]):
        rel = relative(entry["path"])
        if rel.startswith(RUNS + "/") or rel.endswith("operation.lock"):
            continue  # retain evidence and proposals
        if entry.get("kind") == "directory":
            continue  # empty directory skeletons are harmless; never recursive-delete
        if entry.get("kind") == "git":
            plan["items"].append({"path": rel, "action": "PRESERVE", "classification": "USER_MODIFIED", "currentHash": None})
            continue
        action, classification = "UNCHANGED", "IDENTICAL"
        try:
            actual = current_hash(root, rel)
            if actual == entry["beforeHash"]:
                pass
            elif actual != entry["afterHash"]:
                action, classification = "PRESERVE", "USER_MODIFIED"
            elif entry["beforeHash"] is None and entry.get("ownership") in {"user-owned", "runtime"}:
                action, classification = "PRESERVE", "USER_MODIFIED"
            else:
                if entry["beforeHash"] is not None:
                    backup_rel = RUNS + "/" + run + "/backup/" + rel
                    original = safe(root, backup_rel).read_bytes()
                    if digest(original) != entry["beforeHash"]:
                        raise Blocked("BACKUP_HASH_MISMATCH")
                    payload[rel] = original
                else:
                    payload[rel] = None
                action, classification = "RESTORE", "OLDER_MANAGED"
        except (OSError, ValueError):
            actual = None
            action, classification = "BLOCK", "SECURITY_CONFLICT"
        plan["items"].append({"path": rel, "action": action, "classification": classification, "currentHash": actual})
    incomplete = any(i["action"] in {"BLOCK", "PRESERVE"} for i in plan["items"])
    plan["recovery"] = "incomplete" if incomplete else "complete"
    # If any payload is preserved, do not revert registries/installation claims.
    if incomplete:
        for item in plan["items"]:
            if item["path"].endswith(("kos-installation.json", "skills.json", "power-ups.json", "packages.json", "capabilities.json")):
                item["action"] = "PRESERVE"
    return plan, payload


def apply_rollback(root, plan, payload):
    restores = [item for item in plan["items"] if item["action"] == "RESTORE"]
    if not restores:
        return None
    for item in restores:
        if current_hash(root, item["path"]) != item["currentHash"]:
            raise Blocked("TARGET_CHANGED_SINCE_PLAN")
    lock = safe(root, INSTALLATION + "/operation.lock", write=True)
    if lock.exists():
        raise Blocked("OPERATION_LOCKED: recovery requires explicit unlock after stopping the writer")
    with Transaction(root, plan) as tx:
        for item in sorted(restores, key=lambda i: i["path"].endswith(("kos-installation.json", "skills.json", "power-ups.json", "packages.json", "capabilities.json"))):
            tx.write(item["path"], payload[item["path"]], item["currentHash"])
        tx.journal["recovery"] = plan["recovery"]
    return tx.run


def rollback(root: Path, run: str, *, approve=False, dry_run=False) -> dict:
    plan, payload = plan_rollback(root, run)
    if approve and not dry_run:
        apply_rollback(root, plan, payload)
    return plan
