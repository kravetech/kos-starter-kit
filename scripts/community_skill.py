#!/usr/bin/env python3
"""Prepare a project action list for one provider or save its verified result locally."""
import sys

sys.dont_write_bytecode = True

import argparse
import json
import os
from pathlib import Path
import re
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "installer"))
import packages
from contracts import check as validate_document
from safety import Blocked, digest, encoded, json_loads
import project_lifecycle as lifecycle
import project_sources as sources


PROVIDERS = ("gemini", "claude", "codex")
READ_PERMISSION = "read:selected-project-sources"
WRITE_PERMISSION = "write:project-result"
MAX_ACTION_LENGTH = 1024
MAX_RESPONSE_BYTES = 1024 * 1024


def read_asset(root, path, limit=64 * 1024):
    return lifecycle.read_file(lifecycle.safe_path(root, path), limit)


def resolve(vault, project, package_id):
    """Resolve data from both immutable registries without executing package code."""
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*", package_id):
        raise Blocked("POWERUP_ID_INVALID")
    activation_path = lifecycle.safe_path(project, "power-ups.json")
    if not activation_path.is_file():
        raise Blocked("PROJECT_POWERUP_OPT_IN_REQUIRED")
    activation = json_loads(lifecycle.read_file(activation_path, 64 * 1024).decode("utf-8-sig"))
    validate_document("project-activation", activation)
    if activation["packages"].get(package_id, {}).get("enabled") is not True:
        raise Blocked("PROJECT_POWERUP_OPT_IN_REQUIRED")
    powerup = packages.resolve_powerup(vault, package_id, project.name)
    if not powerup["enabled"]:
        raise Blocked("POWERUP_DISABLED")
    registries = packages.registries(vault)
    record = registries[packages.REGISTRIES["powerup"]]["packages"][package_id]["versions"][powerup["version"]]
    manifest = record["manifest"]
    if (manifest["id"] != package_id or manifest["version"] != powerup["version"] or manifest["type"] != "powerup"
            or manifest["entrypoints"] != ["shared-skill.json"] or "shared-skill.json" not in manifest["integrity"]):
        raise Blocked("SHARED_SKILL_BINDING_REQUIRED")
    packages.verify_installed(vault, record)
    if READ_PERMISSION not in manifest["permissions"]:
        raise Blocked("POWERUP_READ_PERMISSION_REQUIRED")
    binding_bytes = read_asset(vault, record["path"] + "/shared-skill.json")
    if digest(binding_bytes) != manifest["integrity"]["shared-skill.json"]:
        raise Blocked("POWERUP_BINDING_CHANGED")
    binding = json_loads(binding_bytes.decode("utf-8-sig"))
    if (not isinstance(binding, dict) or not all(isinstance(binding.get(key), str)
            for key in ("skillId", "version", "entrypoint", "sha256"))
            or binding["entrypoint"] != "SKILL.md"
            or manifest["dependencies"].get(binding["skillId"]) != binding["version"]):
        raise Blocked("SHARED_SKILL_BINDING_INVALID")
    by_id = {key: value for registry in registries.values() for key, value in registry["packages"].items()}
    packages.dependencies(manifest, by_id)
    entry = registries[packages.REGISTRIES["skill"]]["packages"].get(binding["skillId"])
    if not entry or not entry["enabled"] or entry["activeVersion"] != binding["version"]:
        raise Blocked("SHARED_SKILL_INACTIVE_OR_VERSION_CHANGED")
    skill = entry["versions"][binding["version"]]
    packages.verify_installed(vault, skill)
    skill_manifest = skill["manifest"]
    if (skill_manifest["type"] != "skill" or skill_manifest["id"] != binding["skillId"]
            or skill_manifest["version"] != binding["version"] or skill_manifest.get("entrypoint") != "SKILL.md"
            or skill_manifest["integrity"].get("SKILL.md") != binding["sha256"]):
        raise Blocked("SHARED_SKILL_IDENTITY_CHANGED")
    path = skill["path"] + "/SKILL.md"
    instructions = read_asset(vault, path)
    if digest(instructions) != binding["sha256"]:
        raise Blocked("SHARED_SKILL_CHANGED")
    limit = powerup["configuration"].get("maxActions", 30)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise Blocked("MAX_ACTIONS_MUST_BE_1_TO_100")
    return {"powerUp": {"id": package_id, "version": powerup["version"], "identity": record["identity"]},
            "skill": {"id": binding["skillId"], "version": binding["version"], "entrypoint": path,
                     "sha256": binding["sha256"], "instructions": instructions.decode("utf-8-sig")},
            "maxActions": limit, "permissions": manifest["permissions"]}


def _visible_line(line, comment):
    """Strip inline and multiline comments, retaining text on either side."""
    pieces = []
    position = 0
    while position < len(line):
        if comment:
            end = line.find(comment, position)
            if end < 0:
                break
            position = end + len(comment)
            comment = ""
            continue
        mark = COMMENT_START.search(line, position)
        if not mark:
            pieces.append(line[position:])
            break
        prefix = line[position:mark.start()]
        literal = ""
        for ticks in re.findall(r"`+", prefix):
            if not literal:
                literal = ticks
            elif ticks == literal:
                literal = ""
        if literal or prefix.endswith("\\"):
            raise Blocked("AMBIGUOUS_COMMENT_DELIMITER: use an ordinary comment line or fenced code")
        pieces.append(prefix)
        comment = "-->" if mark[0] == "<!--" else "%%"
        position = mark.end()
    return "".join(pieces), comment


COMMENT_START = re.compile(r"<!--|%%")


def open_actions(body, header_lines):
    """Read visible bullet checkboxes with up to three leading spaces on one line.

    Four-space and tab-indented examples can also represent deeply nested list
    items. Omit both. Fenced code, HTML comments and Obsidian comments are
    excluded. Line numbers refer to physical lines in the selected note.
    """
    fence = ""
    comment = ""
    for number, line in enumerate(body.splitlines(), header_lines + 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
            continue
        if not comment and marker and (marker[1][0] == "~" or "`" not in marker[2]):
            fence = marker[1]
            continue
        starts_visible = not comment and re.match(r"^ {0,3}[-*+][ \t]+\[ \][ \t]+", line)
        if not comment and COMMENT_START.search(line) and re.match(r"^(?: {4}| {0,3}\t)", line):
            # In these contexts a delimiter could be literal. Decline rather
            # than accidentally treating the next real opener as its closer.
            raise Blocked("AMBIGUOUS_COMMENT_DELIMITER: use an ordinary comment line or fenced code")
        visible, comment = _visible_line(line, comment)
        if not starts_visible:
            continue
        task = re.fullmatch(r" {0,3}[-*+][ \t]+\[ \][ \t]+(.+)", visible)
        if task and task[1].strip():
            yield number, task[1].strip()


def prepare(args):
    project = lifecycle.project_path(args.vault, args.project)
    resolved = resolve(args.vault, project, args.power_up)
    if args.command == "save" and WRITE_PERMISSION not in resolved["permissions"]:
        raise Blocked("POWERUP_WRITE_PERMISSION_REQUIRED")
    before = lifecycle.check(project)
    if before["status"] != "active":
        raise Blocked("PROJECT_CONTEXT_REVIEW_REQUIRED")
    selected = args.source
    if not 1 <= len(selected) <= sources.DEFAULT_FILES:
        raise Blocked("SELECT_1_TO_32_PROJECT_SOURCES")
    candidates = []
    truncated = False

    def collect(source, body, header_lines):
        nonlocal truncated
        for number, text in open_actions(body, header_lines):
            if len(candidates) == resolved["maxActions"]:
                truncated = True
                break
            if len(text) > MAX_ACTION_LENGTH:
                raise Blocked("ACTION_TEXT_EXCEEDS_1024_CHARACTERS")
            candidates.append({"path": source["path"], "line": number, "text": text})

    report = sources.visit_selected_sources(project, selected, collect, vault=args.vault)
    if report["skipped"] or report["truncated"]:
        raise Blocked("SOURCE_SELECTION_INCOMPLETE: " + ", ".join(sorted({item["reason"] for item in report["skipped"]})))
    after = lifecycle.check(project)
    if after["status"] != "active" or after["review_token"] != before["review_token"]:
        raise Blocked("PROJECT_CONTEXT_CHANGED")
    if resolve(args.vault, project, args.power_up) != resolved:
        raise Blocked("POWERUP_ACTIVATION_CHANGED")
    result = {"provider": args.provider, "project": project.name, "powerUp": resolved["powerUp"],
              "skill": resolved["skill"], "maxActions": resolved["maxActions"], "truncated": truncated,
              "sources": [{"path": item["path"], "sha256": item["sha256"]} for item in report["sources"]],
              "candidates": candidates}
    directory = project.stat()
    result["preparationSha256"] = digest(encoded({"preparation": result, "approvedContext": before["review_token"],
                                                  "projectDirectory": [directory.st_dev, directory.st_ino]}))
    return project, result


def save(project, name, result):
    if (not name.lower().endswith(".json") or name.startswith(".") or "/" in name or "\\" in name
            or len(name) > 120):
        raise Blocked("OUTPUT_REQUIRES_ONE_JSON_FILENAME")
    relative = "Results/" + name
    target = lifecycle.safe_path(project, relative)
    policy = sources.load_source_policy(project.parents[2])
    if policy.excludes(f"{lifecycle.ACTIVE}/{project.name}/{relative}", relative):
        raise Blocked("RESULT_LOCATION_EXCLUDED")
    if target.exists():
        raise Blocked("OUTPUT_ALREADY_EXISTS")
    data = encoded({"actions": result["candidates"]})
    target.parent.mkdir(exist_ok=True)
    lifecycle.safe_path(project, relative)
    # A reader sees either the entire result or no result, including during concurrent saves.
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".kos-result-", delete=False) as f:
        pending = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            f.close()
            pending.unlink(missing_ok=True)
            raise
    try:
        lifecycle.safe_path(project, relative)
        if os.name == "nt":
            os.rename(pending, target)  # Windows refuses to replace an existing destination.
        else:
            os.link(pending, target)
    except FileExistsError:
        raise Blocked("OUTPUT_ALREADY_EXISTS") from None
    finally:
        pending.unlink(missing_ok=True)
    return {"status": "saved", "output": relative, "sha256": digest(data), "actions": len(result["candidates"]),
            "truncated": result["truncated"], "preparationSha256": result["preparationSha256"]}


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--power-up", required=True)
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "save"):
        command = commands.add_parser(name)
        command.add_argument("--source", action="append", required=True, help="one selected project-relative Markdown path")
        if name == "save":
            command.add_argument("--preparation-sha256", "--run-token", required=True,
                                 help="SHA-256 returned by prepare for this selection")
            command.add_argument("--output", required=True, help="new JSON filename in the project's Results folder")
            command.add_argument("--response-stdin", action="store_true", help="validate a provider's UTF-8 JSON response")
    return parser.parse_args(argv)


def main(argv=None):
    args = arguments(argv)
    try:
        response = None
        if args.command == "save" and args.response_stdin:
            raw = sys.stdin.buffer.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise Blocked("PROVIDER_RESPONSE_TOO_LARGE")
            response = json_loads(raw.decode("utf-8-sig"))
        project, result = prepare(args)
        if args.command == "save":
            if args.preparation_sha256 != result["preparationSha256"]:
                raise Blocked("PREPARATION_CHANGED: prepare again before saving")
            if args.response_stdin and encoded(response) != encoded({"actions": result["candidates"]}):
                raise Blocked("PROVIDER_RESPONSE_MISMATCH")
            result = save(project, args.output, result)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        message = str(error) if isinstance(error, Blocked) else "Cannot verify the selected project, package or result."
        print(json.dumps({"status": "blocked", "error": message}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
