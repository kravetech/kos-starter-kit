"""Check actual preservation and link resolution on synthetic vaults."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "installer"))

from engine import apply, answers_read, plan
from packages import plan_package, REGISTRIES
from safety import STATE, digest, encoded
from setup_audit import capture_audit, compare_audits, plan_guard


class SetupAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir()

    def write(self, rel, data):
        path = self.vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, dict):
            data = encoded(data)
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)

    def test_link_destinations_and_baseline(self):
        self.write("Notes/a.md", "---\naliases: [Agenda]\n---\n# First Heading\nText ^marker")
        self.write("Media/picture.png", b"sample")
        self.write("Index.md", "[[a|my alias]] ![[Agenda#First Heading]] [[Notes/a#^marker]]\n"
                              "[relative](Notes/a.md#first-heading) ![pic](Media/picture.png)\n"
                              "[[already absent]]\n")
        before = capture_audit(self.vault)
        stable = compare_audits(before, capture_audit(self.vault))
        self.assertEqual([], stable["blockers"])
        self.assertEqual(1, len(stable["links"]["preexisting"]))
        self.write("Notes/a.md", "---\naliases: [Agenda]\n---\n# Renamed Heading")
        self.write("Archive/a.md", "# Same basename")
        (self.vault / "Media/picture.png").unlink()
        result = compare_audits(before, capture_audit(self.vault))
        self.assertEqual(5, len(result["links"]["regressions"]))
        self.assertEqual(1, len(result["links"]["preexisting"]))
        self.assertIn("LINK_AMBIGUOUS: Index.md:1", result["blockers"])

    def test_same_text_resolves_to_new_note_and_new_broken_reference(self):
        self.write("Old/a.md", "# A")
        self.write("Index.md", "[[a]]")
        before = capture_audit(self.vault)
        (self.vault / "Old/a.md").unlink()
        self.write("New/a.md", "# A")
        self.write("Another.md", "[[missing]]")
        result = compare_audits(before, capture_audit(self.vault))
        self.assertIn("LINK_REDIRECTED: Index.md:1", result["blockers"])
        self.assertIn("LINK_MISSING: Another.md:1", result["blockers"])

    def test_code_external_and_dynamic_links(self):
        fence = chr(96) * 3
        self.write("Intro.md", "# Intro\n[here](#intro) [site](https://example.org/)\n" +
                   fence + "dataview\n[[not static]]\n" + fence + "\n" +
                   chr(96) + "[[example]]" + chr(96) + "\n")
        snap = capture_audit(self.vault)
        result = compare_audits(snap, snap)
        self.assertEqual(1, result["links"]["references"])
        self.assertEqual([], result["blockers"])
        self.assertTrue(any("dynamic plugin" in w for w in result["warnings"]))

    def test_relative_markdown_is_not_hijacked_by_root_names(self):
        self.write("Notes/Start.md", "[a](Sub/a.md)")
        self.write("Sub/a.md", "# Wrong directory")
        self.write("Notes/Sub/a.md", "# Correct directory")
        snap = capture_audit(self.vault)
        self.assertEqual(("Notes/Sub/a.md",), next(iter(snap.links.values()))[1])

    def test_setext_heading_and_new_duplicate_block(self):
        self.write("Anchor.md", "Main title\n==========\nLine ^id\n")
        self.write("Source.md", "[[Anchor#Main title]] [[Anchor#^id]]")
        before = capture_audit(self.vault)
        self.assertTrue(all(info[0] == "resolved" for info in before.links.values()))
        self.write("Anchor.md", "Main title\n==========\nLine ^id\nAnother ^id\n")
        self.assertIn("LINK_AMBIGUOUS: Source.md:1", compare_audits(before, capture_audit(self.vault))["blockers"])

    def test_ownership_and_occupied_id_before_apply(self):
        path = ".agents/skills/handmade/SKILL.md"
        self.write(path, "# User skill")
        self.write("AGENTS.md", "Customized router")
        self.write(STATE, {"components": {"AGENTS.md": {"ownership": "managed-customizable",
                   "installedHash": digest(b"released"), "sourceVersion": "1.2.0"}}})
        before = capture_audit(self.vault)
        def check_item(rel, action):
            return plan_guard(self.vault, {"targetType": "managed-kos", "items": [
                {"path": rel, "action": action, "componentId": "example"}]}, before)
        self.assertIn("OCCUPIED_COMPONENT_PATH: " + path, check_item(path, "PROPOSE"))
        self.assertIn("PROTECTED_FILE_WRITE: AGENTS.md", check_item("AGENTS.md", "UPDATE_SAFE"))
        self.assertEqual([], check_item("AGENTS.md", "PROPOSE"))
        self.assertTrue(any("PACKAGE_ID_COLLISION" in issue for issue in
                            check_item(".agents/skills/handmade/2.0.0/manifest.json", "CREATE")))
        self.write(path, "Replaced")
        result = compare_audits(before, capture_audit(self.vault))
        self.assertIn("PROTECTED_FILE_CHANGED: " + path, result["blockers"])

    def test_portable_declared_ids_can_differ_from_folder_names(self):
        self.write(".agents/skills/mine/SKILL.md", "---\nname: 'meeting-tools'\n---\n# My skill")
        self.write("Tools/mine/module.json", {"id": "meeting-module"})
        self.write("Tools/unknown/module.json", {"vendorFormat": 4})
        before = capture_audit(self.vault)
        self.assertTrue(any("declared identity unverified: Tools/unknown/module.json" in w for w in before.warnings))
        keep = compare_audits(before, before)["extensions"]["preservedPortablePaths"]
        self.assertIn(".agents/skills/mine/SKILL.md", keep)
        for declared in ("meeting-tools", "meeting-module"):
            path = f".agents/skills/{declared}/1.0.0/SKILL.md"
            preview = {"items": [{"path": path, "action": "CREATE"}]}
            self.assertIn(f"PACKAGE_ID_COLLISION: {declared} at {path}", plan_guard(self.vault, preview, before))
        self.write("Tools/added/module.json", {"id": "meeting-module"})
        self.assertIn("PORTABLE_ID_COLLISION: meeting-module at Tools/added/module.json",
                      compare_audits(before, capture_audit(self.vault))["blockers"])

    def test_real_package_metadata_and_host_contract(self):
        apply(self.vault, *plan(self.vault, "new", answers_read({})))
        for kind, name in (("skill", "project-action-list-skill"), ("powerup", "project-action-list")):
            fixture = ROOT / "examples/project-action-list" / kind
            apply(self.vault, *plan_package(self.vault, "install", fixture, permission_approval=True))
            if kind == "skill":
                apply(self.vault, *plan_package(self.vault, "enable", package_id=name))
        original = capture_audit(self.vault)
        self.assertFalse(original.issues)
        copy = Path(self.tmp.name) / "rehearsal"
        shutil.copytree(self.vault, copy)
        copied = capture_audit(copy)
        self.assertEqual([], compare_audits(original, copied)["blockers"])
        registry = REGISTRIES["powerup"]
        data = json.loads((self.vault / registry).read_bytes())
        data["packages"]["project-action-list"]["enabled"] = True
        self.write(registry, data)
        state = json.loads((self.vault / STATE).read_bytes())
        state["kosContractVersion"] = "2.0.0"
        self.write(STATE, state)
        result = compare_audits(original, capture_audit(self.vault))
        self.assertEqual(["project-action-list-skill"], result["extensions"]["preservedRegisteredIds"])
        self.assertTrue(any("PACKAGE_REGISTRATION_CHANGED" in i for i in result["blockers"]))
        self.assertTrue(any("COMPATIBILITY" in i for i in result["blockers"]))

    def test_historical_template_hash_and_unknown_file_remain_distinct(self):
        self.write("00 - System/Installation/installer-state.json", {"installer_version": "1.1.0"})
        history = json.loads((ROOT / "installer/historical-templates.json").read_bytes())["templates"]
        template = next(record for record in history if record["path"] == "CODEX.md")
        self.write("CODEX.md", template["text"])
        self.write("CLAUDE.md", "Custom user binding.")
        for business_note in ("Operations", "Products", "Strategy"):
            self.write(f"01 - Business/{business_note}.md", "# " + business_note)
        before = capture_audit(self.vault)
        preview, payload = plan(self.vault, "upgrade", answers_read({}))
        self.assertEqual("UPDATE_SAFE", next(i["action"] for i in preview["items"] if i["path"] == "CODEX.md"))
        self.assertEqual([], plan_guard(self.vault, preview, before))
        apply(self.vault, preview, payload)
        after = capture_audit(self.vault)
        self.assertEqual([], compare_audits(before, after, preview)["blockers"])
        self.write("CODEX.md", "Unapproved output.")
        self.assertIn("PROTECTED_FILE_CHANGED: CODEX.md",
                      compare_audits(before, capture_audit(self.vault), preview)["blockers"])

    def test_older_receipt_can_gain_previously_unrecorded_settings_and_capabilities(self):
        self.write(STATE, {"components": {}, "providers": ["codex"]})
        before = capture_audit(self.vault)
        self.write(STATE, {"components": {}, "providers": ["codex"], "installationDate": "2024-03-01",
                           "privacy": {"restricted_folders": ["Private"]}})
        self.write("00 - System/Config/capabilities.json", {"capabilities": [
            {"id": "kos.new", "paths": ["Tool.md"], "version": "1.0.0"}]})
        self.assertEqual([], compare_audits(before, capture_audit(self.vault))["blockers"])


if __name__ == "__main__":
    unittest.main()
