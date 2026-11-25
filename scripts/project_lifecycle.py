"""Owner-reviewed, content-bound project context for an installed Community vault."""
from __future__ import annotations

import base64
import difflib
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


ACTIVE = "02 - Projects/Active"
NOTES = {
    "memory.md": "# Project Memory\n\n## Approved decisions\n\n## Constraints\n",
    "handoff.md": "# Project Handoff\n\n## Current objective\n\n## Current status\n\n## Next action\n",
}
RECEIPT = ".kos-context-approval.json"
WRITE_LOCK = ".kos-context-write.lock"
MAX_NOTE = 256 * 1024
MAX_HEADER = 8192
MAX_RECEIPT = 2 * ((MAX_NOTE + 2) // 3 * 4) + 8192
ALLOWED = {"public", "internal"}


def _part(value):
    return (isinstance(value, str) and bool(value) and value not in {".", ".."}
            and not value.endswith((".", " ")) and not re.search(r'[\x00-\x1f\\/:*?"<>|]', value)
            and not re.match(r"^(CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])(?:\.|$)", value, re.I))


def safe_path(root: Path, relative: str) -> Path:
    """Resolve a portable relative name without following aliases, links or reparse points."""
    parts = relative.split("/")
    if not all(_part(part) for part in parts):
        raise ValueError("Expected a portable relative path inside the selected scope.")
    root = Path(os.path.abspath(root))
    path = root.joinpath(*parts)
    for node in (*reversed(path.parents), path):
        try:
            info = node.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked or redirected paths are outside the selected scope.")
        if node != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError("A path component is not a directory.")
        if node == path and stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ValueError("Multiply linked files are outside the selected scope.")
    return path


@contextmanager
def _open_regular(path, limit):
    path = safe_path(path.parent, path.name)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError(f"{path.name} must be a regular file of at most {limit} bytes.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not os.path.samestat(info, before) or info.st_nlink != 1:
            raise ValueError("File identity changed. Review the project again.")
        yield stream


def read_file(path: Path, byte_limit: int) -> bytes:
    with _open_regular(path, byte_limit) as stream:
        data = stream.read(byte_limit + 1)
    if len(data) > byte_limit:
        raise ValueError("File grew beyond the configured byte limit.")
    return data


POLICY_FIELDS = {"ai_access", "status", "review_status", "ai_context", "enabled", "disabled"}


def _description_scalar(value):
    """Accept complete, single-line descriptive values without interpreting them."""
    if value.startswith('"'):
        return re.fullmatch(r'"(?:[^"\\]|\\.)*"(?:\s+#.*)?', value) is not None
    if value.startswith("'"):
        return re.fullmatch(r"'(?:[^']|'')*'(?:\s+#.*)?", value) is not None
    if value.startswith(("[", "{")):
        # Obsidian also emits single-line sequences for tags and aliases.
        closing = "]" if value.startswith("[") else "}"
        return re.fullmatch(r".*" + re.escape(closing) + r"(?:\s+#.*)?", value) is not None
    return not value.startswith(("!", "&", "*", "|", ">"))


def frontmatter_policy(data):
    """Read strict policy scalars from bounded Obsidian Markdown front matter."""
    data = data.removeprefix(b"\xef\xbb\xbf")
    first = data.split(b"\n", 1)[0].rstrip(b"\r")
    if first != b"---":
        if first.strip().startswith(b"---"):
            return {}, "invalid"
        return {}, "unclassified"
    fields = {}
    seen = set()
    continuation = None
    for line in data[:MAX_HEADER].split(b"\n")[1:]:
        if line.rstrip(b"\r") == b"---":
            if "ai_access" not in fields:
                return fields, "unclassified"
            access = fields["ai_access"]
            return fields, access if access in ALLOWED | {"restricted"} else "invalid"
        try:
            line = line.decode("utf-8").rstrip("\r")
        except UnicodeDecodeError:
            break
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if continuation == "text" and line.startswith(" "):
            continue
        list_item = re.fullmatch(r" *- +(.+)", line)
        if continuation == "list" and list_item:
            if not _description_scalar(list_item[1].strip()):
                break
            continue
        match = re.fullmatch(r"([A-Za-z_][\w -]*):(?:[ \t]+(.*))?", line)
        if not match:
            break
        key = match[1].rstrip().casefold()
        if key in seen:
            break
        seen.add(key)
        continuation = None
        value = (match[2] or "").strip()
        if key in POLICY_FIELDS:
            scalar = re.fullmatch(r"""(['"]?)([\w-]+)\1(?:\s+#.*)?""", value)
            if not scalar:
                break
            fields[key] = scalar[2]
        elif not value or value.startswith("#"):
            continuation = "list"
        elif re.fullmatch(r"[|>](?:[+-][1-9]?|[1-9][+-]?)?(?:\s+#.*)?", value):
            continuation = "text"
        elif not _description_scalar(value):
            break
    return {}, "invalid"


def frontmatter_access(data: bytes) -> str:
    access = frontmatter_policy(data)[1]
    return access if access in ALLOWED | {"restricted", "unclassified"} else "invalid"


def frontmatter_disabled(fields, *, allow_draft):
    inactive = {"disabled", "inactive", "archived", "never", "rejected", "withdrawn"}
    if not allow_draft:
        inactive.add("draft")
    return (fields.get("enabled", "true").casefold() != "true"
            or fields.get("disabled", "false").casefold() != "false"
            or fields.get("ai_context", "").casefold() in {"false", "off", "excluded"}
            or any(value.casefold() in inactive for value in fields.values()))


def project_path(vault: Path, name: str) -> Path:
    if not _part(name) or name.startswith("."):
        raise ValueError("Select one project by its folder name under 02 - Projects/Active.")
    for anchor in ("AGENTS.md", "00 - System/Config/ai-context-manifest.yaml"):
        if not safe_path(vault, anchor).is_file():
            raise ValueError("Select an installed vault with AGENTS.md and its context manifest.")
    project = safe_path(vault, f"{ACTIVE}/{name}")
    if project.exists():
        if not project.is_dir():
            raise ValueError("The selected project is not a directory.")
        if os.name == "nt":
            # Use the on-disk name for receipt identity, including on case-sensitive volumes.
            project = safe_path(project.parent, project.resolve(strict=True).name)
    _check_scope(project)
    return project


def _check_scope(project):
    from project_sources import load_source_policy
    policy = load_source_policy(project.parents[2])
    relative = f"{ACTIVE}/{project.name}"
    if policy.excludes(relative, project.name):
        raise ValueError("The selected project is excluded by vault policy.")
    return policy


def _ensure_snapshot_ignored(project, filename):
    """Require the actual repository index and ignore rules to protect local originals."""
    for directory in (project, *project.parents):
        try:
            (directory / ".git").lstat()
        except FileNotFoundError:
            continue
        break
    else:
        return

    # Inherited index/worktree overrides could check a different repository than the vault.
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(project), "check-ignore", "-q", "--", filename],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is None or result.returncode not in (0, 1):
        raise ValueError("Git could not verify privacy for the local approval snapshot. "
                         "Make Git available and verify this vault's worktree, then retry.")
    # Without --no-index Git also rejects a matching ignore rule for an already tracked file.
    if result.returncode == 1:
        raise ValueError("Git can track local approval files. Add .kos-context-* to the applicable "
                         "Git ignore rules and ensure .kos-context-approval.json is untracked. "
                         "If it was already shared, review its history before proceeding.")


@contextmanager
def _writing(project):
    lock = safe_path(project, WRITE_LOCK)
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError("A project context write is in progress. Retry after it finishes. "
                         "After an interrupted write, verify the writer has stopped before removing "
                         f"the empty {WRITE_LOCK} directory.") from error
    try:
        yield
    finally:
        lock.rmdir()


def _pair_token(project_name, hashes):
    reviewed = [f"{ACTIVE}/{project_name}", [(name, hashes[name]) for name in NOTES]]
    return hashlib.sha256(json.dumps(reviewed, ensure_ascii=False).encode()).hexdigest()


def _unique_entries(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate context approval field.")
    return result


def _receipt(project):
    path = safe_path(project, RECEIPT)
    if not path.exists():
        return None
    try:
        receipt = json.loads(read_file(path, MAX_RECEIPT), object_pairs_hook=_unique_entries)
    except (ValueError, RecursionError) as error:
        raise ValueError(f"Invalid {RECEIPT}. Inspect and recover it before approving this project.") from error
    if isinstance(receipt, dict) and receipt.get("schema") == "kos-context-approval/v2":
        saved_name = receipt.get("project")
        if saved_name != project.name:
            same_directory = False
            if os.name == "nt" and _part(saved_name) and saved_name.casefold() == project.name.casefold():
                saved_project = safe_path(project.parent, saved_name)
                same_directory = saved_project.exists() and saved_project.samefile(project)
            if not same_directory:
                raise ValueError("The saved approval belongs to a different project. Restore the original project "
                                 "name for its review, or recover this project's own receipt from a backup.")
    try:
        required = {"schema", "review_token", "classify_unmarked"}
        if (not isinstance(receipt, dict) or not required.issubset(receipt)
                or type(receipt["classify_unmarked"]) is not bool
                or not isinstance(receipt["review_token"], str)
                or not re.fullmatch("[0-9a-f]{64}", receipt["review_token"])):
            raise ValueError("Invalid approval fields.")
        if receipt["schema"] == "kos-context-approval/v1" and set(receipt) == required:
            return receipt
        if (receipt["schema"] != "kos-context-approval/v2" or set(receipt) != required | {"project", "approved_files"}
                or not _part(receipt["project"]) or not isinstance(receipt["approved_files"], dict)
                or set(receipt["approved_files"]) != set(NOTES)):
            raise ValueError("Invalid approval snapshot.")
        hashes = {}
        for name, entry in receipt["approved_files"].items():
            if not isinstance(entry, dict) or set(entry) != {"sha256", "content_b64"}:
                raise ValueError("Invalid snapshot entry.")
            data = base64.b64decode(entry["content_b64"], validate=True)
            hashes[name] = hashlib.sha256(data).hexdigest()
            if hashes[name] != entry["sha256"] or len(data) > MAX_NOTE:
                raise ValueError("Snapshot content verification failed.")
            data.decode("utf-8-sig")
            entry["bytes"] = data
        if _pair_token(receipt["project"], hashes) == receipt["review_token"]:
            # An older Windows approval could have stored the owner's typed casing.
            # Its original token has now been verified; compare edits using today's physical name.
            if receipt["project"] != project.name:
                receipt["review_token"] = _pair_token(project.name, hashes)
            return receipt
    except (ValueError, TypeError, RecursionError):
        pass
    raise ValueError(f"Invalid {RECEIPT}. Inspect and recover it before approving this project.")


def _note(path):
    with _open_regular(path, MAX_NOTE) as stream:
        # Inspect policy before reading a body. Legacy context may be hashed for explicit review.
        first = stream.readline(MAX_HEADER + 1)
        header = bytearray(first)
        if first.removeprefix(b"\xef\xbb\xbf").rstrip(b"\r\n") == b"---":
            while len(header) <= MAX_HEADER:
                line = stream.readline(MAX_HEADER + 1 - len(header))
                header.extend(line)
                if not line or line.rstrip(b"\r\n") == b"---":
                    break
        fields, access = frontmatter_policy(bytes(header))
        if access not in ALLOWED | {"unclassified"}:
            return {"path": path.name, "ai_access": access, "issue": "Check access classification."}, None
        if frontmatter_disabled(fields, allow_draft=True):
            return {"path": path.name, "ai_access": access, "issue": "Owner review of note status required."}, None
        stream.seek(0)
        data = stream.read(MAX_NOTE + 1)
    if len(data) > MAX_NOTE:
        raise ValueError("Context note grew beyond the byte limit.")
    data.decode("utf-8-sig")
    item = {"path": path.name, "sha256": hashlib.sha256(data).hexdigest(), "ai_access": access}
    if access == "unclassified":
        item["proposed_access"] = "internal"
    return item, data


def _snapshot(project):
    if not project.is_dir():
        raise ValueError("Project is missing. Initialize it first.")
    policy = _check_scope(project)
    items, bodies = [], {}
    for name in NOTES:
        path = safe_path(project, name)
        if policy.excludes(f"{ACTIVE}/{project.name}/{name}", name):
            items.append({"path": name, "issue": "Excluded by vault policy."})
        elif not path.exists():
            items.append({"path": name, "issue": "Missing context note. Run init."})
        else:
            item, body = _note(path)
            items.append(item)
            if body is not None:
                bodies[name] = body
    token = None
    if len(bodies) == len(NOTES):
        token = _pair_token(project.name, {item["path"]: item["sha256"] for item in items})
    return items, bodies, token


def _diff(name, before, after):
    old, new = before.splitlines(), after.splitlines()
    if old == new:
        return "Only line endings, the final newline, or the UTF-8 byte-order mark changed.", False
    # Bound diff computation as well as display. Locate the first difference
    # even when a change comes near the end of a long document.
    if len(old) + len(new) > 2000 or any(len(line) > 8192 for lines in (old, new) for line in lines):
        start = 0
        while start < min(len(old), len(new)) and old[start] == new[start]:
            start += 1
        old_line = old[start] if start < len(old) else ""
        new_line = new[start] if start < len(new) else ""
        column = 0
        while column < min(len(old_line), len(new_line)) and old_line[column] == new_line[column]:
            column += 1
        left = max(0, column - 80)
        parts = [f"First difference at line {start + 1}, column {column + 1} (excerpt)"]
        for marker, lines in (("- ", old), ("+ ", new)):
            if start < len(lines):
                parts.append(marker + lines[start][left:left + 240])
                parts.extend(marker + line[:240] for line in lines[start + 1:start + 4])
        return "\n".join(parts), True
    lines = difflib.unified_diff(old, new, fromfile=f"approved/{name}", tofile=f"current/{name}", lineterm="")
    output = "\n".join(lines)
    return output[:32768], len(output) > 32768


def _stale_report(result, receipt, bodies, current_token, owner_review, include_diff):
    result["review_token"] = None
    result["changed_files"] = None
    if "approved_files" not in receipt:
        result["guidance"] = ("The older approval contains only the pair digest. Save current edits, restore "
                              "both original notes from your backup, and explicitly approve that matching "
                              "pair to save its snapshot. Reapply the edits and run review.")
        return
    changes = []
    needs_classification = False
    for item in result["files"]:
        name = item["path"]
        old = receipt["approved_files"][name]
        if old["sha256"] == item["sha256"]:
            continue
        change = {"path": name, "previous_sha256": old["sha256"], "current_sha256": item["sha256"]}
        changes.append(change)
        if item["ai_access"] not in ALLOWED:
            needs_classification = True
        elif include_diff:
            original = old["bytes"].decode("utf-8-sig")
            diff, truncated = _diff(name, original, bodies[name].decode("utf-8-sig"))
            change.update(original_content=original, diff=diff, diff_truncated=truncated)
    result["changed_files"] = changes
    if needs_classification:
        result["guidance"] = ("Classify the edited unmarked note locally before comparing its current "
                              "contents with the approved original. Then run review again.")
        return
    result["guidance"] = "Run review to compare the edited files with their saved approved originals before approving."
    if owner_review:
        payload = f"kos-stale-review/v1:{receipt['review_token']}:{current_token}".encode("ascii")
        result["review_token"] = hashlib.sha256(payload).hexdigest()


def _evaluate(project, *, owner_review=False, include_diff=False):
    items, bodies, token = _snapshot(project)
    receipt = _receipt(project) if token else None
    status = "draft"
    if not token:
        status = "blocked"
    elif receipt:
        status = "active" if receipt["review_token"] == token else "stale"
        if status == "active" and any(item["ai_access"] == "unclassified" for item in items):
            if not receipt["classify_unmarked"]:
                status = "blocked"
    if status == "active":
        for item in items:
            item["effective_access"] = item.get("proposed_access", item["ai_access"])
    result = {"status": status, "review_token": token, "files": items}
    if receipt:
        result["receipt_schema"] = receipt["schema"]
    if status == "stale":
        _stale_report(result, receipt, bodies, token, owner_review, include_diff)
    return result, bodies


def initialize(project: Path) -> dict:
    policy = _check_scope(project)
    for name in NOTES:
        if policy.excludes(f"{ACTIVE}/{project.name}/{name}", name):
            raise ValueError("Project context is excluded by vault policy.")
    # Recognized minimal installations may not have the Projects domain yet.
    project.mkdir(parents=True, exist_ok=True)
    created = []
    with _writing(project):
        _receipt(project)
        paths = [safe_path(project, name) for name in NOTES]
        for path in paths:
            if path.exists() and not path.is_file():
                raise ValueError(f"{path.name} must be a regular note.")
        for path in paths:
            if not path.exists():
                # Draft until the owner approves the exact pair. Marker lives in the receipt.
                note = "---\nai_access: internal\n---\n\n" + NOTES[path.name]
                with path.open("xb") as stream:
                    stream.write(note.encode())
                    stream.flush()
                    os.fsync(stream.fileno())
                created.append(path.name)
        result, _ = _evaluate(project)
    return {**result, "created": created}


def _inspect(project: Path, *, owner_review=False) -> dict:
    if safe_path(project, WRITE_LOCK).exists():
        raise ValueError("Project context is being written. Retry after the writer finishes.")
    result, _ = _evaluate(project, owner_review=owner_review, include_diff=owner_review)
    if project.is_dir():
        try:
            _ensure_snapshot_ignored(project, RECEIPT)
        except ValueError as error:
            result["snapshot_warning"] = str(error)
    return result


def review(project: Path) -> dict:
    return _inspect(project, owner_review=True)


def check(project: Path) -> dict:
    return _inspect(project)


def approve(project: Path, review_token: str, classify_unmarked: bool = False) -> dict:
    if not review_token:
        raise ValueError("Review the project, then supply its review token to approve both notes.")
    with _writing(project):
        _ensure_snapshot_ignored(project, RECEIPT)
        result, bodies = _evaluate(project, owner_review=True)
        if result["review_token"] != review_token:
            raise ValueError("The reviewed pair is missing, blocked or has changed. Review it again.")
        if result["status"] == "active":
            if result["receipt_schema"] == "kos-context-approval/v2":
                return result
            # The legacy pair still matches its approval; its actual bytes are available now.
            classify_unmarked = any(item["ai_access"] == "unclassified" for item in result["files"])
        if any(item["ai_access"] == "unclassified" for item in result["files"]) and not classify_unmarked:
            raise ValueError("Review the proposed internal classification and explicitly "
                             "pass --classify-unmarked, or classify the notes yourself and review again.")
        hashes = {item["path"]: item["sha256"] for item in result["files"]}
        current_token = _pair_token(project.name, hashes)
        receipt = {"schema": "kos-context-approval/v2", "review_token": current_token,
                   "classify_unmarked": classify_unmarked, "project": project.name,
                   "approved_files": {
                       name: {"sha256": hashes[name], "content_b64": base64.b64encode(data).decode("ascii")}
                       for name, data in bodies.items()
                   }}
        dest = safe_path(project, RECEIPT)
        with tempfile.NamedTemporaryFile(dir=project, prefix=".kos-context-", delete=False) as stream:
            tmp = Path(stream.name)
            try:
                _ensure_snapshot_ignored(project, tmp.name)
                stream.write((json.dumps(receipt, indent=2) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                stream.close()
                tmp.unlink(missing_ok=True)
                raise
        try:
            if _snapshot(project)[2] != current_token:
                raise ValueError("Context changed during approval. Review the current pair again.")
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
        result, _ = _evaluate(project)
        if result["status"] != "active":
            raise ValueError("Approval is stale. Review the current pair again.")
        return result


def read_context(project: Path) -> dict:
    if safe_path(project, WRITE_LOCK).exists():
        raise ValueError("Project context is being written. Retry after the writer finishes.")
    result, bodies = _evaluate(project)
    if result["status"] != "active":
        if result["status"] == "stale":
            changed = ", ".join(entry["path"] for entry in result.get("changed_files") or [])
            raise ValueError(f"Context is stale{f' ({changed})' if changed else ''}. {result['guidance']}")
        raise ValueError(f"Context is {result['status']}. Review and approve the current pair first.")
    for item in result["files"]:
        item["content"] = bodies[item["path"]].decode("utf-8-sig")
        item["source"] = f"{ACTIVE}/{project.name}/{item['path']}"
    return result
