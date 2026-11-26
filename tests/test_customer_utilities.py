"""Customer manifests and compatibility with earlier installer questionnaires."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import tooling
from engine import answers_read
from safety import Blocked


class CustomerUtilityTests(unittest.TestCase):
    def test_manifest_hashes_only_the_shipped_or_frozen_source_files(self):
        with tempfile.TemporaryDirectory() as directory:
            kit = Path(directory)
            customer_list = "installer/archive-files.json"
            files = json.loads((ROOT / customer_list).read_bytes())["files"]
            self.assertIn(customer_list, files)
            for name in files:
                destination = kit / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, destination)
            extra = kit / "local-notes.md"
            extra.write_text("Local addition", encoding="utf-8")
            output = kit / "build/file-manifest.json"
            for _ in range(2):
                tooling.manifest(kit, output)
                result = json.loads(output.read_bytes())["files"]
                self.assertEqual([entry["path"] for entry in result], files)
                for entry in result:
                    data = (kit / entry["path"]).read_bytes()
                    self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
                    self.assertEqual(entry["bytes"], len(data))
            with self.assertRaisesRegex(Blocked, "MANIFEST_OUTPUT_IS_INPUT"):
                tooling.manifest(kit, kit / customer_list)
            (kit / "scripts/release.py").touch()
            with self.assertRaises(FileNotFoundError):
                tooling.manifest(kit, output)
            source_list = kit / "installer/release-files.json"
            source_list.write_text(json.dumps({"files": [customer_list, "local-notes.md"]}), encoding="utf-8")
            tooling.manifest(kit, output)
            self.assertEqual([f["path"] for f in json.loads(output.read_bytes())["files"]],
                             [customer_list, "local-notes.md"])

    def test_earlier_fixed_options_accept_only_the_previous_values(self):
        fixed = {"include_gitkeep": True, "enable_windows_scripts": True,
                 "enable_unix_scripts": True, "configure_external_integrations": False}
        for source in ("installer/defaults.json", "installer/answers.example.json"):
            self.assertTrue(fixed.keys().isdisjoint(json.loads((ROOT / source).read_bytes())["installation"]))
        schema = json.loads((ROOT / "installer/schemas/answers.schema.json").read_bytes())
        self.assertEqual(schema, json.loads((ROOT / "installer/questionnaire.schema.json").read_bytes()))
        self.assertEqual(answers_read({"installation": fixed})["installation"] | fixed,
                         answers_read({})["installation"] | fixed)
        for name, previous in fixed.items():
            with self.subTest(name=name):
                self.assertIs(schema["properties"]["installation"]["properties"][name]["const"], previous)
                with self.assertRaisesRegex(Blocked, "^FIXED_INSTALLATION_OPTION:" + name + "$"):
                    answers_read({"installation": {name: not previous}})
