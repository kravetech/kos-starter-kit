"""Release notes and verified package selection for guided Community setup."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys

# The installed skill and the command use the same standalone verifier.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/kos-community-fix/scripts"))
from community_asset import COMMUNITY_URL, ReleaseError, VERSION_PATTERN, version_parts, unpack, verified_archive


@dataclass(frozen=True)
class Release:
    root: Path
    version: str
    community_version: str
    digest: str

    def changes_since(self, installed_distribution):
        lower, upper = version_parts(installed_distribution), version_parts(self.version)
        if lower > upper:
            raise ReleaseError("A Community downgrade is not supported")
        expected = json.loads((self.root / "installer/release.json").read_text(encoding="utf-8-sig"))
        versions = {v for v in expected.get("supportedUpgradeVersions", []) if lower < version_parts(v) <= upper}
        if lower < upper:
            versions.add(self.version)
        changelog = self.root / "CHANGELOG.md"
        contents = changelog.read_text(encoding="utf-8-sig") if changelog.exists() else ""
        summaries = {}
        active = None
        for line in contents.splitlines():
            if line.startswith("## "):
                title = re.match(rf"## (?:KOS Community |\[)({VERSION_PATTERN})(?:\]|\s|$)", line)
                active = None
                if title and lower < version_parts(title[1]) <= upper:
                    active = title[1]
                    versions.add(active)
                    summaries.setdefault(active, [])
            elif active and line.startswith(("- ", "* ")):
                summaries[active].append(line[2:].strip())
            elif active and line.startswith(("  ", "\t")) and summaries[active] and line.strip():
                summaries[active][-1] += " " + line.strip()
        result = []
        for version in sorted(versions, key=version_parts):
            notes = summaries.get(version, [])
            result.append({"version": version, "changes": notes or ["Release notes unavailable for this version."],
                           "complete": bool(notes)})
        return result


@contextmanager
def open_release(source=COMMUNITY_URL):
    with verified_archive(source) as asset:
        root = unpack(asset, asset.path.parent / "package")
        yield Release(root, asset.version, asset.community_version, asset.digest)
