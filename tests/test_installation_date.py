"""Installation dates are local at first setup and historical thereafter."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_safety import ROOT, STATE, answers_read, apply, digest, encoded, json_read, plan, write


class InstallationDateTests(unittest.TestCase):
    def test_multiline_description_in_verified_legacy_readme(self):
        date_line_example = "First paragraph.\n\nInstalled: 1999-01-01\n\nSecond paragraph."
        ambiguous = "Reference metadata:\n\nOwner: Example\nTimezone: UTC\nInstalled: 1999-01-01\n\n## KOS Distribution"
        cases = (("## Core Areas", date_line_example, "2000-02-29"),
                 ("## KOS Distribution", date_line_example, "2000-02-29"),
                 ("## Core Areas", ambiguous, None))
        for boundary, description, expected in cases:
            with self.subTest(boundary=boundary, description=description), TemporaryDirectory() as temp:
                vault = Path(temp) / "vault"
                supplied = {"system": {"description": description, "installation_date": "2000-02-29"}}
                first, payload = plan(vault, "new", answers_read(supplied), "minimal")
                apply(vault, first, payload)
                state = json_read(vault / STATE)
                del state["installationDate"]
                heading = f"## KOS Community `{state['communityVersion']}`".encode()
                before_release, release_section = payload["README.md"].split(heading, 1)
                if boundary == "## Core Areas":
                    # Early releases had no version section between setup and the domain list.
                    legacy = before_release + b"## Core Areas\n" + release_section.split(b"## Core Areas\n", 1)[1]
                else:
                    legacy = before_release + b"## KOS Distribution" + release_section
                state.update(communityVersion="1.1.0", installerVersion="1.3.0", starterKitVersion="1.3.0")
                state["components"]["README.md"].update(installedHash=digest(legacy), sourceVersion="1.3.0")
                write(vault, "README.md", legacy)
                write(vault, STATE, encoded(state))
                upgrade, rendered = plan(vault, "upgrade", answers_read({}), supplied_answers={})
                self.assertEqual(upgrade.get("installationDate"), expected)
                self.assertEqual(json.loads(rendered[STATE]).get("installationDate"), expected)
                shell = shutil.which("powershell") or shutil.which("pwsh")
                if shell:
                    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "install.ps1"),
                                             "-Target", str(vault), "-Operation", "upgrade", "-DryRun"],
                                            capture_output=True, check=True, timeout=120)
                    self.assertEqual(json.loads(result.stdout.decode("utf-8-sig")).get("installationDate"), expected)

    def test_new_default_example_and_explicit_dates_survive_later_runs(self):
        instant = datetime(2030, 1, 31, 17, 30, tzinfo=timezone.utc)
        local_day = instant.astimezone(timezone(timedelta(hours=8))).date()
        example = json_read(ROOT / "installer/answers.example.json")
        self.assertNotIn("installation_date", example["system"])
        self.assertNotIn("installation_date", json_read(ROOT / "installer/defaults.json")["system"])
        for supplied, expected in (({}, "2030-02-01"), (example, "2030-02-01"),
                                   ({"system": {"installation_date": "2004-02-29"}}, "2004-02-29")):
            with self.subTest(expected=expected), TemporaryDirectory() as temp, patch("engine.date", wraps=date) as clock:
                vault = Path(temp) / "vault"
                clock.today.return_value = local_day
                first, payload = plan(vault, "new", answers_read(supplied), "minimal", supplied_answers=supplied)
                self.assertEqual(first["installationDate"], expected)
                self.assertEqual(json.loads(payload[STATE])["installationDate"], expected)
                for rel in ("README.md", "ARCHITECTURE.md", "CHANGELOG.md"):
                    self.assertIn(expected.encode(), payload[rel])
                # Applying one reviewed in-memory plan does not resample the clock.
                clock.today.return_value = local_day + timedelta(days=1)
                apply(vault, first, payload)
                for operation in ("upgrade", "repair"):
                    again, files = plan(vault, operation, answers_read(supplied), supplied_answers=supplied)
                    self.assertEqual(again["installationDate"], expected)
                    self.assertIsNone(apply(vault, again, files))
                prior = json_read(vault / STATE)
                prior.update(communityVersion="1.0.0", installerVersion="1.2.0", starterKitVersion="1.2.0")
                write(vault, STATE, encoded(prior))
                changed, files = plan(vault, "upgrade", answers_read(supplied), supplied_answers=supplied)
                self.assertEqual(changed["installationDate"], expected)
                self.assertIn(b"] - 2030-02-02", files["CHANGELOG.md"])

    def test_old_receipt_recovers_verified_date_and_never_invents_an_unknown_date(self):
        with TemporaryDirectory() as temp:
            vault = Path(temp) / "vault"
            answers = answers_read({"system": {"installation_date": "2001-07-08"}})
            first, payload = plan(vault, "new", answers, "minimal")
            apply(vault, first, payload)
            state = json_read(vault / STATE)
            del state["installationDate"]
            write(vault, STATE, encoded(state))
            later = {"system": {"installation_date": "2020-03-04"}}
            plan_old, result = plan(vault, "upgrade", answers_read(later), supplied_answers=later)
            self.assertEqual(plan_old["installationDate"], "2001-07-08")
            self.assertIn(b"Installed: 2001-07-08", result["README.md"])
            write(vault, "README.md", b"# Owner document\nInstalled: 2000-01-02\n")
            write(vault, "DESIGN.md", b"Edited design history\n")
            unknown, result = plan(vault, "repair", answers_read({}), supplied_answers={})
            self.assertNotIn("installationDate", unknown)
            self.assertNotIn("installationDate", json.loads(result[STATE]))
            self.assertEqual(result["DESIGN.md"], b"Edited design history\n")
            actions = {item["path"]: item["action"] for item in unknown["items"]}
            self.assertEqual(actions["README.md"], "PRESERVE")
            original = {"system": {"installation_date": "2001-07-08"}}
            recovered, _ = plan(vault, "repair", answers_read(original), supplied_answers=original)
            self.assertEqual(recovered["installationDate"], "2001-07-08")

    def test_adopting_edited_readme_does_not_verify_its_historical_date(self):
        with TemporaryDirectory() as temp:
            vault = Path(temp) / "vault"
            answers = answers_read({"system": {"installation_date": "2001-07-08"}})
            first, payload = plan(vault, "new", answers, "minimal")
            apply(vault, first, payload)
            state = json_read(vault / STATE)
            del state["installationDate"]
            original = (vault / "README.md").read_bytes()
            legacy = original.replace(state["communityVersion"].encode(), b"1.0.0")
            state.update(communityVersion="1.0.0", installerVersion="1.2.0", starterKitVersion="1.2.0")
            state["components"]["README.md"].update(sourceVersion="1.2.0", installedHash=digest(legacy))
            write(vault, STATE, encoded(state))
            write(vault, "README.md", legacy + b"\nLocal owner addition.\n")
            upgrade, files = plan(vault, "upgrade", answers_read({}), supplied_answers={})
            self.assertNotIn("installationDate", upgrade)
            self.assertIn(b"Local owner addition.", files["README.md"])
            self.assertNotEqual(files["README.md"], (vault / "README.md").read_bytes())
            apply(vault, upgrade, files)
            write(vault, "README.md", files["README.md"])
            refresh, files = plan(vault, "upgrade", answers_read({}), supplied_answers={})
            self.assertIsNotNone(apply(vault, refresh, files))
            self.assertNotIn("installationDate", json_read(vault / STATE))
            for operation in ("upgrade", "repair"):
                repeat, files = plan(vault, operation, answers_read({}), supplied_answers={})
                self.assertNotIn("installationDate", repeat)
                self.assertIsNone(apply(vault, repeat, files))
            explicit = {"system": {"installation_date": "2000-05-04"}}
            recovered, _ = plan(vault, "repair", answers_read(explicit), supplied_answers=explicit)
            self.assertEqual(recovered["installationDate"], "2000-05-04")
