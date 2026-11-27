"""Local recovery planning and verified copies for the guided Community updater."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from safety import Blocked, safe


@dataclass(frozen=True)
class Entry:
    kind: str
    value: str = ""
    size: int = 0
    mode: int = 0
    attributes: int = 0


def _absolute(path: Path) -> Path:
    path = Path(path).expanduser()
    if ".." in path.parts:
        raise Blocked("RECOVERY_PATH_HAS_PARENT_REFERENCE")
    return Path(os.path.abspath(path))


def _synced(path: Path) -> bool:
    # Common client roots plus provider markers at custom locations.
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer", "DROPBOX_PATH"):
        if os.environ.get(var) and path.is_relative_to(Path(os.environ[var]).absolute()):
            return True
    for part in (path, *path.parents):
        name = part.name.casefold()
        if (name in {"onedrive", "dropbox", "google drive", "googledrive", "icloud drive",
                     "iclouddrive", "cloudstorage", "mobile documents", "nextcloud"}
                or name.startswith(("onedrive - ", "dropbox ("))):
            return True
        if any(os.path.lexists(part / marker) for marker in (".stfolder", ".dropbox", ".sync/ID")):
            return True
    return False


def _destination(vault: Path, run_root: Path) -> Path:
    safe(vault)
    safe(run_root)
    if (run_root.is_relative_to(vault) or vault.is_relative_to(run_root)
            or os.path.lexists(run_root)):
        raise Blocked("RECOVERY_LOCATION_OVERLAPS_OR_EXISTS")
    if (os.name == "nt" and run_root.drive.startswith("\\\\")) or _synced(run_root):
        raise Blocked("RECOVERY_REQUIRES_PRIVATE_LOCAL_LOCATION")
    ancestor = run_root.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not os.access(ancestor, os.W_OK | os.X_OK):
        raise Blocked("RECOVERY_PARENT_NOT_WRITABLE")
    if os.name == "posix":
        mode = ancestor.stat().st_mode
        if mode & (stat.S_IWGRP | stat.S_IWOTH) and not mode & stat.S_ISVTX:
            raise Blocked("RECOVERY_PARENT_SHARED_WRITABLE")
    return ancestor


def propose_recovery(vault: Path, recovery_parent: Path | None = None) -> Path:
    """Return a fresh run path; approval must precede directory creation."""
    vault = _absolute(vault)
    safe(vault)
    if not vault.is_dir() or vault.parent == vault:
        raise Blocked("RECOVERY_VAULT_REQUIRES_DIRECTORY")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{uuid.uuid4().hex[:12]}"
    if recovery_parent is not None:
        candidate = _absolute(recovery_parent) / name
        _destination(vault, candidate)
        return candidate
    sibling = vault.parent / (vault.name + "-recovery") / name
    try:
        _destination(vault, sibling)
        return sibling
    except (Blocked, PermissionError):
        fallback = _absolute(Path.home()) / "KOS Recovery" / vault.name / name
        _destination(vault, fallback)
        return fallback


def _identity(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)


@contextmanager
def _open_regular(path: Path, info: os.stat_result):
    safe(path.parent)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        current = os.fstat(stream.fileno())
        if not stat.S_ISREG(current.st_mode) or _identity(current) != _identity(info):
            raise Blocked("RECOVERY_SOURCE_CHANGED")
        yield stream
        if (_identity(os.fstat(stream.fileno())) != _identity(info)
                or _identity(path.lstat()) != _identity(info)):
            raise Blocked("RECOVERY_SOURCE_CHANGED")


def _link_kind(info: os.stat_result) -> str | None:
    if stat.S_ISLNK(info.st_mode):
        is_dir = getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_DIRECTORY
        return "directory-symlink" if is_dir else "symlink"
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        if getattr(info, "st_reparse_tag", 0) == stat.IO_REPARSE_TAG_MOUNT_POINT:
            return "junction"
        raise Blocked("RECOVERY_UNSUPPORTED_REPARSE_POINT")
    return None


def snapshot(vault: Path) -> dict[str, Entry]:
    """Inventory all entries, including hidden files, empty dirs and installer history."""
    vault = _absolute(vault)
    safe(vault)
    if not vault.exists():
        return {}
    if not vault.is_dir():
        raise Blocked("RECOVERY_VAULT_REQUIRES_DIRECTORY")
    entries = {}
    pending = [vault]
    while pending:
        path = pending.pop()
        safe(path.parent)
        info = path.lstat()
        rel = path.relative_to(vault).as_posix()
        kind = _link_kind(info)
        if kind:
            entries[rel] = Entry(kind, value=os.readlink(path))
            continue
        mode = stat.S_IMODE(info.st_mode)
        attributes = getattr(info, "st_file_attributes", 0) & (
            stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM | stat.FILE_ATTRIBUTE_READONLY)
        if stat.S_ISDIR(info.st_mode):
            if os.name == "posix" and path != vault and path.is_mount():
                raise Blocked("RECOVERY_NESTED_MOUNT")
            entries[rel] = Entry("directory", mode=mode, attributes=attributes)
            safe(path)
            pending.extend(path.iterdir())
        elif stat.S_ISREG(info.st_mode):
            digest = hashlib.sha256()
            with _open_regular(path, info) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            entries[rel] = Entry("file", digest.hexdigest(), info.st_size, mode, attributes)
        else:
            raise Blocked("RECOVERY_UNSUPPORTED_FILE_TYPE")
    return entries


def _copy_metadata(source: Path, destination: Path, entry: Entry) -> None:
    shutil.copystat(source, destination, follow_symlinks=False)
    if os.name == "nt" and entry.attributes != (destination.lstat().st_file_attributes & 7):
        import ctypes
        from ctypes import wintypes

        setter = ctypes.WinDLL("kernel32", use_last_error=True).SetFileAttributesW
        setter.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
        setter.restype = wintypes.BOOL
        attributes = (destination.lstat().st_file_attributes & ~7) | entry.attributes
        if not setter(str(destination), attributes):
            raise ctypes.WinError(ctypes.get_last_error())


def _make_private_run(path: Path) -> None:
    if os.name != "nt":
        path.mkdir(mode=0o700)
        if path.stat().st_mode & 0o077:
            raise Blocked("RECOVERY_FILESYSTEM_CANNOT_ENFORCE_PRIVATE_MODE")
        return
    # Windows originally ignored mkdir's mode. Create the directory with the
    # protected, inheritable ACL used by patched CPython for mode 0700.
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    volume = ctypes.create_unicode_buffer(32768)
    flags = wintypes.DWORD()
    if not kernel.GetVolumePathNameW(str(path.parent), volume, len(volume)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.GetVolumeInformationW(volume, None, 0, None, None, ctypes.byref(flags), None, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    if not flags.value & 0x8 or kernel.GetDriveTypeW(volume) == 4:  # persistent ACLs, local volume
        raise Blocked("RECOVERY_REQUIRES_PRIVATE_LOCAL_FILESYSTEM")

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", wintypes.BOOL)]

    descriptor = ctypes.c_void_p()
    acl = "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)"
    if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(acl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attrs = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        if not kernel.CreateDirectoryW(str(path), ctypes.byref(attrs)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


def _copy_junction(source: Path, destination: Path) -> None:
    """Clone the reparse buffer itself, including a dangling junction's exact target."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    open_handle = kernel.CreateFileW
    open_handle.restype = wintypes.HANDLE
    open_handle.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    control = kernel.DeviceIoControl
    control.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
    buffer = ctypes.create_string_buffer(16 * 1024)  # MAXIMUM_REPARSE_DATA_BUFFER_SIZE
    count = wintypes.DWORD()
    get_reparse, set_reparse = 0x900A8, 0x900A4
    open_reparse_directory = 0x00200000 | 0x02000000
    for path, request in ((source, get_reparse), (destination, set_reparse)):
        if request == set_reparse:
            destination.mkdir()
        access = 0 if request == get_reparse else 0x40000000
        handle = open_handle(str(path), access, 7, None, 3, open_reparse_directory, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if request == get_reparse:
                ok = control(handle, request, None, 0, buffer, len(buffer), ctypes.byref(count), None)
            else:
                if int.from_bytes(buffer.raw[:4], "little") != stat.IO_REPARSE_TAG_MOUNT_POINT:
                    raise Blocked("RECOVERY_SOURCE_CHANGED")
                ok = control(handle, request, buffer, count.value, None, 0, ctypes.byref(count), None)
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(wintypes.HANDLE(handle))


def _copy_tree(source: Path, destination: Path, baseline: dict[str, Entry]) -> None:
    destination.mkdir(mode=0o700, exist_ok=False)
    # Lexical order puts parents before descendants. Restore directory modes last.
    directories = []
    for rel, entry in sorted(baseline.items()):
        src, dst = source / rel, destination / rel
        safe(src.parent)
        safe(dst.parent)
        info = src.lstat()
        kind = _link_kind(info)
        if kind:
            if entry.kind != kind or os.readlink(src) != entry.value:
                raise Blocked("RECOVERY_SOURCE_CHANGED")
            if kind == "junction":
                _copy_junction(src, dst)
            else:
                os.symlink(entry.value, dst, target_is_directory=kind == "directory-symlink")
        elif entry.kind == "directory" and stat.S_ISDIR(info.st_mode):
            if rel != ".":
                dst.mkdir(mode=0o700)
            directories.append((src, dst, entry))
        elif entry.kind == "file" and stat.S_ISREG(info.st_mode):
            with _open_regular(src, info) as reader, dst.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
                writer.flush()
                os.fsync(writer.fileno())
            _copy_metadata(src, dst, entry)
        else:
            raise Blocked("RECOVERY_SOURCE_CHANGED")
    for src, dst, entry in reversed(directories):
        safe(src)
        safe(dst)
        _copy_metadata(src, dst, entry)
    if snapshot(destination) != baseline:
        raise Blocked("RECOVERY_COPY_VERIFICATION_FAILED")


def create_recovery(vault: Path, run_root: Path,
                    baseline: dict[str, Entry]) -> tuple[Path, Path]:
    """After approval, create two independent copies without replacing any prior run."""
    vault, run_root = _absolute(vault), _absolute(run_root)
    ancestor = _destination(vault, run_root)
    if "." not in baseline or snapshot(vault) != baseline:
        raise Blocked("RECOVERY_SOURCE_CHANGED")
    required = 2 * sum(entry.size for entry in baseline.values())
    if shutil.disk_usage(ancestor).free < required:
        raise Blocked("RECOVERY_INSUFFICIENT_SPACE")
    for parent in reversed(run_root.parents):
        if not parent.exists():
            parent.mkdir(mode=0o700, exist_ok=True)
            safe(parent)
    safe(run_root)
    _make_private_run(run_root)
    backup, rehearsal = run_root / "backup", run_root / "test-copy"
    # A failed copy remains isolated in its unique run. Only these final names
    # advertise a verified copy; leave incomplete work available for diagnosis.
    staging = run_root / "backup.incomplete"
    _copy_tree(vault, staging, baseline)
    if snapshot(vault) != baseline:
        raise Blocked("RECOVERY_SOURCE_CHANGED")
    staging.rename(backup)
    staging = run_root / "test-copy.incomplete"
    _copy_tree(backup, staging, baseline)
    staging.rename(rehearsal)
    if snapshot(vault) != baseline:
        raise Blocked("RECOVERY_SOURCE_CHANGED")
    return backup, rehearsal
