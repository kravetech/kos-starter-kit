"""Read an explicit selection of project Markdown sources under the installed policy."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import stat
from functools import lru_cache
from pathlib import Path

from project_lifecycle import ALLOWED, NOTES, check, frontmatter_disabled, frontmatter_policy, read_file, safe_path


DEFAULT_FILES = 32
DEFAULT_RESULTS = 30
MAX_FILES = 128
MAX_RESULTS = 200
MAX_SOURCE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_HEADER_BYTES = 8192
MAX_SNIPPET = 240
MANIFEST = "00 - System/Config/ai-context-manifest.yaml"
INSTALL_STATE = "00 - System/Installation/kos-installation.json"
POLICY_SECTIONS = {"restricted", "never_auto_load"}


def _policy_pattern(value):
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("Context policy contains an invalid exclusion.")
    parts = value.rstrip("/").split("/")
    if (len(parts) > 32 or any(part in {"", ".", ".."} for part in parts)
            or any(c in value for c in ("\\", ":", "\x00"))):
        raise ValueError("Use relative forward-slash paths in context exclusions.")
    return tuple(part.casefold() for part in parts)


def _policy_scalar(value):
    """Decode the simple YAML sequence entries used by the installed manifest."""
    value = value.strip()
    if value.startswith('"'):
        result, end = json.JSONDecoder().raw_decode(value)
        remainder = value[end:].strip()
        if remainder and not remainder.startswith("#"):
            raise ValueError("Unsupported quoted context exclusion.")
        return result
    if value.startswith("'"):
        quoted = re.fullmatch(r"'((?:''|[^'])*)'\s*(?:#.*)?", value)
        if not quoted:
            raise ValueError("Unsupported quoted context exclusion.")
        return quoted.group(1).replace("''", "'")
    if not value or value[0] in "!&*|>{}[]`@":
        raise ValueError("Use one plain or quoted relative glob per exclusion.")
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def _manifest_exclusions(data):
    section = None
    seen = set()
    patterns = []
    for line in data.decode("utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("\t"):
            raise ValueError("Use spaces to indent the context manifest.")
        if not line.startswith(" "):
            key = re.fullmatch(r"([A-Za-z_][\w-]*):\s*(.*)", line)
            if not key or key[1] in seen:
                raise ValueError("Unsupported or duplicate context manifest key.")
            section = key[1]
            seen.add(section)
            if section in POLICY_SECTIONS:
                value = key[2].split("#", 1)[0].strip()
                if value not in {"", "[]"}:
                    raise ValueError("Use a list of relative paths for context exclusions.")
            continue
        if section in POLICY_SECTIONS:
            item = re.fullmatch(r" +- +(.*)", line)
            if not item:
                raise ValueError("Unsupported context exclusion. Use one glob per list item.")
            patterns.append(_policy_scalar(item[1]))
    if not POLICY_SECTIONS.issubset(seen):
        raise ValueError("Context manifest needs restricted and never_auto_load lists.")
    return patterns


def _matches(pattern, parts):
    """Match slash-separated globs against the file and its parent folders."""
    @lru_cache(maxsize=None)
    def visit(i, j):
        if i == len(pattern):
            return True
        if pattern[i] == "**":
            return visit(i + 1, j) or (j < len(parts) and visit(i, j + 1))
        return (j < len(parts) and fnmatch.fnmatchcase(parts[j], pattern[i])
                and visit(i + 1, j + 1))
    return visit(0, 0)


class SourcePolicy:
    def __init__(self, patterns):
        if len(patterns) > 256:
            raise ValueError("Context policy exceeds 256 exclusions.")
        self.patterns = tuple(_policy_pattern(item) for item in patterns)

    def excludes(self, vault_relative, project_relative=""):
        for value in (vault_relative, project_relative):
            if not value:
                continue
            parts = tuple(value.casefold().split("/"))
            if (len(parts) > 64 or any(part.startswith(".") for part in parts)
                    or any(_matches(pattern, parts) for pattern in self.patterns)):
                return True
        return False


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate installation-state field.")
        result[key] = value
    return result


def load_source_policy(vault: Path) -> SourcePolicy:
    """Read only the public installed context policy and optional stored folder rules."""
    patterns = _manifest_exclusions(read_file(safe_path(vault, MANIFEST), 64 * 1024))
    state_path = safe_path(vault, INSTALL_STATE)
    if state_path.exists():
        state = json.loads(read_file(state_path, 1024 * 1024).decode("utf-8-sig"),
                           object_pairs_hook=_unique_keys)
        privacy = state.get("privacy", {}) if isinstance(state, dict) else None
        folders = privacy.get("restricted_folders", []) if isinstance(privacy, dict) else None
        if not isinstance(folders, list):
            raise ValueError("Invalid installed privacy.restricted_folders list.")
        patterns.extend(folders)
    return SourcePolicy(patterns)


def _header(stream):
    """Stop at the frontmatter boundary before consuming the source body."""
    first = stream.readline(8)  # Optional UTF-8 BOM, delimiter and CRLF.
    if first.decode("utf-8-sig", errors="replace").rstrip("\r\n") != "---":
        return first, False
    parts = [first]
    size = len(first)
    while size < MAX_HEADER_BYTES:
        line = stream.readline(MAX_HEADER_BYTES - size)
        if not line:
            break
        parts.append(line)
        size += len(line)
        if line.rstrip(b"\r\n") == b"---":
            return b"".join(parts), True
    return b"".join(parts), False


class _Excluded(ValueError):
    def __init__(self, reason, bytes_read=0, limited=False):
        super().__init__(reason)
        self.bytes_read = bytes_read
        self.limited = limited


def _read_source(project, vault_prefix, name, policy, remaining, approved):
    if (not isinstance(name, str) or len(name) > 1024 or len(name.split("/")) > 64
            or not name.casefold().endswith(".md")):
        raise _Excluded("invalid_source")
    if policy.excludes(vault_prefix + "/" + name, name):
        raise _Excluded("excluded_by_policy")
    try:
        path = safe_path(project, name)
        before = path.lstat()
        if approved and not os.path.samestat(before, safe_path(project, approved["path"]).lstat()):
            approved = None
    except FileNotFoundError:
        raise _Excluded("missing") from None
    except (OSError, ValueError):
        raise _Excluded("unsafe_or_unavailable") from None
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise _Excluded("unsafe_or_unavailable")
    if before.st_size > MAX_SOURCE_BYTES:
        raise _Excluded("source_byte_limit", limited=True)
    if before.st_size > remaining:
        raise _Excluded("total_byte_limit", limited=True)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    read_bytes = 0
    try:
        with os.fdopen(os.open(path, flags), "rb", buffering=0) as stream:
            opened = os.fstat(stream.fileno())
            if (not os.path.samestat(before, opened) or opened.st_nlink != 1
                    or opened.st_size != before.st_size or opened.st_mtime_ns != before.st_mtime_ns):
                raise _Excluded("source_changed")
            header, parsed = _header(stream)
            read_bytes = len(header)
            if not parsed and read_bytes >= MAX_HEADER_BYTES:
                raise _Excluded("metadata_byte_limit", read_bytes, limited=True)
            if not parsed and not approved:
                raise _Excluded("unclassified_or_invalid", read_bytes)
            fields, access = frontmatter_policy(header)
            reviewed_legacy = approved and approved["ai_access"] == access == "unclassified"
            if access not in ALLOWED and not reviewed_legacy:
                raise _Excluded("restricted" if access == "restricted" else "unclassified_or_invalid", read_bytes)
            if frontmatter_disabled(fields, allow_draft=bool(approved)):
                raise _Excluded("disabled_or_draft", read_bytes)
            body = stream.read(max(0, before.st_size - len(header)))
            read_bytes += len(body)
            after = os.fstat(stream.fileno())
            if (after.st_size != read_bytes or after.st_mtime_ns != opened.st_mtime_ns
                    or after.st_ctime_ns != opened.st_ctime_ns or after.st_nlink != 1
                    or not os.path.samestat(after, safe_path(project, name).lstat())):
                raise _Excluded("source_changed", read_bytes)
        revision = hashlib.sha256(header + body).hexdigest()
        if approved:
            if revision != approved["sha256"]:
                raise _Excluded("source_changed", read_bytes)
            access = approved["effective_access"]
        if not parsed:
            # An approved legacy note begins with its body on physical line one.
            body, header = header + body, b""
        text = body.decode("utf-8-sig" if not parsed else "utf-8")
    except _Excluded:
        raise
    except (OSError, ValueError):
        raise _Excluded("unsafe_or_unreadable", read_bytes) from None
    return {"path": name, "access": access, "sha256": revision, "bytes": read_bytes}, text, header.count(b"\n")


def _snippet(line, start):
    if len(line) <= MAX_SNIPPET:
        return line
    begin = max(0, min(start - 48, len(line) - MAX_SNIPPET + 2))
    piece = line[begin:begin + MAX_SNIPPET - 2]
    return ("…" if begin else "") + piece + ("…" if begin + len(piece) < len(line) else "")


def _run(project, selected, query, max_files, max_results, vault, visit=None):
    if not 1 <= max_files <= MAX_FILES or not 1 <= max_results <= MAX_RESULTS:
        raise ValueError(f"max_files must be 1–{MAX_FILES}; max_results must be 1–{MAX_RESULTS}.")
    matcher = None
    if query is not None:
        if not isinstance(query, str) or not query.strip() or len(query) > 256 or any(c in query for c in "\r\n"):
            raise ValueError("Use a nonempty single-line search of up to 256 characters.")
        matcher = re.compile(re.escape(query), re.IGNORECASE)
    project = Path(os.path.abspath(project))
    owner = Path(os.path.abspath(vault)) if vault is not None else project.parents[2]
    prefix = project.relative_to(owner).as_posix()
    policy = load_source_policy(owner)
    if policy.excludes(prefix):
        raise ValueError("Selected project is restricted by the installed context policy.")
    report = {
        "project": prefix,
        "selected_count": len(selected), "processed_count": 0, "sources": [], "skipped": [],
        "matches": [], "truncated": len(selected) > max_files,
        "limits": {"max_files": max_files, "max_results": max_results,
                   "max_source_bytes": MAX_SOURCE_BYTES, "max_total_bytes": MAX_TOTAL_BYTES},
    }
    remaining = MAX_TOTAL_BYTES
    seen = set()
    context_names = {name.casefold() for name in NOTES}
    approved_files = None
    for name in selected[:max_files]:
        if os.name == "nt":
            name = name.replace("\\", "/")
        report["processed_count"] += 1
        if os.path.normcase(name) in seen:
            report["skipped"].append({"path": name, "reason": "duplicate"})
            continue
        seen.add(os.path.normcase(name))
        try:
            approved = None
            if name.casefold() in context_names:
                if approved_files is None:
                    current = check(project)
                    approved_files = ({item["path"].casefold(): item for item in current["files"]}
                                      if current["status"] == "active" else {})
                approved = approved_files.get(name.casefold())
                if not approved:
                    raise _Excluded("context_requires_approval")
            source, body, header_lines = _read_source(project, prefix, name, policy, remaining, approved)
        except _Excluded as error:
            report["skipped"].append({"path": name, "reason": str(error)})
            remaining -= error.bytes_read
            report["truncated"] |= error.limited
            continue
        report["sources"].append(source)
        remaining -= source["bytes"]
        if visit is not None:
            visit(source, body, header_lines)
        if matcher is None:
            continue
        for line_no, line in enumerate(body.splitlines(), start=header_lines + 1):
            match = matcher.search(line)
            if match is not None:
                if len(report["matches"]) == max_results:
                    report["truncated"] = True
                    return report
                report["matches"].append({"path": name, "line": line_no, "snippet": _snippet(line, match.start())})
    return report


def inspect_sources(project: Path, selected, *, max_files=DEFAULT_FILES, vault=None):
    return _run(project, selected, None, max_files, DEFAULT_RESULTS, vault)


def visit_selected_sources(project: Path, selected, visit, *, vault=None):
    """Pass only eligible, bounded source bodies to a built-in local consumer."""
    return _run(project, selected, None, DEFAULT_FILES, DEFAULT_RESULTS, vault, visit)


def search_sources(project: Path, selected, query: str, *, max_files=DEFAULT_FILES,
                   max_results=DEFAULT_RESULTS, vault=None):
    return _run(project, selected, query, max_files, max_results, vault)
