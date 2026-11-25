#!/usr/bin/env python3
"""Initialize, review and search the context of one selected KOS project."""
import sys

# The installed command also runs in read-only vaults. Keep imports write-free.
sys.dont_write_bytecode = True

import argparse
import json
import re
from pathlib import Path

import project_lifecycle as lifecycle
import project_sources as sources


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=Path.cwd(), help="installed vault (default: current directory)")
    parser.add_argument("--project", required=True, help="one folder name under 02 - Projects/Active")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create missing draft project records")
    commands.add_parser("review", help="inspect current files, classifications and review token")
    approve = commands.add_parser("approve", help="approve the exact context pair you reviewed")
    approve.add_argument("--review-token", required=True)
    approve.add_argument("--classify-unmarked", action="store_true",
                         help="explicitly classify the reviewed, unmarked legacy context notes as internal")
    commands.add_parser("check", help="check whether the current pair is approved")
    commands.add_parser("context", help="read the approved project memory and handoff")
    for name, summary in (("sources", "inspect the selected sources and their revisions"),
                          ("search", "find literal text and return source lines")):
        command = commands.add_parser(name, help=summary)
        command.add_argument("--source", action="append", default=[], metavar="FILE",
                             help="project-relative Markdown file, repeat for each selected file")
        command.add_argument("--max-files", type=int, default=32)
        if name == "search":
            command.add_argument("--query", required=True)
            command.add_argument("--max-results", type=int, default=30)
    return parser.parse_args(argv)


def run(args):
    project = lifecycle.project_path(args.vault, args.project)
    if args.command == "init":
        return explain(lifecycle.initialize(project), args.vault)
    if args.command == "review":
        return explain(lifecycle.review(project), args.vault)
    if args.command == "approve":
        return lifecycle.approve(project, args.review_token, args.classify_unmarked)
    if args.command == "check":
        return explain(lifecycle.check(project), args.vault)
    if args.command == "context":
        return lifecycle.read_context(project)

    before = lifecycle.check(project)
    if before["status"] != "active":
        if before["status"] == "stale":
            names = ", ".join(entry["path"] for entry in before.get("changed_files") or [])
            detail = f"Edited: {names}. " if names else ""
            raise ValueError(detail + "Run review to compare the current project with its approved local original.")
        raise ValueError("Review and approve the current project context before selecting sources.")
    options = {"max_files": args.max_files, "vault": args.vault}
    if args.command == "sources":
        result = sources.inspect_sources(project, args.source, **options)
    else:
        result = sources.search_sources(project, args.source, args.query, max_results=args.max_results, **options)
    after = lifecycle.check(project)
    if after["status"] != "active" or after["review_token"] != before["review_token"]:
        raise ValueError("Project context changed during retrieval. Review the current pair and retry.")
    return result


def _instruction_lines(markdown):
    """Yield active prose outside HTML comments and Markdown fence examples."""
    markdown = re.sub(r"<!--.*?(?:-->|$)", "", markdown, flags=re.S)
    fence = ""
    for line in markdown.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
        elif marker and (marker[1][0] == "~" or "`" not in marker[2]):
            fence = marker[1]
        else:
            yield line


def routing_status(vault):
    manifest = "00 - System/Config/ai-context-manifest.yaml"
    pending = []
    for path in ("AGENTS.md", "CONTEXT-POLICY.md", manifest):
        try:
            current = lifecycle.read_file(lifecycle.safe_path(vault, path), 64 * 1024).decode("utf-8-sig")
        except (OSError, ValueError):
            current = ""
        if path == manifest:
            lines = [line.split("#", 1)[0].rstrip() for line in current.splitlines()]
            indices = [i for i, line in enumerate(lines) if re.match(r"^project_loaded\s*:", line)]
            ready = len(indices) == 1
            if ready:
                index = indices[0]
                following = next((line for line in lines[index + 1:] if line.strip()), "")
                ready = (bool(re.fullmatch(r"project_loaded\s*:\s*\[\s*\]", lines[index]))
                         and (not following or re.match(r"^[\w-]+\s*:", following) is not None))
        elif path == "AGENTS.md":
            routes = [line for line in _instruction_lines(current) if line.startswith("- Active project:")]
            ready = (len(routes) == 1 and "project_context.py" in routes[0]
                     and "--project" in routes[0] and " context`" in routes[0]
                     and "PROJECT-CONTEXT.md" not in routes[0])
        else:
            ready = any(line.startswith("For an active project, load the approved pair through the installed project context tool.")
                        and "owner review before retrieval" in line for line in _instruction_lines(current))
        if not ready:
            pending.append({"path": path, "proposal": f"00 - System/Installation/Runs/<upgrade-run>/proposals/{path}"})
    return {"status": "adoption_pending" if pending else "ready", "pending": pending}


def explain(result, vault):
    steps = {
        "draft": "Open memory.md and handoff.md, review the pair, then approve the displayed review token.",
        "stale": "See changed_files. Run review to load the approved local original and compare edits before approving the new pair.",
        "blocked": "Inspect the files list for missing records, access classifications or exclusions.",
        "active": "Use context for the approved pair, or search with explicitly selected source files.",
    }
    result["next_action"] = steps[result["status"]]
    changed = result.get("changed_files") or []
    if result["status"] == "stale" and changed:
        names = ", ".join(item["path"] for item in changed)
        result["message"] = f"Edited since approval: {names}."
        if result.get("review_token"):
            result["next_action"] = "Compare the saved original and diff. Approve this review token to accept the edits, or revise the notes and review again."
    result["routing"] = routing_status(vault)
    if result["routing"]["pending"]:
        result["routing_warnings"] = [
            f"Review {item['path']} and merge the approved routing rule from {item['proposal']} if available."
            for item in result["routing"]["pending"]]
    return result


def main(argv=None):
    args = arguments(argv)
    try:
        result = run(args)
    except (ValueError, OSError) as exc:
        message = exc.strerror if isinstance(exc, OSError) else str(exc)
        print(json.dumps({"status": "blocked", "error": message}))
        return 2
    print(json.dumps(result, indent=2))
    if result.get("status") == "blocked" or (
            args.command in ("check", "approve", "context") and result.get("status") != "active"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
