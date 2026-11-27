"""Select, verify and unpack exactly one published KOS Community distribution."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import tempfile
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

COMMUNITY_URL = "https://github.com/kravetech/kos-community"
_API = "https://api.github.com/repos/kravetech/kos-community/releases"
_PART = r"(?:0|[1-9][0-9]*)"
VERSION_PATTERN = rf"{_PART}\.{_PART}\.{_PART}"
_LIMIT = 256 * 1024 * 1024
# Published customer ZIP digests. A known local attachment can be verified offline.
_KNOWN = {
    "1.3.0": "93c2dcd6c0a03d3d24ef0405bbcecceb7f425d476ea57e727026549eb0f1be7d",
    "1.3.1": "296f7a4ceda957d6c04242331c664988688eea789979d1881ef1cfda9c362376",
}


class ReleaseError(ValueError):
    """A stable, authentic Community release could not be established."""


def version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(VERSION_PATTERN, value):
        raise ReleaseError("Invalid distribution version")
    return tuple(map(int, value.split(".")))


def _metadata(version=None):
    selector = "latest" if version is None else "tags/v" + version
    req = Request(_API + "/" + selector, headers={"Accept": "application/vnd.github+json",
                                                 "User-Agent": "kos-community-setup"})
    with urlopen(req, timeout=30) as res:
        body = res.read(4_000_001)
    if len(body) > 4_000_000:
        raise ReleaseError("Release metadata exceeds the supported limit")
    record = json.loads(body)
    tag = record.get("tag_name")
    if (record.get("draft") is not False or record.get("prerelease") is not False
            or not isinstance(tag, str) or not re.fullmatch("v" + VERSION_PATTERN, tag)
            or version is not None and tag != "v" + version):
        raise ReleaseError("A matching stable Community release is required")
    version = tag[1:]
    prefix = "kos-community" if version_parts(version) >= (1, 3, 1) else "kos-starter-kit"
    name = f"{prefix}-{tag}.zip"
    assets = [a for a in record.get("assets", []) if a.get("name") == name]
    if len(assets) != 1:
        raise ReleaseError("The published Community installer asset is missing or ambiguous")
    asset = assets[0]
    digest = asset.get("digest") or ""
    if not re.fullmatch("sha256:[0-9a-fA-F]{64}", digest):
        raise ReleaseError("The published installer has no verified SHA-256 digest")
    url = f"{COMMUNITY_URL}/releases/download/{tag}/{name}"
    if asset.get("browser_download_url") != url:
        raise ReleaseError("Unexpected installer download location")
    return version, digest[7:].lower(), url


def _copy_zip(stream, dest):
    size = 0
    digest = hashlib.sha256()
    with dest.open("xb") as out:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if size > _LIMIT:
                raise ReleaseError("Installer ZIP exceeds the supported size")
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest()


def _release_identity(archive):
    record = archive.getinfo("installer/release.json")
    if record.file_size > 65536:
        raise ReleaseError("Oversized installer identity record")
    meta = json.loads(archive.read(record).decode("utf-8-sig"))
    if not isinstance(meta, dict) or meta.get("edition") not in {"community", "starter"}:
        raise ReleaseError("The selected file is not a Community installer")
    version = meta.get("starterKitVersion")
    community = meta.get("communityVersion")
    version_parts(version)
    version_parts(community)
    if meta.get("installerVersion") != version or (version_parts(version) >= (1, 3, 1) and community != version):
        raise ReleaseError("Inconsistent Community installer version")
    return version, community


def member_path(name):
    """Reject archive names that would change meaning on a supported filesystem."""
    parts = name.split("/")
    for part in parts:
        if (part in {"", ".", ".."} or part.endswith((".", " "))
                or any(ord(c) < 32 or c in '\\:<>"|?*' for c in part)
                or re.match(r"(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)", part)):
            raise ReleaseError("Unsafe installer member name")
    return name


def _extract(archive, dest):
    paths = {}
    total = 0
    if len(archive.infolist()) > 25000:
        raise ReleaseError("Too many installer entries")
    for item in archive.infolist():
        path = member_path(item.filename[:-1] if item.is_dir() else item.filename)
        kind = stat.S_IFMT(item.external_attr >> 16)
        if item.flag_bits & 1 or kind not in {0, stat.S_IFDIR if item.is_dir() else stat.S_IFREG}:
            raise ReleaseError("Unsupported installer entry: " + path)
        if path.casefold() in paths:
            raise ReleaseError("Duplicate installer path: " + path)
        paths[path.casefold()] = path
        total += item.file_size
        if total > _LIMIT:
            raise ReleaseError("Expanded installer exceeds the supported size")
        target = dest / path
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(item) as source, target.open("xb") as out:
            shutil.copyfileobj(source, out)
        if path.endswith(".sh"):
            target.chmod(0o700)


@dataclass(frozen=True)
class Asset:
    path: Path
    version: str
    community_version: str
    digest: str


def is_repository(source):
    return str(source).rstrip("/") in {COMMUNITY_URL, COMMUNITY_URL + ".git", COMMUNITY_URL + "/releases/latest"}


@contextmanager
def verified_archive(source=COMMUNITY_URL):
    """Materialize verified bytes privately for the lifetime of the caller's operation."""
    value = str(source)
    remote = is_repository(source)
    if not remote and ("://" in value or Path(source).suffix.lower() != ".zip"):
        raise ReleaseError("Supply the official KOS Community repository URL or a local Community ZIP")
    with tempfile.TemporaryDirectory(prefix="kos-community-release-") as temp:
        work = Path(temp)
        pinned = work / "release.zip"
        try:
            if remote:
                wanted, checksum, url = _metadata()
                request = Request(url, headers={"User-Agent": "kos-community-setup"})
                with urlopen(request, timeout=60) as stream:
                    if urlparse(stream.geturl()).scheme != "https":
                        raise ReleaseError("A secure installer download is required")
                    received = _copy_zip(stream, pinned)
            else:
                with Path(source).open("rb") as stream:
                    received = _copy_zip(stream, pinned)
                wanted = next((v for v, h in _KNOWN.items() if h == received), None)
                if wanted is None:
                    with zipfile.ZipFile(pinned) as archive:
                        candidate, _ = _release_identity(archive)
                    if candidate in _KNOWN:
                        raise ReleaseError("Community ZIP differs from its published SHA-256")
                    wanted, checksum, _ = _metadata(candidate)
                else:
                    checksum = _KNOWN[wanted]
            if received != checksum or (wanted in _KNOWN and _KNOWN[wanted] != received):
                raise ReleaseError("Community ZIP differs from its published SHA-256")
            with zipfile.ZipFile(pinned) as archive:
                version, community = _release_identity(archive)
                if version != wanted:
                    raise ReleaseError("The installer version does not match its published tag")
                if "installer/install.py" not in archive.namelist():
                    raise ReleaseError("The package is missing its installer")
        except ReleaseError:
            raise
        except (OSError, KeyError, TypeError, ValueError, RuntimeError, zipfile.BadZipFile, URLError) as error:
            raise ReleaseError(f"Unable to open official Community release: {error}") from error
        yield Asset(pinned, version, community, received)


def unpack(asset, destination):
    """Extract a verified immutable local copy into a fresh private directory."""
    destination.mkdir(mode=0o700)
    try:
        with zipfile.ZipFile(asset.path) as archive:
            _extract(archive, destination)
    except (OSError, KeyError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        raise ReleaseError(f"Unable to unpack Community release: {error}") from error
    return destination
