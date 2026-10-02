"""Journaled, hash-guarded writes and conservative recoverable rollback."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from safety import (Blocked, INSTALLATION, RUNS, current_hash, digest, durable,
                    encoded, inventory, json_read, relative, safe)


def markdown(plan: dict, status="PLANNED", run=None, findings=None) -> str:
    counts = {}
    for item in plan.get("items", []):
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    lines = ["# KOS operation report", "", f"Status: {status}",
             f"Operation: {plan['operation']}", f"Target type: {plan['targetType']}",
             f"Previous Starter Kit: {plan.get('previousVersion') or 'unknown'}",
             f"Resulting Starter Kit: {plan.get('resultingVersion') or 'unchanged'}",
             f"Edition: {plan.get('edition', 'community')}", "",
             f"Recovery: {plan.get('recovery', 'not requested')}",
             "Counts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), ""]
    for item in plan.get("items", []):
        lines.append(f"- `{item['path']}`: {item['classification']} / {item['action']}")
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
    lines.extend(["", "Validation: " + (", ".join(findings) if findings else "see status and classified items"),
                  f"Backup: {RUNS}/{run}/backup" if run else "Backup: none (no changes)",
                  f"Rollback: --operation rollback --run-id {run}" if run else "Rollback: not needed",
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


def rollback(root: Path, run: str, *, approve=False, dry_run=False) -> dict:
    if not isinstance(run, str) or len(run) != 32 or any(c not in "0123456789abcdef" for c in run):
        raise Blocked("RUN_ID_INVALID")
    journal_rel = RUNS + "/" + run + "/journal.json"
    journal = json_read(safe(root, journal_rel))
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
    if dry_run or not approve or not any(i["action"] == "RESTORE" for i in plan["items"]):
        return plan
    lock = safe(root, INSTALLATION + "/operation.lock", write=True)
    if lock.exists():
        raise Blocked("OPERATION_LOCKED: recovery requires explicit unlock after stopping the writer")
    with Transaction(root, plan) as tx:
        for item in sorted(plan["items"], key=lambda i: i["path"].endswith(("kos-installation.json", "skills.json", "power-ups.json", "packages.json", "capabilities.json"))):
            if item["action"] == "RESTORE":
                tx.write(item["path"], payload[item["path"]], item["currentHash"])
        tx.journal["recovery"] = plan["recovery"]
    return plan
