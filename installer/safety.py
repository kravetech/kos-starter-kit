"""Filesystem boundaries shared by planning, validation and transactions."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent
INSTALLATION = "00 - System/Installation"
STATE = INSTALLATION + "/kos-installation.json"
RUNS = INSTALLATION + "/Runs"


class Blocked(ValueError):
    """Input or target cannot safely be used; exit 2."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def json_loads(text: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key.casefold() in {existing.casefold() for existing in result}:
                raise Blocked("JSON_DUPLICATE_KEY")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique)


def json_read(path: Path):
    return json_loads(path.read_text(encoding="utf-8-sig"))


def link(path: Path) -> bool:
    try:
        info = path.lstat()
        return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)
    except FileNotFoundError:
        return False


def relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise Blocked("PATH_INVALID")
    parts = value.split("/")
    for part in parts:
        if (part in {"", ".", ".."} or part.endswith((".", " ")) or
                any(ord(c) < 32 or c in ':<>"|?*' for c in part) or
                re.match(r"(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)", part)):
            raise Blocked("PATH_RESERVED")
    return value


def safe(root: Path, rel: str = "", *, write: bool = False) -> Path:
    root = Path(os.path.abspath(root))
    path = root / relative(rel) if rel else root
    for node in reversed([path, *path.parents]):
        if link(node):
            raise Blocked("PATH_LINK")
        if node.exists() and node != path and not node.is_dir():
            raise Blocked("PATH_PARENT_FILE")
    if write and path.is_file() and path.stat().st_nlink > 1:
        raise Blocked("PATH_HARDLINK")
    return path


def target_root(value: Path) -> Path:
    root = Path(os.path.abspath(value))
    safe(root)
    if root == Path(root.anchor) or root == Path.home() or root == ROOT or root in ROOT.parents:
        raise Blocked("TARGET_UNSAFE_OR_SOURCE")
    if root.exists() and not root.is_dir():
        raise Blocked("TARGET_NOT_DIRECTORY")
    config = ROOT / "installer/local-config.json"
    if config.exists():
        data = json_read(config)
        for item in data.get("protected_paths", []) + data.get("reference_paths", []):
            protected = Path(os.path.abspath(item))
            if root == protected or protected in root.parents or root in protected.parents:
                raise Blocked("TARGET_PROTECTED")
    return root


def inventory(root: Path, excluded: set[str] | None = None) -> list[dict]:
    """lstat first; never descend into a link, junction, or runtime evidence."""
    safe(root)
    result = []
    if not root.exists():
        return result
    pending = [root]
    while pending:
        parent = pending.pop()
        safe(root, parent.relative_to(root).as_posix() if parent != root else "")
        for path in sorted(parent.iterdir(), key=lambda p: p.name):
            rel = path.relative_to(root).as_posix()
            if excluded and path.name in excluded:
                continue
            if link(path):
                result.append({"path": rel, "kind": "link", "ownership": "user-owned"})
            elif path.is_dir():
                result.append({"path": rel, "kind": "directory"})
                if rel not in {".git", RUNS}:
                    pending.append(path)
            elif path.is_file():
                safe(root, rel)
                result.append({"path": rel, "kind": "file", "hash": digest(path.read_bytes())})
            else:
                result.append({"path": rel, "kind": "special", "ownership": "user-owned"})
    return sorted(result, key=lambda x: x["path"])


def current_hash(root: Path, rel: str):
    path = safe(root, rel, write=True)
    if path.exists() and not path.is_file():
        raise Blocked("PATH_NOT_FILE")
    return digest(path.read_bytes()) if path.exists() else None


def durable(path: Path, data: bytes, *, exclusive=False):
    """Caller establishes ancestry and journaling. Flush before returning."""
    with path.open("xb" if exclusive else "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def merge_existing(defaults, existing):
    """Object keys recurse; arrays are atomic user choices, including []."""
    if isinstance(defaults, dict) and isinstance(existing, dict):
        result = dict(existing)
        for key, value in defaults.items():
            result[key] = merge_existing(value, existing[key]) if key in existing else value
        return result
    if type(defaults) is not type(existing):
        raise Blocked("CONFIG_TYPE_CONFLICT")
    return existing
