"""Regression coverage for the public Community release bootstrap."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "installer"))
import setup_release as releases
import community_asset as assets


def package(version="2.1.0", community=None, edition="community", extra=None):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("installer/release.json", json.dumps({
            "starterKitVersion": version, "installerVersion": version,
            "edition": edition, "communityVersion": community or version,
            "supportedUpgradeVersions": ["1.0.0", "1.1.0", "1.2.0", version],
        }))
        archive.writestr("installer/install.py", "")
        archive.writestr("CHANGELOG.md", f"## KOS Community {version}\n- Target changes\n"
                         "## [1.2.0] Historical\n- Intermediate changes\n  and details\n")
        if extra:
            archive.writestr(*extra)
    return buffer.getvalue()


class Download(BytesIO):
    def geturl(self):
        return "https://release-assets.githubusercontent.com/asset"


class SetupReleaseTests(unittest.TestCase):
    def setUp(self):
        self.space = tempfile.TemporaryDirectory()
        self.addCleanup(self.space.cleanup)
        self.attachment = Path(self.space.name) / "upload 2.zip"

    def test_renamed_zip_uses_its_published_tag_and_independent_pinned_copy(self):
        data = package()
        self.attachment.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        with patch.object(assets, "_metadata", return_value=("2.1.0", digest, "unused")) as metadata:
            with releases.open_release(self.attachment) as release:
                self.attachment.write_bytes(b"replaced after verification")
                self.assertEqual("2.1.0", release.community_version)
                self.assertEqual(digest, release.digest)
                self.assertTrue((release.root / "installer/install.py").is_file())
                result = release.changes_since("1.0.0")
                self.assertEqual(["1.1.0", "1.2.0", "2.1.0"], [row["version"] for row in result])
                self.assertFalse(result[0]["complete"])
                self.assertEqual(["Intermediate changes and details"], result[1]["changes"])
                self.assertTrue(result[2]["complete"])
                self.assertEqual([], release.changes_since("2.1.0"))
                with self.assertRaises(releases.ReleaseError):
                    release.changes_since("2.2.0")
            self.assertFalse(release.root.exists())
            metadata.assert_called_once_with("2.1.0")

    def test_latest_resolves_once_even_when_tag_changes_later(self):
        data = package()
        digest = hashlib.sha256(data).hexdigest()
        url = releases.COMMUNITY_URL + "/releases/download/v2.1.0/kos-community-v2.1.0.zip"
        metadata = {"tag_name": "v2.1.0", "draft": False, "prerelease": False, "assets": [
            {"name": "kos-community-v2.1.0.zip", "digest": "sha256:" + digest, "browser_download_url": url}]}
        responses = [BytesIO(json.dumps(metadata).encode()), Download(data)]
        with patch.object(assets, "urlopen", side_effect=responses) as fetch:
            with releases.open_release(releases.COMMUNITY_URL) as release:
                self.assertEqual("2.1.0", release.version)
                self.assertEqual(1, len(release.changes_since("1.2.0")))
            self.assertEqual([assets._API + "/latest", url],
                             [call.args[0].full_url for call in fetch.call_args_list])

    def test_source_archives_wrong_sources_and_untrusted_bytes_are_rejected(self):
        for source in ["https://example.org/download.zip", releases.COMMUNITY_URL + "/tree/main",
                       "https://github.com/unrelated/kos-community", "file.txt"]:
            with self.subTest(source=source), self.assertRaises(releases.ReleaseError):
                with releases.open_release(source):
                    self.fail()
        with zipfile.ZipFile(self.attachment, "w") as archive:
            archive.writestr("kos-community-main/installer/release.json", "{}")
        with self.assertRaises(releases.ReleaseError), releases.open_release(self.attachment):
            self.fail()
        for data in [package(edition="pro"), package("1.3.1")]:
            self.attachment.write_bytes(data)
            with patch.object(assets, "_metadata") as lookup, self.assertRaises(releases.ReleaseError):
                with releases.open_release(self.attachment):
                    self.fail()
            lookup.assert_not_called()
        self.attachment.write_bytes(package())
        with patch.object(assets, "_metadata", return_value=("2.1.0", "0" * 64, "")):
            with self.assertRaisesRegex(releases.ReleaseError, "SHA-256"), releases.open_release(self.attachment):
                self.fail()

    def test_historical_community_version_can_differ_from_distribution(self):
        data = package("1.2.0", community="1.0.0")
        self.attachment.write_bytes(data)
        with patch.dict(assets._KNOWN, {"1.2.0": hashlib.sha256(data).hexdigest()}):
            with patch.object(assets, "_metadata") as lookup, releases.open_release(self.attachment) as release:
                self.assertEqual(("1.2.0", "1.0.0"), (release.version, release.community_version))
                lookup.assert_not_called()

    def test_refuse_unsafe_archive_members_even_with_matching_digest(self):
        link = zipfile.ZipInfo("linked")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for entry in ["../outside", "/absolute", "drive:stream", "CON", link]:
            with self.subTest(entry=str(entry)):
                data = package(extra=(entry, "destination"))
                self.attachment.write_bytes(data)
                with patch.dict(assets._KNOWN, {"2.1.0": hashlib.sha256(data).hexdigest()}):
                    with self.assertRaises(releases.ReleaseError), releases.open_release(self.attachment):
                        self.fail()

    def test_stable_metadata_requires_unique_named_asset_and_published_digest(self):
        name = "kos-starter-kit-v1.2.0.zip"
        url = releases.COMMUNITY_URL + "/releases/download/v1.2.0/" + name
        asset = {"name": name, "digest": "sha256:" + "a" * 64, "browser_download_url": url}
        base = {"tag_name": "v1.2.0", "draft": False, "prerelease": False, "assets": [asset]}
        for invalid in [dict(base, tag_name="v1.2.1"), dict(base, draft=True), dict(base, prerelease=True),
                        dict(base, assets=[asset, asset]), dict(base, assets=[dict(asset, digest=None)]),
                        dict(base, assets=[dict(asset, browser_download_url="https://example.org/asset")])]:
            with self.subTest(record=invalid), patch.object(assets, "urlopen", return_value=BytesIO(json.dumps(invalid).encode())):
                with self.assertRaises(releases.ReleaseError):
                    assets._metadata("1.2.0")
        with patch.object(assets, "urlopen", return_value=BytesIO(json.dumps(base).encode())):
            self.assertEqual(("1.2.0", "a" * 64, url), assets._metadata("1.2.0"))
