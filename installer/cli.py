"""Install, upgrade or validate a KOS Community workspace."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
import re
import sys
import subprocess
import zipfile
from pathlib import Path

from pro import pro_plan
from engine import answers_read, apply, detect, plan
from packages import plan_package
from safety import Blocked, ROOT, encoded, export_path, json_read, target_root
from transaction import apply_rollback, markdown, plan_rollback
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
    exports = OperationExports()
    applying = False
    applied = False
    try:
        if args.target is not None:
            root = target_root(args.target)
            exports.configure(root, args.plan_output, args.report)
        supplied_answers = json_read(args.answers) if args.answers else {}
        answers = answers_read(supplied_answers)
        if args.target is None:
            args.target = ROOT / answers["installation"]["target_directory"]
            root = target_root(args.target)
            exports.configure(root, args.plan_output, args.report)
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
                for idx, label in enumerate(["Create a new KOS Community installation", "Upgrade an existing KOS Community installation", "Enhance an existing Obsidian vault", "Learn about KOS Pro availability", "Validate a KOS Community installation", "Repair a KOS Community installation"], 1):
                    print(f"[{idx}] {label}")
                selection = int(input("Confirm operation [1-6]: "))
                if selection not in range(1, 7):
                    raise Blocked("OPERATION_INVALID")
                operation = options[selection - 1]
            operation = operation or "new"  # old answer-file clean-install invocation
            if operation == "validate":
                result = {"operation": "validate", "targetType": detect(root), "items": []}
                findings = validate_installation(root, installed_release=result)
                result["findings"] = findings
                result["status"] = "FAIL" if any(i["severity"] == "error" for i in findings) else "PASS"
                exports.plan(result)
                print(encoded(result).decode("utf-8"))
                return 2 if result["status"] == "FAIL" else 0
            if operation == "rollback":
                planned, payload = plan_rollback(root, args.run_id)
            elif operation in {"pro", "core"}:
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
                planned, payload = plan(root, operation, answers, profile, decisions, supplied_answers)
        exports.plan(planned)
        print(encoded(planned).decode("utf-8"))
        if args.dry_run or args.package_command in {"list", "validate"}:
            if planned.get("recovery") == "incomplete":
                return 4
            return 2 if planned.get("blocked") else 0
        approved = args.approve or (args.answers is not None and operation == "new")
        if not approved and sys.stdin.isatty():
            for classification in sorted({i["classification"] for i in planned["items"]}):
                print(classification + ": " + str(sum(i["classification"] == classification for i in planned["items"])))
            print("[1] Accept recommended safe actions\n[2] Review conflicts one by one\n[3] Review complete plan\n[4] Export plan without changes\n[5] Cancel")
            choice = input("Select [5]: ")
            if choice == "2" and not args.package_command and operation in {"new", "upgrade", "enhance", "repair"}:
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
                planned, payload = plan(root, operation, answers, profile, decisions, supplied_answers)
                exports.plan(planned)
                print(encoded(planned).decode("utf-8"))
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
            exports.report(planned, "APPROVAL REQUIRED")
            print("Approval required for writes: review plan, then pass --approve.")
            return 2
        applying = True
        apply_plan = apply_rollback if planned["operation"] == "rollback" else apply
        run = apply_plan(root, planned, payload)
        applied = True
        status = "COMPLETE" if run else "UNCHANGED"
        print(markdown(planned, status, run))
        exports.report(planned, status, run)
        return 4 if planned.get("recovery") == "incomplete" else 0
    except (Blocked, ValueError, KeyError, TypeError, IndexError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        rule = str(error).split(":")[0]
        if not re.fullmatch(r"[A-Z_]+", rule):
            rule = "INPUT_INVALID"
        blocked = {"operation": args.operation or args.package_command or "new", "targetType": "unsafe-or-invalid", "blocked": True,
                   "items": [{"path": "target", "classification": "BLOCKED", "action": "BLOCK", "rule": rule}]}
        if rule == "LEGACY_VERSION_UNKNOWN":
            blocked["targetType"] = "legacy-kos"
            blocked["requiredAction"] = (
                "The original installer-state.json has no verified installer_version. "
                "Recover the original record from a verified backup or request a manual migration review."
            )
        if rule == "FIXED_INSTALLATION_OPTION":
            field = "installation." + str(error).split(":", 1)[1]
            blocked["items"][0]["path"] = field
            blocked["requiredAction"] = f"Omit {field} from your answers or use its documented historical value in QUESTIONNAIRE.md."
        if rule == "ROLLBACK_RUN_NOT_FOUND":
            blocked["requiredAction"] = "Check the target vault and choose an existing run ID from its Installation/Runs directory."
        if rule in {"ROLLBACK_JOURNAL_MISSING", "ROLLBACK_JOURNAL_INVALID", "ROLLBACK_JOURNAL_UNREADABLE"}:
            blocked["requiredAction"] = "Inspect the existing run directory and recover its journal from a verified backup before retrying."
        if applying:
            blocked["targetType"] = planned["targetType"]
            blocked["status"] = "FAILED"
            blocked["requiredAction"] = "Inspect the operation journal before retrying."
        print("BLOCKED: " + rule, file=sys.stderr)
        print(encoded(blocked).decode("utf-8"))
        try:
            if applying:
                exports.report(blocked, "FAILED")
            elif rule != "ROLLBACK_RUN_NOT_FOUND":
                exports.plan(blocked)
        except (OSError, ValueError, AttributeError):
            pass  # Never overwrite a report or relax an unsafe output boundary.
        return 3 if rule == "ROLLBACK_JOURNAL_UNREADABLE" else 2
    except (OSError, subprocess.CalledProcessError):
        if applied:
            message = "The operation finished but writing the requested output failed. Inspect its journal and report before retrying."
        elif applying:
            message = "The operation failed during apply. Inspect the journal before retrying."
            try:
                exports.report(planned, "FAILED")
            except OSError:
                pass
        else:
            message = "The installer did not start applying changes."
        print("ERROR: IO_FAILURE. " + message, file=sys.stderr)
        return 3
    finally:
        exports.close()


def export(path, data, root):
    destination = export_path(path, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(data)


class OperationExports(ExitStack):
    """Reserve both new files before applying and update only our open handles."""

    def __init__(self):
        super().__init__()
        self.plan_stream = self.report_stream = None
        self.destinations = None

    def configure(self, root, plan_path, report_path):
        plan = export_path(plan_path, root) if plan_path else None
        report = export_path(report_path, root) if report_path else None
        if plan and report and (plan == report or plan in report.parents or report in plan.parents):
            raise Blocked("REPORT_DESTINATION_CONFLICT")
        self.destinations = (plan, report)

    def reserve(self):
        if self.destinations is None:
            return
        plan, report = self.destinations
        self.destinations = None
        def reserve(path):
            if path is None:
                return None
            path.parent.mkdir(parents=True, exist_ok=True)
            return self.enter_context(path.open("xb"))

        first = reserve(plan)
        try:
            self.report_stream = reserve(report)
        except OSError:
            if first:
                own_file = os.fstat(first.fileno())
                first.close()
                try:
                    if os.path.samestat(own_file, plan.lstat()):
                        plan.unlink()
                except OSError:
                    pass  # Preserve the original reservation failure.
            raise
        self.plan_stream = first

    @staticmethod
    def write(stream, data):
        if stream:
            stream.seek(0)
            stream.write(data)
            stream.truncate()
            stream.flush()

    def plan(self, record):
        self.reserve()
        self.write(self.plan_stream, encoded(record))
        self.report(record, record.get("status", "BLOCKED" if record.get("blocked") else "PLANNED"))

    def report(self, record, status, run=None):
        if self.report_stream:
            self.write(self.report_stream, markdown(record, status, run).encode("utf-8"))
