"""Public CLI: explicit operation, deterministic plan, approval, transaction."""
from __future__ import annotations

import argparse
import json
import re
import sys
import subprocess
import zipfile
from pathlib import Path

from pro import pro_plan
from engine import answers_read, apply, detect, plan
from packages import plan_package
from safety import Blocked, ROOT, encoded, json_read, safe, target_root
from transaction import markdown, rollback
from validation import validate_installation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--operation", choices=["new", "upgrade", "enhance", "pro", "core", "validate", "repair", "rollback"])
    parser.add_argument("--mode", choices=["lean", "standard", "business", "developer", "creator", "custom", "migration", "minimal", "complete"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--migration", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-overwrite", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--plan-output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--package-command", choices=["validate", "install", "list", "enable", "disable", "update", "rollback", "uninstall"])
    parser.add_argument("--package", type=Path)
    parser.add_argument("--id")
    parser.add_argument("--version")
    parser.add_argument("--trust", type=Path)
    parser.add_argument("--approve-permissions", action="store_true")
    args = parser.parse_args(argv)
    try:
        answers = answers_read(json_read(args.answers) if args.answers else json_read(ROOT / "installer/defaults.json"))
        if args.target is None:
            args.target = ROOT / answers["installation"]["target_directory"]
        root = target_root(args.target)
        if args.allow_overwrite:
            raise Blocked("GLOBAL_OVERWRITE_FORBIDDEN")
        if args.resume:
            raise Blocked("RESUME_REQUIRES_JOURNAL_REVIEW: rollback the interrupted run then replan")
        operation = args.operation or answers["installation"].get("operation")
        if args.migration or args.mode == "migration":
            operation = "upgrade" if detect(root) in {"managed-kos", "legacy-kos"} else "enhance"
        if args.package_command:
            planned, payload = plan_package(root, args.package_command, args.package, args.id, args.version, args.trust, args.approve_permissions)
        else:
            if operation is None and args.answers is None and sys.stdin.isatty():
                detected = detect(root)
                recommended = {"new-target": "new", "empty-directory": "new", "managed-kos": "upgrade", "legacy-kos": "upgrade", "obsidian-vault": "enhance"}.get(detected, "review target manually")
                print("Detected: " + detected + "; recommended: " + recommended)
                options = ["new", "upgrade", "enhance", "pro", "validate", "repair"]
                for idx, label in enumerate(["Create a new KOS Community installation", "Upgrade an existing KOS Community installation", "Enhance an existing Obsidian vault", "Learn about KOS Pro availability", "Validate an existing installation", "Repair an existing KOS"], 1):
                    print(f"[{idx}] {label}")
                selection = int(input("Confirm operation [1-6]: "))
                if selection not in range(1, 7):
                    raise Blocked("OPERATION_INVALID")
                operation = options[selection - 1]
            operation = operation or "new"  # old answer-file clean-install invocation
            if operation == "validate":
                findings = validate_installation(root)
                result = {"operation": "validate", "targetType": detect(root), "items": [], "findings": findings}
                output(result, args)
                return 2 if any(i["severity"] == "error" for i in findings) else 0
            if operation == "rollback":
                result = rollback(root, args.run_id, approve=args.approve, dry_run=args.dry_run)
                output(result, args)
                return 4 if result["recovery"] == "incomplete" else 0
            if operation in {"pro", "core"}:
                planned, payload = pro_plan(root, args.package), {}
            else:
                profile = args.mode or answers["installation"].get("mode", "standard")
                if profile == "migration":
                    profile = "standard"
                if operation == "enhance" and args.mode is None:
                    profile = "minimal"
                    if sys.stdin.isatty() and not args.dry_run and not args.approve and args.answers is None:
                        print("[1] Minimal KOS layer\n[2] Complete KOS architecture")
                        selection = input("Profile [1]: ")
                        if selection not in {"", "1", "2"}:
                            raise Blocked("PROFILE_INVALID")
                        profile = "complete" if selection == "2" else "minimal"
                decisions = json_read(args.decisions) if args.decisions else {}
                planned, payload = plan(root, operation, answers, profile, decisions)
        output(planned, args)
        if args.dry_run or args.package_command in {"list", "validate"}:
            return 2 if planned.get("blocked") else 0
        approved = args.approve or (args.answers is not None and operation == "new")
        if not approved and sys.stdin.isatty():
            for classification in sorted({i["classification"] for i in planned["items"]}):
                print(classification + ": " + str(sum(i["classification"] == classification for i in planned["items"])))
            print("[1] Accept recommended safe actions\n[2] Review conflicts one by one\n[3] Review complete plan\n[4] Export plan without changes\n[5] Cancel")
            choice = input("Select [5]: ")
            if choice == "2" and not args.package_command:
                decisions = dict(planned.get("decisions", {}))
                for item in planned["items"]:
                    if item["classification"] in {"USER_MODIFIED", "SEMANTIC_DUPLICATE"}:
                        print(item["path"] + ": " + item["classification"])
                        options = ["keep", "propose", "skip"]
                        if item["classification"] == "SEMANTIC_DUPLICATE":
                            options = ["keep", "adopt", "skip"]
                        if item.get("ownership") in {"managed", "managed-customizable"}:
                            options.append("replace")
                        selected = input("Action (" + "/".join(options) + ", default keep): ") or "keep"
                        if selected not in options:
                            raise Blocked("DECISION_INVALID")
                        decisions[item["path"]] = selected
                planned, payload = plan(root, operation, answers, profile, decisions)
                output(planned, args)
                approved = input("Approve this revised plan? [yes/no]: ") == "yes"
            elif choice == "1":
                approved = True
            elif choice == "3":
                print(markdown(planned))
            elif choice == "4":
                destination = Path(input("Export destination outside target: "))
                export(destination, encoded(planned), root)
        if planned.get("blocked"):
            return 2
        if not approved:
            print("Approval required for writes: review plan, then pass --approve.")
            return 2
        run = apply(root, planned, payload)
        print(markdown(planned, "COMPLETE" if run else "UNCHANGED", run))
        return 0
    except (Blocked, ValueError, KeyError, TypeError, IndexError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        rule = str(error).split(":")[0]
        if not re.fullmatch(r"[A-Z_]+", rule):
            rule = "INPUT_INVALID"
        blocked = {"operation": args.operation or args.package_command or "new", "targetType": "unsafe-or-invalid", "blocked": True,
                   "items": [{"path": "target", "classification": "BLOCKED", "action": "BLOCK", "rule": rule}]}
        print("BLOCKED: " + rule, file=sys.stderr)
        try:
            output(blocked, args)
        except (OSError, ValueError, AttributeError):
            pass  # Never overwrite a report or relax an unsafe output boundary.
        return 2
    except (OSError, subprocess.CalledProcessError):
        print("ERROR: IO_FAILURE; inspect the operation journal before retrying.", file=sys.stderr)
        return 3


def export(path, data, root):
    destination = path.absolute()
    safe(destination.parent, destination.name, write=True)
    if destination == root or root in destination.parents:
        raise Blocked("DRY_RUN_EXPORT_MUST_BE_OUTSIDE_TARGET")
    if destination.exists():
        raise Blocked("REPORT_DESTINATION_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(data)


def output(planned, args):
    print(encoded(planned).decode("utf-8"))
    if args.plan_output:
        export(args.plan_output, encoded(planned), args.target.absolute())
        args.plan_output = None
    if args.report:
        report = markdown(planned, "BLOCKED" if planned.get("blocked") else "PLANNED", findings=[i["rule"] for i in planned.get("findings", [])])
        export(args.report, report.encode("utf-8"), args.target.absolute())
        args.report = None
