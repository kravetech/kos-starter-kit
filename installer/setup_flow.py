"""Approved, rehearsed Community installs and updates. No user extension is executed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from safety import Blocked, RUNS, STATE, digest, durable, encoded, json_read, merge_existing, safe, target_root
from setup_audit import capture_audit, compare_audits, plan_guard
from setup_backup import create_recovery, propose_recovery, snapshot


def worker(package, vault, mode, **params):
    request = {"package": str(package), "vault": str(vault), "mode": mode, **params}
    process = subprocess.run(
        [sys.executable, "-I", "-B", str(Path(__file__).with_name("setup_worker.py"))],
        input=encoded(request), capture_output=True, cwd=package,
    )
    if process.returncode:
        raise Blocked("The verified installer stopped unexpectedly. Inspect its local run journal.")
    result = json.loads(process.stdout)
    if result.get("error") and mode != "apply":
        raise Blocked(result["error"])
    return result


def show_plan(plan):
    return {action: [item["path"] for item in plan["items"] if item["action"] == action]
            for action in sorted({item["action"] for item in plan["items"]} - {"UNCHANGED"})}


def preview(package, vault, operation, answers, audit=None):
    plan = worker(package, vault, "plan", operation=operation, answers=answers)["plan"]
    blockers = [f"{item['path']} ({item.get('rule', item['classification'])})"
                for item in plan["items"] if item["action"] == "BLOCK"]
    if audit is not None:
        blockers.extend(plan_guard(vault, plan, audit))
    if plan["blocked"] or blockers:
        raise Blocked("Plan requires review: " + ", ".join(blockers))
    return plan


def confirm(question, details):
    print("\n" + question)
    while True:
        try:
            answer = input("Enter yes, no, or details [no]: ").strip().lower()
        except EOFError:
            return False
        if answer == "details":
            print(json.dumps(details, indent=2, ensure_ascii=True))
        elif answer in {"yes", "y"}:
            return True
        elif answer in {"no", "n", ""}:
            return False


def new_answers(supplied, adapter):
    # Avoid seeding an example person's identity into the user's workspace.
    defaults = {"user": {"preferred_name": "Vault owner", "author_name": "Vault owner",
                         "technical_username": "owner"}}
    if adapter is not None:
        defaults["installation"] = {"providers": [adapter] if adapter != "none" else []}
    return merge_existing(defaults, supplied)


def journal_summary(vault, run_id, plan):
    rel = f"{RUNS}/{run_id}"
    journal = json_read(safe(vault, rel + "/journal.json"))
    if journal["runId"] != run_id or journal["operation"] != plan["operation"]:
        raise Blocked("Unexpected journal identity. Inspect the run folder.")
    changes = {"created": [], "updated": [], "removed": [], "proposals": [], "preserved": [], "pending": []}
    for entry in journal["entries"]:
        path = entry["path"]
        if entry.get("kind") == "directory" and (path == rel or path.startswith(rel + "/")):
            continue  # Run evidence directories are not user-facing vault additions.
        if entry["status"] != "written":
            changes["pending"].append(path)
        elif path.startswith(rel + "/proposals/"):
            changes["proposals"].append(path[len(rel + "/proposals/"):])
        elif entry.get("kind") in {"directory", "git"} or entry.get("beforeHash") is None:
            changes["created"].append(path)
        elif entry.get("afterHash") is None:
            changes["removed"].append(path)
        else:
            changes["updated"].append(path)
    changes["preserved"] = [i["path"] for i in plan["items"] if i["action"] in {"PRESERVE", "PROPOSE", "SKIP"}
                            or (i["classification"] == "USER_MODIFIED" and i["action"] == "UNCHANGED")]
    return {"transactionStatus": journal["status"], "changes": changes,
            "journal": str(safe(vault, rel + "/journal.json")), "operationReport": str(safe(vault, rel + "/report.md"))}


def apply_reviewed(release, vault, plan, answers, before_audit, backup, stage, emit, release_changes=None):
    emit("Applying approved plan", {"stage": stage, "vault": str(vault),
                                    "journalDirectory": str(vault / RUNS),
                                    "backup": str(backup) if backup else None})
    applied = worker(release.root, vault, "apply", operation=plan["operation"], answers=answers,
                     approvedPlan=digest(encoded(plan)))
    run_id = applied.get("runId")
    report = {"stage": stage, "vault": str(vault), "edition": "Community", "runId": run_id,
              "previousDistribution": plan.get("previousVersion"), "previousCommunity": plan.get("previousCommunityVersion"),
              "targetDistribution": release.version, "targetCommunity": release.community_version,
              "backup": str(backup) if backup else None, "lastCompletedStep": "approved preview"}
    if release_changes is not None:
        report["releaseChanges"] = release_changes
    if not run_id:
        report.update(status="failed", error=applied.get("error") or "Installer returned no run ID",
                      journalDirectory=str(vault / RUNS))
        emit("Run result", report)
        raise Blocked(report["error"])
    where = safe(vault, f"{RUNS}/{run_id}/setup-summary.json", write=True)
    try:
        report.update(journal_summary(vault, run_id, plan))
        if applied.get("error") or report["transactionStatus"] != "complete":
            raise Blocked(applied.get("error") or "Incomplete transaction")
        report["lastCompletedStep"] = "installer transaction"
        report["validation"] = worker(release.root, vault, "validate")
        if report["validation"]["status"] != "PASS":
            raise Blocked("Installation validation failed.")
        report["lastCompletedStep"] = "installation validation"
        if before_audit is not None:
            report["audit"] = compare_audits(before_audit, capture_audit(vault), plan)
            if report["audit"]["blockers"]:
                raise Blocked("Vault compatibility checks failed: " + ", ".join(report["audit"]["blockers"]))
            report["lastCompletedStep"] = "link and extension checks"
        else:
            initial = capture_audit(vault)
            links = compare_audits(initial, initial)["links"]
            report["initialLinks"] = {"references": links["references"], "unresolved": links["preexisting"],
                                      "unverified": links["unverified"]}
        receipt = json_read(safe(vault, STATE))
        report["installedCommunity"] = receipt.get("communityVersion")
        report["installedDistribution"] = receipt["starterKitVersion"]
        report["enabledAdapters"] = receipt.get("providers", [])
        if receipt["starterKitVersion"] != release.version:
            raise Blocked("Installed version does not match the selected release.")
        report["status"] = "complete"
        if plan["operation"] == "new":
            report["firstAction"] = "Open the vault in your Markdown editor and read README.md."
    except (OSError, ValueError, KeyError) as error:
        report.update(status="failed", error=str(error))
    report["report"] = str(where)
    try:
        durable(where, encoded(report), exclusive=True)
    except OSError as error:
        report.pop("report")
        emit("Run result", report)
        raise Blocked("Could not save the setup summary. See the transaction journal above.") from error
    emit("Run result", report)
    if report["status"] != "complete":
        raise Blocked(report["error"])
    return report


def describe_preview(vault, plan, emit):
    items = show_plan(plan)
    summary = {"vault": str(vault), "actionCounts": {key: len(paths) for key, paths in items.items()}}
    if plan["operation"] == "upgrade":
        summary["examples"] = {key: paths[:3] for key, paths in items.items()}
    else:
        summary["topLevelAdditions"] = sorted({path.split("/")[0] for paths in items.values() for path in paths})
    if plan.get("postActions"):
        summary["postActions"] = plan["postActions"]
    emit("Planned changes", summary)


def setup(release, vault, *, supplied=None, adapter=None, recovery_parent=None, check_only=False, ask=confirm, emit=print):
    vault = target_root(vault)
    identity = worker(release.root, vault, "identify")
    state = identity["state"]
    emit("Community setup", {"vault": str(vault), "state": state, "selectedCommunity": release.community_version,
                             "selectedDistribution": release.version, **identity})
    guidance = {"pro": "Use the Pro installer for this vault.",
                "obsidian": "Use the Obsidian enhancement guide for this existing vault.",
                "unrecognized": "Select a recognized vault or a new or empty folder."}
    if state in guidance:
        raise Blocked(guidance[state])
    if check_only:
        if state not in {"current", "upgrade"}:
            raise Blocked("Choose an existing Community vault to check.")
        validation = worker(release.root, vault, "validate")
        audit = capture_audit(vault)
        result = compare_audits(audit, audit)
        links = result["links"]
        emit("Vault check", {"vault": str(vault), "validation": validation,
                            "unresolvedLinks": links["preexisting"], "unverifiedLinks": links["unverified"],
                            "extensionIssues": result["blockers"], "warnings": result["warnings"],
                            "registeredExtensions": result["extensions"]["registeredIds"],
                            "portableExtensions": result["extensions"]["portablePaths"]})
        if validation["status"] != "PASS" or result["blockers"] or links["preexisting"]:
            return "review needed"
        return "checked"
    if state == "current":
        return "current"
    supplied = supplied or {}
    baseline = snapshot(vault)
    if state == "new":
        answers = new_answers(supplied, adapter)
        defaults = merge_existing(json_read(release.root / "installer/defaults.json"), answers)
        emit("Proposed settings", {"workspace": defaults["system"]["name"], "owner": defaults["user"]["preferred_name"],
                                   "adapters": defaults["installation"]["providers"], "privacy": defaults["privacy"],
                                   "initializeGit": defaults["installation"].get("initialize_git", False)})
        plan = preview(release.root, vault, "new", answers)
        describe_preview(vault, plan, emit)
        if not ask("Install KOS here?", show_plan(plan)):
            return "cancelled"
        if snapshot(vault) != baseline:
            raise Blocked("The destination changed. Run setup again to review it.")
        apply_reviewed(release, vault, plan, answers, None, None, "install", emit)
        return "installed"

    if state != "upgrade":
        raise Blocked("Unknown vault state.")
    before = capture_audit(vault)
    plan = preview(release.root, vault, "upgrade", supplied, before)
    if plan.get("previousVersion") != identity["previous"]:
        raise Blocked("The installation identity changed. Review the vault again.")
    notes = release.changes_since(identity["previous"])
    emit("Changes between releases", notes)
    describe_preview(vault, plan, emit)
    run_root = propose_recovery(vault, recovery_parent)
    paths = {"original": str(vault), "backup": str(run_root / "backup"), "testCopy": str(run_root / "test-copy")}
    emit("Proposed recovery locations", paths)
    if not ask("Close editors and pause sync. Use these locations for a verified backup and rehearsal? "
               "To choose another location, cancel and use --recovery-parent.", {**paths, "plan": show_plan(plan)}):
        return "cancelled"
    try:
        backup, copy = create_recovery(vault, run_root, baseline)
    except (OSError, ValueError) as error:
        emit("Recovery preparation stopped", {"original": str(vault), "recoveryDirectory": str(run_root),
                                             "lastCompletedStep": "approved recovery locations",
                                             "error": str(error)})
        raise
    emit("Verified backup", {"backup": str(backup), "rehearsal": str(copy)})
    rehearsal = preview(release.root, copy, "upgrade", supplied, before)
    if rehearsal != plan:
        raise Blocked("The rehearsal preview differs from the approved changes. Original vault untouched.")
    result = apply_reviewed(release, copy, rehearsal, supplied, before, backup, "rehearsal", emit, notes)
    if snapshot(vault) != baseline or snapshot(backup) != baseline:
        raise Blocked("The original or backup changed. Run setup again for a fresh backup and rehearsal.")
    live = preview(release.root, vault, "upgrade", supplied, before)
    if live != rehearsal:
        raise Blocked("The original plan differs from the tested plan. Run setup again.")
    describe_preview(vault, live, emit)
    if not ask("Apply this tested update to the original vault?", {"vault": str(vault), "plan": show_plan(live),
                                                                  "rehearsalReport": result["report"]}):
        return "rehearsed"
    if snapshot(vault) != baseline or snapshot(backup) != baseline:
        raise Blocked("The vault or backup changed during approval. Run setup again.")
    apply_reviewed(release, vault, live, supplied, before, backup, "update", emit, notes)
    return "updated"


def console(label, data):
    # Keep the terminal readable. Full file lists and checks stay in the local report.
    print("\n" + label)
    if label == "Changes between releases":
        for section in data:
            print("  " + section["version"])
            for change in section["changes"]:
                print("    - " + change)
            if not section["complete"]:
                print("    Release notes are incomplete for this version.")
        return
    if label == "Run result":
        data = dict(data)
        first_action = data.pop("firstAction", None)
        validation = data.get("validation", {})
        if validation.get("status") == "PASS":
            findings = validation.get("findings", [])
            data["validation"] = {"status": "PASS", "findings": len(findings)}
        if "releaseChanges" in data:
            data["releasesCovered"] = [s["version"] for s in data.pop("releaseChanges")]
        audit = data.get("audit")
        if audit and not audit["blockers"]:
            extensions = audit["extensions"]
            data["audit"] = {"protectedFilesChecked": audit["protectedFilesChecked"],
                             "preservedRegisteredIds": extensions["preservedRegisteredIds"][:5],
                             "preservedPortablePaths": extensions["preservedPortablePaths"][:5],
                             "totalPreservedPortablePaths": len(extensions["preservedPortablePaths"]),
                             "linkRegressions": len(audit["links"]["regressions"]),
                             "preexistingLinkIssues": len(audit["links"]["preexisting"]),
                             "unverifiedLinks": len(audit["links"]["unverified"]),
                             "warnings": audit["warnings"][:8], "totalWarnings": len(audit["warnings"])}
        changes = data.pop("changes", {})
        if changes:
            for key, paths in changes.items():
                if paths:
                    shown = paths[:8]
                    extra = f" (+{len(paths) - len(shown)} in report)" if len(paths) > len(shown) else ""
                    print(f"  {key} ({len(paths)}): " + ", ".join(shown) + extra)
    for key, value in data.items():
        if value is not None:
            print(f"  {key}: " + (json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value)))
    if label == "Run result" and first_action:
        print("  Next: " + first_action)


def suggested_vault():
    current = Path.cwd()
    if current not in {Path(__file__).resolve().parents[1], Path.home(), Path(current.anchor)}:
        return current
    for index in range(1, 1000):
        suffix = "" if index == 1 else f" {index}"
        candidate = Path.home() / ("My KOS" + suffix)
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise Blocked("Choose a new or empty folder with --target.")


def main(argv=None):
    from setup_release import COMMUNITY_URL, open_release

    parser = argparse.ArgumentParser(description="Install or update a KOS Community vault using its official release.")
    parser.add_argument("source", nargs="?", default=COMMUNITY_URL, help="Official Community repository URL or local release ZIP")
    parser.add_argument("--target", type=Path, help="Vault to inspect (default: current folder, or suggest My KOS from the installer)")
    parser.add_argument("--recovery-parent", type=Path, help="Private parent folder for a new backup and rehearsal")
    parser.add_argument("--answers", type=Path, help="Existing private answers file")
    parser.add_argument("--adapter", choices=["codex", "claude", "gemini", "none"], help="Fresh-install adapter preference")
    parser.add_argument("--check", action="store_true", help="Check a recognized vault without applying any changes")
    args = parser.parse_args(argv)
    try:
        vault = target_root(args.target.expanduser() if args.target else suggested_vault())
        answers = json_read(args.answers) if args.answers and not args.check else {}
        with open_release(args.source) as release:
            outcome = setup(release, vault, supplied=answers, adapter=args.adapter, recovery_parent=args.recovery_parent,
                            check_only=args.check, emit=console)
        print("\n" + outcome.capitalize() + ".")
        return 2 if outcome == "review needed" else 0
    except KeyboardInterrupt:
        print("Interrupted. Inspect any reported run journal before retrying.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Setup stopped: " + str(error), file=sys.stderr)
        return 2
