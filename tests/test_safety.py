"""Synthetic migration and negative security fixtures; no real vaults."""
import copy
import base64
import secrets
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT / "installer"))
from safety import Blocked, STATE, RUNS, digest, encoded, inventory, json_read, merge_existing, safe
from engine import answers_read, apply, detect, plan
from packages import effective_config, plan_package, read_package
from transaction import Transaction, rollback
from core import core_plan
from validation import validate_installation


def write(root, rel, data):
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


class SafetyTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / "test-output"
        base.mkdir(exist_ok=True)
        self.base = base / ("safety-" + uuid.uuid4().hex)
        self.base.mkdir()
        self.vault = self.base / "vault"
        self.answers = answers_read(json_read(ROOT / "installer/answers.example.json"))
        self.answers["installation"]["providers"] = ["codex", "claude", "gemini"]

    def tearDown(self):
        # Verify absolute scope before recursive fixture cleanup.
        self.assertEqual(self.base.resolve().parent, (ROOT / "test-output").resolve())
        shutil.rmtree(self.base)

    def install(self, operation="new", profile="standard", decisions=None):
        p, data = plan(self.vault, operation, self.answers, profile, decisions)
        self.assertFalse(p["blocked"])
        return apply(self.vault, p, data)

    def package(self, kind="skill", version="1.0.0", content="Synthetic skill\n", **extra):
        source = self.base / (kind + version + str(len(list(self.base.iterdir()))))
        entry = "SKILL.md" if kind == "skill" else "README.md"
        manifest = {"schemaVersion": "1.0.0", "schema": "kos-skill/v1" if kind == "skill" else "kos-powerup/v1" if kind == "powerup" else "kos-package/v1", "type": kind, "id": "example." + kind,
                    "name": "Synthetic example", "version": version, "creator": "Example Author", "license": "Apache-2.0",
                    "compatibility": {"min": "1.0.0", "maxExclusive": "2.0.0"}, "supportedEditions": ["community", "pro"],
                    "scope": "both", "permissions": [], "dependencies": {}, "entrypoints": [entry], "entrypoint": entry,
                    "enabledByDefault": True, "configurationSchema": {}, "defaults": {}, "integrity": {entry: digest(content.encode())}, **extra}
        write(source, "manifest.json", encoded(manifest))
        write(source, "payload/" + entry, content)
        return source

    def pkg(self, command, source=None, kind="skill", **kwargs):
        p, payload = plan_package(self.vault, command, package=source, package_id="example." + kind, **kwargs)
        self.assertFalse(p["blocked"])
        return apply(self.vault, p, payload)

    def test_new_validation_and_repeat_upgrade(self):
        self.install()
        self.assertFalse([x for x in validate_installation(self.vault) if x["severity"] == "error"])
        before = inventory(self.vault)
        self.assertIsNone(self.install("upgrade"))
        self.assertEqual(before, inventory(self.vault))
        with self.assertRaises(Blocked):
            self.install("new")

    def test_core_contract_stamp_and_legacy_staging_guard(self):
        self.install()
        state = json_read(self.vault / STATE)
        self.assertEqual(state["kosContractVersion"], "1.0.0")
        state["kosContractVersion"] = "1.1.0"
        write(self.vault, STATE, encoded(state))
        with self.assertRaisesRegex(Blocked, "CONTRACT_DOWNGRADE"):
            plan(self.vault, "upgrade", self.answers)

    def test_configuration_schema_constraints_fail_closed(self):
        from contracts import validate
        validate("2026-09-19", {"type": "string", "format": "date"})
        validate({"custom": [1, 2]}, {"type": "object"})
        for value, schema in [
            ("2026-02-30", {"type": "string", "format": "date"}),
            ("20260919", {"type": "string", "format": "date"}),
            ({}, {"$ref": "https://example.invalid/schema"}),
            (True, {"type": "number"}),
            (3, {"type": "integer", "maximum": 2}),
            ([1, 2], {"type": "array", "maxItems": 1}),
        ]:
            with self.subTest(value=value, schema=schema), self.assertRaises(Blocked):
                validate(value, schema)

    def test_legacy_answer_file_target_argument_remains_optional(self):
        answer_file = self.base / "answers.json"
        answers = copy.deepcopy(self.answers)
        answers["installation"]["target_directory"] = str(self.vault)
        answer_file.write_bytes(encoded(answers))
        commands = [[sys.executable, str(ROOT / "installer/install.py"), "--answers", str(answer_file), "--dry-run"]]
        for shell in ("pwsh", "powershell"):
            executable = shutil.which(shell)
            if executable:
                commands.append([executable, "-NoProfile", "-File", str(ROOT / "install.ps1"), "-Answers", str(answer_file), "-DryRun"])
        for command in commands:
            with self.subTest(engine=command[0]):
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=90)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertFalse(json.loads(result.stdout)["blocked"])
        self.assertFalse(self.vault.exists())

    def test_existing_vault_migration_requires_explicit_approval(self):
        write(self.vault, ".obsidian/app.json", '{"userChoice":true}')
        original = (self.vault / ".obsidian/app.json").read_bytes()
        answer_file = self.base / "answers.json"
        answer_file.write_bytes(encoded(self.answers))
        commands = [[sys.executable, str(ROOT / "installer/install.py"), "--answers", str(answer_file),
                     "--target", str(self.vault), "--migration"]]
        for shell in ("pwsh", "powershell"):
            executable = shutil.which(shell)
            if executable:
                commands.append([executable, "-NoProfile", "-File", str(ROOT / "install.ps1"),
                                 "-Answers", str(answer_file), "-Target", str(self.vault), "-Migration"])
        for command in commands:
            with self.subTest(engine=command[0]):
                result = subprocess.run(command, input="", capture_output=True, text=True,
                                        encoding="utf-8", timeout=90)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertIn("Approval required", result.stdout)
                self.assertFalse((self.vault / STATE).exists())
                self.assertEqual(original, (self.vault / ".obsidian/app.json").read_bytes())

    def test_obsolete_backup_setting_is_rejected_before_migration(self):
        answers = copy.deepcopy(self.answers)
        answers["installation"]["backup_before_migration"] = True
        with self.assertRaisesRegex(Blocked, "BACKUP_SETTING_UNSUPPORTED"):
            answers_read(answers)
        write(self.vault, ".obsidian/app.json", "{}")
        before = inventory(self.vault)
        answer_file = self.base / "legacy-answers.json"
        answer_file.write_bytes(encoded(answers))
        commands = [[sys.executable, str(ROOT / "installer/install.py"), "--answers", str(answer_file),
                     "--target", str(self.vault), "--operation", "enhance", "--dry-run"]]
        for shell in ("pwsh", "powershell"):
            executable = shutil.which(shell)
            if executable:
                commands.append([executable, "-NoProfile", "-File", str(ROOT / "install.ps1"),
                                 "-Answers", str(answer_file), "-Target", str(self.vault),
                                 "-Operation", "enhance", "-DryRun"])
        for command in commands:
            with self.subTest(engine=command[0]):
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=90)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertIn("BACKUP_SETTING_UNSUPPORTED", result.stdout + result.stderr)
                self.assertEqual(before, inventory(self.vault))

    def test_pro_vault_is_not_a_community_migration_source(self):
        write(self.vault, "00 - System/Core/version.json",
              encoded({"product_id": "kos-pro", "edition": "pro", "product_version": "1.0.0"}))
        write(self.vault, "AGENTS.md", "Pro routing")
        write(self.vault, "CONTEXT-POLICY.md", "Pro policy")
        write(self.vault, ".obsidian/app.json", "{}")
        before = inventory(self.vault)
        self.assertEqual("pro-kos", detect(self.vault))
        for operation in ("upgrade", "enhance"):
            with self.subTest(operation=operation), self.assertRaises(Blocked):
                plan(self.vault, operation, self.answers)
        commands = [[sys.executable, str(ROOT / "installer/install.py"), "--target", str(self.vault),
                     "--migration", "--approve"]]
        for shell in ("pwsh", "powershell"):
            executable = shutil.which(shell)
            if executable:
                commands.append([executable, "-NoProfile", "-File", str(ROOT / "install.ps1"),
                                 "-Target", str(self.vault), "-Migration", "-Approve"])
        for command in commands:
            with self.subTest(engine=command[0]):
                result = subprocess.run(command, input="", capture_output=True, text=True,
                                        encoding="utf-8", timeout=90)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertEqual(before, inventory(self.vault))

    def test_managed_pro_state_is_rejected(self):
        self.install()
        state = json_read(self.vault / STATE)
        state["edition"] = "pro"
        write(self.vault, STATE, encoded(state))
        with self.assertRaises(Blocked):
            plan(self.vault, "upgrade", self.answers)

    def test_planning_zero_writes_deterministic_unicode(self):
        self.vault = self.base / "知识 café"
        first, _ = plan(self.vault, "new", self.answers)
        second, _ = plan(self.vault, "new", self.answers)
        self.assertEqual(first, second)
        self.assertFalse(self.vault.exists())
        self.install()

    def test_managed_update_and_customized_proposal(self):
        self.install()
        state = json_read(self.vault / STATE)
        for rel in ("CODEX.md", "CLAUDE.md"):
            write(self.vault, rel, "Historical managed adapter\n")
            state["components"][rel]["installedHash"] = digest(b"Historical managed adapter\n")
        state["starterKitVersion"] = "1.1.0"
        write(self.vault, STATE, encoded(state))
        write(self.vault, "CLAUDE.md", "User customization\n")
        p, payload = plan(self.vault, "upgrade", self.answers)
        actions = {i["path"]: i["action"] for i in p["items"]}
        self.assertEqual(actions["CODEX.md"], "UPDATE_SAFE")
        self.assertEqual(actions["CLAUDE.md"], "PROPOSE")
        run = apply(self.vault, p, payload)
        self.assertEqual((self.vault / "CLAUDE.md").read_text(), "User customization\n")
        self.assertTrue((self.vault / RUNS / run / "proposals/CLAUDE.md").is_file())
        self.assertIsNone(self.install("upgrade"))

    def test_legacy_10_11_preserve_uncertain_knowledge(self):
        for legacy in ("1.0.0", "1.1.0"):
            self.vault = self.base / legacy
            write(self.vault, "00 - System/Installation/installer-state.json", encoded({"installer_version": legacy}))
            write(self.vault, "AGENTS.md", "Customized legacy router")
            write(self.vault, "notes/project.md", "User knowledge")
            self.install("upgrade")
            self.assertEqual((self.vault / "notes/project.md").read_text(), "User knowledge")
            self.assertEqual((self.vault / "AGENTS.md").read_text(), "Customized legacy router")

    def test_obsidian_minimal_conflicts_idempotent(self):
        write(self.vault, ".obsidian/app.json", '{"userChoice":true}')
        write(self.vault, "AGENTS.md", "Existing router")
        write(self.vault, "Notes/reference.md", "[[other]]")
        before = (self.vault / ".obsidian/app.json").read_bytes()
        self.install("enhance", "minimal")
        self.assertFalse((self.vault / "01 - Business").exists())
        self.assertEqual(before, (self.vault / ".obsidian/app.json").read_bytes())
        self.assertEqual((self.vault / "Notes/reference.md").read_text(), "[[other]]")
        self.assertIsNone(self.install("enhance", "minimal"))

    def test_obsidian_link_audit_and_byte_preservation(self):
        write(self.vault, ".obsidian/app.json", "{}")
        links = ("[[Alpha|label]] ![[diagram.png]] "
                 "[relative](../Docs/Guide%20One.md) "
                 "[root](Docs/Guide%20One.md#Section) [[Missing]]\n")
        write(self.vault, "Notes/Start.md", links)
        write(self.vault, "Notes/Alpha.md", "# Alpha\n")
        write(self.vault, "Docs/Guide One.md", "# Guide\n")
        write(self.vault, "Media/diagram.png", b"synthetic image bytes")
        preserved = {rel: (self.vault / rel).read_bytes() for rel in
                     ("Notes/Start.md", "Notes/Alpha.md", "Docs/Guide One.md",
                      "Media/diagram.png", ".obsidian/app.json")}
        planned, payload = plan(self.vault, "enhance", self.answers, "minimal")
        self.assertFalse(planned["blocked"])
        self.assertEqual(planned["linkAudit"]["references"], 5)
        self.assertEqual(planned["linkAudit"]["preexistingUnresolved"], 1)
        self.assertEqual(planned["linkAudit"]["preexistingAmbiguous"], 0)
        self.assertEqual(planned["linkAudit"]["regressions"], [])
        apply(self.vault, planned, payload)
        for rel, original in preserved.items():
            self.assertEqual((self.vault / rel).read_bytes(), original, rel)

    def test_obsidian_new_basename_collision_blocks_existing_wikilink(self):
        write(self.vault, ".obsidian/app.json", "{}")
        write(self.vault, "Notes/AGENTS.md", "# Existing note\n")
        write(self.vault, "Notes/Index.md", "[[AGENTS]] [[Notes/AGENTS]] [local](AGENTS.md)\n")
        before = inventory(self.vault)
        planned, payload = plan(self.vault, "enhance", self.answers, "minimal")
        self.assertTrue(planned["blocked"])
        self.assertIn("agents", planned["linkAudit"]["newBasenameCollisions"])
        self.assertEqual(planned["linkAudit"]["regressions"],
                         [{"source": "Notes/Index.md", "kind": "wiki", "target": "AGENTS"}])
        self.assertTrue(any(item.get("rule") == "LINK_RESOLUTION_REGRESSION" for item in planned["items"]))
        with self.assertRaises(Blocked):
            apply(self.vault, planned, payload)
        self.assertEqual(inventory(self.vault), before)

    def test_obsidian_collision_without_affected_link_is_review_only(self):
        write(self.vault, ".obsidian/app.json", "{}")
        write(self.vault, "Notes/AGENTS.md", "# Existing note\n")
        write(self.vault, "Notes/Index.md", "[[Notes/AGENTS]] [local](AGENTS.md)\n"
              "```md\n[[AGENTS]]\n```\n")
        planned, _ = plan(self.vault, "enhance", self.answers, "minimal")
        self.assertFalse(planned["blocked"])
        self.assertIn("agents", planned["linkAudit"]["newBasenameCollisions"])
        self.assertEqual(planned["linkAudit"]["regressions"], [])

    def test_configuration_merge(self):
        self.assertEqual(merge_existing({"a": 2, "b": [], "nested": {"new": True}}, {"a": 9, "b": [1], "foreign": "keep", "nested": {"choice": 7}}), {"a": 9, "b": [1], "foreign": "keep", "nested": {"new": True, "choice": 7}})
        with self.assertRaises(Blocked):
            merge_existing({"a": True}, {"a": "yes"})
        self.assertEqual(effective_config({"x": 1}, {"x": 2}, {"x": 3}), {"x": 3})

    def test_new_defaults_do_not_replace_existing_personalization(self):
        self.answers["user"]["preferred_name"] = "Synthetic Owner"
        self.install()
        original = (self.vault / "AGENTS.md").read_bytes()
        other = answers_read(json_read(ROOT / "installer/defaults.json"))
        p, payload = plan(self.vault, "upgrade", other)
        item = next(i for i in p["items"] if i["path"] == "AGENTS.md")
        self.assertEqual((item["classification"], item["action"]), ("CONFIG_CONFLICT", "PROPOSE"))
        apply(self.vault, p, payload)
        self.assertEqual(original, (self.vault / "AGENTS.md").read_bytes())

    def test_historical_11_exact_managed_template_updates(self):
        write(self.vault, "00 - System/Installation/installer-state.json", encoded({"installer_version": "1.1.0"}))
        snapshots = json_read(ROOT / "installer/historical-templates.json")["templates"]
        original = next(x["text"] for x in snapshots if x["path"] == "CODEX.md")
        write(self.vault, "CODEX.md", original)
        p, _ = plan(self.vault, "upgrade", self.answers)
        self.assertEqual(next(i["action"] for i in p["items"] if i["path"] == "CODEX.md"), "UPDATE_SAFE")

    def test_project_activation_and_configuration_precedence(self):
        from packages import resolve_powerup
        self.install()
        self.pkg("install", self.package("powerup", defaults={"color": "blue", "retain": True}), "powerup")
        write(self.vault, "00 - System/Config/Power-Ups/example.powerup.json", '{"color":"green","foreign":"preserved"}')
        write(self.vault, "02 - Projects/Active/Example/power-ups.json", encoded({"schemaVersion": "1.0.0", "packages": {"example.powerup": {"enabled": True, "configuration": {"color": "red"}}}}))
        result = resolve_powerup(self.vault, "example.powerup", "Example")
        self.assertEqual(result["configuration"], {"color": "red", "retain": True, "foreign": "preserved"})
        self.pkg("disable", kind="powerup")
        self.assertFalse(resolve_powerup(self.vault, "example.powerup", "Example")["enabled"])

    def test_semantic_duplicate_alternate_adapter(self):
        write(self.vault, ".obsidian/app.json", "{}")
        write(self.vault, "providers/google.md", "AGENTS.md")
        write(self.vault, "alternate.json", encoded({"capabilities": [{"id": "kos.provider.gemini", "paths": ["providers/google.md"]}]}))
        p, _ = plan(self.vault, "enhance", self.answers, "minimal")
        self.assertTrue(p["blocked"])
        p, data = plan(self.vault, "enhance", self.answers, "minimal", {"GEMINI.md": "adopt"})
        self.assertFalse(p["blocked"])
        apply(self.vault, p, data)
        self.assertFalse((self.vault / "GEMINI.md").exists())

    def test_alternate_skills_registry_blocks_duplication(self):
        write(self.vault, ".obsidian/app.json", "{}")
        write(self.vault, "custom-skills/example/skill.json", '{"schema":"kos-skill/v1"}')
        p, _ = plan(self.vault, "enhance", self.answers)
        item = next(i for i in p["items"] if i["path"] == ".agents/registry/skills.json")
        self.assertEqual(item["classification"], "SEMANTIC_DUPLICATE")

    def test_links_preserved_not_traversed_and_write_blocked(self):
        self.install()
        outside = self.base / "outside"
        write(outside, "never-read.md", "outside")
        try:
            (self.vault / "linked").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink permission unavailable; junction test covers Windows")
        inv = inventory(self.vault)
        self.assertFalse(any(i["path"] == "linked/never-read.md" for i in inv))
        self.install("upgrade")
        self.assertTrue((self.vault / "linked").is_symlink())
        with self.assertRaises(Blocked):
            safe(self.vault, "linked/new.md", write=True)

    @unittest.skipUnless(os.name == "nt", "Windows junction fixture")
    def test_windows_junction(self):
        self.install()
        outside = self.base / "outside"
        outside.mkdir()
        link = self.vault / "junction"
        # Native PowerShell; never delete or move through a shell boundary.
        command = "New-Item -ItemType Junction -Path '" + str(link).replace("'", "''") + "' -Target '" + str(outside).replace("'", "''") + "' | Out-Null"
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True, capture_output=True)
        try:
            self.assertTrue(any(i["path"] == "junction" and i["kind"] == "link" for i in inventory(self.vault)))
            self.install("upgrade")
            with self.assertRaises(Blocked):
                safe(self.vault, "junction/write.md")
        finally:
            link.rmdir()  # removes junction entry, never its target

    def test_rollback_preserves_post_install_edits(self):
        self.install()
        write(self.vault, "CODEX.md", "old adapter")
        state = json_read(self.vault / STATE)
        state["components"]["CODEX.md"]["installedHash"] = digest(b"old adapter")
        write(self.vault, STATE, encoded(state))
        run = self.install("upgrade")
        write(self.vault, "CODEX.md", "post-install user edits")
        result = rollback(self.vault, run, approve=True)
        self.assertEqual(result["recovery"], "incomplete")
        self.assertEqual((self.vault / "CODEX.md").read_text(), "post-install user edits")

    def test_interrupted_transaction_and_partial_rollback(self):
        self.install()
        p = {"operation": "repair", "targetType": "managed-kos", "items": []}
        try:
            with Transaction(self.vault, p) as tx:
                tx.write("synthetic-created.md", b"created", None)
                raise OSError("simulated interruption")
        except OSError:
            pass
        self.assertEqual(json_read(self.vault / tx.rel / "journal.json")["status"], "failed")
        result = rollback(self.vault, tx.run, approve=True)
        self.assertEqual(result["recovery"], "complete")
        self.assertFalse((self.vault / "synthetic-created.md").exists())
        before = inventory(self.vault)
        rollback(self.vault, tx.run, approve=True)
        self.assertEqual(before, inventory(self.vault))

    def test_incomplete_rollback_report_is_honest(self):
        self.install()
        p = {"operation": "repair", "targetType": "managed-kos", "items": []}
        with Transaction(self.vault, p) as tx:
            tx.write("one.md", b"created", None)
            tx.write("two.md", b"created", None)
        write(self.vault, "one.md", "edited after installation")
        rollback(self.vault, tx.run, approve=True)
        journals = [json_read(p) for p in (self.vault / RUNS).glob("*/journal.json")]
        recovery = next(j for j in journals if j["operation"] == "rollback")
        self.assertEqual(recovery["status"], "incomplete")
        report = (self.vault / RUNS / recovery["runId"] / "report.md").read_text(encoding="utf-8")
        self.assertIn("Status: INCOMPLETE", report)

    def test_target_changes_between_plan_and_apply(self):
        self.install()
        (self.vault / "CODEX.md").unlink()
        p, payload = plan(self.vault, "repair", self.answers)
        write(self.vault, "CODEX.md", "user won race")
        with self.assertRaises(Blocked):
            apply(self.vault, p, payload)
        self.assertEqual((self.vault / "CODEX.md").read_text(), "user won race")

    def test_package_all_kinds_lifecycle_and_user_config(self):
        self.install()
        for kind in ("skill", "powerup", "adapter", "integration", "bundle"):
            source = self.package(kind)
            self.pkg("install", source, kind)
            before = inventory(self.vault)
            self.assertIsNone(self.pkg("install", source, kind))
            self.assertEqual(before, inventory(self.vault))
            self.pkg("disable", kind=kind)
            self.pkg("enable", kind=kind)
            self.pkg("update", self.package(kind, "1.1.0"), kind)
            self.pkg("rollback", kind=kind)
            write(self.vault, "00 - System/Config/Power-Ups/user.json", '{"custom":true}')
            self.pkg("uninstall", kind=kind)
            self.assertTrue((self.vault / "00 - System/Config/Power-Ups/user.json").exists())

    def test_package_identity_modified_code_permissions_and_dependencies(self):
        self.install()
        self.pkg("install", self.package())
        with self.assertRaises(Blocked):
            self.pkg("install", self.package(content="different bytes"))
        with self.assertRaises(Blocked):
            self.pkg("install", self.package("powerup", dependencies={"missing": "1.0.0"}))
        with self.assertRaises(Blocked):
            self.pkg("install", self.package("powerup", compatibility={"min": "2.0.0", "maxExclusive": "3.0.0"}))
        p, _ = plan_package(self.vault, "update", self.package(version="1.1.0", permissions=["filesystem:read"]))
        self.assertTrue(p["blocked"])
        write(self.vault, ".agents/skills/example.skill/1.0.0/SKILL.md", "user edits")
        with self.assertRaises(Blocked):
            self.pkg("uninstall")

    def test_dependency_cycle(self):
        from packages import dependencies
        a = {"id": "a", "dependencies": {"b": "1.0.0"}}
        b = {"enabled": True, "activeVersion": "1.0.0", "versions": {"1.0.0": {"manifest": {"dependencies": {"a": "1.0.0"}}}}}
        with self.assertRaisesRegex(Blocked, "CYCLE"):
            dependencies(a, {"b": b})

    def test_archive_traversal_duplicates_and_signature(self):
        source = self.package(signature={"keyId": "unknown", "algorithm": "rsa-sha256", "value": "invalid"})
        with self.assertRaises(Blocked):
            read_package(source)
        for name in ("../escape", "/root", "payload/CON", "payload/file:stream", "payload/../escape"):
            archive = self.base / "bad.kospkg"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr(name, "synthetic")
            with self.assertRaises(Blocked):
                read_package(archive)

    def test_package_cannot_shadow_its_manifest(self):
        source = self.package()
        manifest = json_read(source / "manifest.json")
        manifest["integrity"]["manifest.json"] = digest(b"shadow")
        write(source, "payload/manifest.json", "shadow")
        write(source, "manifest.json", encoded(manifest))
        with self.assertRaisesRegex(Blocked, "RESERVED_MANIFEST"):
            read_package(source)

    def test_valid_archive_round_trip(self):
        self.install()
        source = self.package()
        archive = self.base / "example.kospkg"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for file in source.rglob("*"):
                if file.is_file():
                    z.write(file, file.relative_to(source).as_posix())
        self.assertEqual(read_package(source), read_package(archive))
        self.pkg("install", archive)

    def test_arbitrary_user_json_is_preserved(self):
        write(self.vault, ".obsidian/app.json", "{}")
        data = encoded({"schema": {"name": "unrelated user object"}, "capabilities": "unrelated field"})
        write(self.vault, "notes/data.json", data)
        self.install("enhance", "minimal")
        self.assertEqual((self.vault / "notes/data.json").read_bytes(), data)

    def test_pro_unavailable_receipt_and_perpetual_boundary(self):
        self.install()
        self.pkg("install", self.package())
        before = inventory(self.vault)
        p = core_plan(self.vault)
        self.assertTrue(p["blocked"])
        with self.assertRaises(Blocked):
            core_plan(self.vault, receipt={"licenseKey": "must-not-be-stored"})
        self.assertEqual(before, inventory(self.vault))

    def test_new_install_uses_community_edition(self):
        self.install()
        self.assertEqual("community", json_read(self.vault / STATE)["edition"])

    def test_new_install_records_community_version(self):
        release = json_read(ROOT / "installer/release.json")
        self.install()
        state = json_read(self.vault / STATE)
        self.assertEqual(release["communityVersion"], state["communityVersion"])
        self.assertEqual(release["kosContractVersion"], state["kosContractVersion"])
        readme = (self.vault / "README.md").read_text(encoding="utf-8")
        self.assertIn("KOS Community `" + release["communityVersion"] + "`", readme)
        architecture = (self.vault / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn("community_version: " + release["communityVersion"], architecture)

    def test_upgrade_records_community_version_on_older_state(self):
        self.install()
        state = json_read(self.vault / STATE)
        del state["communityVersion"]
        write(self.vault, STATE, encoded(state))
        self.install("upgrade")
        release = json_read(ROOT / "installer/release.json")
        self.assertEqual(release["communityVersion"], json_read(self.vault / STATE)["communityVersion"])

    def test_community_downgrade_rejected(self):
        self.install()
        state = json_read(self.vault / STATE)
        state["communityVersion"] = "9.0.0"
        write(self.vault, STATE, encoded(state))
        with self.assertRaises(Blocked):
            self.install("upgrade")

    def test_downgrade_and_overwrite_rejected(self):
        self.install()
        state = json_read(self.vault / STATE)
        state["starterKitVersion"] = "9.0.0"
        write(self.vault, STATE, encoded(state))
        with self.assertRaises(Blocked):
            self.install("upgrade")
        with self.assertRaises(Blocked):
            answers_read({"installation": {"allow_overwrite": True}})

    def test_valid_and_invalid_signature(self):
        # Ephemeral synthetic test keys stay in memory; no private key fixture.
        def prime():
            while True:
                n = secrets.randbits(1024) | (1 << 1023) | 1
                if any(n % p == 0 for p in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31)):
                    continue
                d, s = n - 1, 0
                while d % 2 == 0:
                    d //= 2
                    s += 1
                for _ in range(24):
                    a = secrets.randbelow(n - 3) + 2
                    x = pow(a, d, n)
                    if x in (1, n - 1):
                        continue
                    for _ in range(s - 1):
                        x = pow(x, 2, n)
                        if x == n - 1:
                            break
                    else:
                        break
                else:
                    return n
        p, q = prime(), prime()
        n, e = p * q, 65537
        d = pow(e, -1, (p - 1) * (q - 1))
        source = self.package()
        manifest = json_read(source / "manifest.json")
        size = (n.bit_length() + 7) // 8
        tail = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(encoded(manifest)).digest()
        block = b"\0\1" + b"\xff" * (size - len(tail) - 3) + b"\0" + tail
        signature = pow(int.from_bytes(block, "big"), d, n).to_bytes(size, "big")
        manifest["signature"] = {"algorithm": "rsa-sha256", "keyId": "synthetic", "value": base64.b64encode(signature).decode()}
        write(source, "manifest.json", encoded(manifest))
        trust = self.base / "trust.json"
        write(self.base, trust.name, encoded({"keys": {"synthetic": {"modulus": base64.b64encode(n.to_bytes(size, "big")).decode(), "exponent": "AQAB"}}}))
        read_package(source, trust)
        manifest["name"] = "Tampered signed name"
        write(source, "manifest.json", encoded(manifest))
        with self.assertRaisesRegex(Blocked, "SIGNATURE_INVALID"):
            read_package(source, trust)

    def test_long_paths_and_optional_profiles(self):
        self.vault = self.base / ("a" * 80) / ("b" * 80) / ("c" * 80)
        try:
            self.vault.mkdir(parents=True)
        except OSError:
            self.skipTest("long paths disabled by host")
        self.install(profile="lean")
        self.assertFalse((self.vault / "01 - Business").exists())
        self.assertTrue((self.vault / "02 - Projects/Incubating/Sample Project/README.md").exists())

    def test_git_initialization_is_explicit_and_journaled(self):
        self.answers["installation"]["initialize_git"] = True
        run = self.install()
        self.assertTrue((self.vault / ".git").is_dir())
        journal = json_read(self.vault / RUNS / run / "journal.json")
        self.assertTrue(any(i.get("kind") == "git" and i["status"] == "written" for i in journal["entries"]))

    def test_interrupted_package_update_keeps_previous_activation(self):
        from unittest.mock import patch
        self.install()
        self.pkg("install", self.package())
        source = self.package(version="1.1.0")
        p, payload = plan_package(self.vault, "update", source)
        original = Transaction.write
        count = 0
        def failing(tx, *args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("synthetic interrupted update")
            return original(tx, *args, **kwargs)
        with patch.object(Transaction, "write", failing):
            with self.assertRaises(OSError):
                apply(self.vault, p, payload)
        registry = json_read(self.vault / ".agents/registry/skills.json")
        self.assertEqual(registry["packages"]["example.skill"]["activeVersion"], "1.0.0")

    def test_manifest_identity_detected_without_conventional_filename(self):
        write(self.vault, ".obsidian/app.json", "{}")
        write(self.vault, "Extensions/action.md", "Synthetic skill")
        write(self.vault, "Extensions/definition.json", encoded({"schema": "kos-skill/v1", "id": "custom.skill", "entrypoint": "action.md"}))
        p, _ = plan(self.vault, "enhance", self.answers)
        item = next(i for i in p["items"] if i["path"] == ".agents/registry/skills.json")
        self.assertEqual(item["classification"], "SEMANTIC_DUPLICATE")

    def test_duplicate_json_keys_and_managed_package_paths(self):
        from safety import json_loads
        with self.assertRaises(Blocked):
            json_loads('{"id":"one","ID":"two"}')
        self.install()
        self.pkg("install", self.package())
        registry = json_read(self.vault / ".agents/registry/skills.json")
        registry["packages"]["example.skill"]["versions"]["1.0.0"]["path"] = "notes"
        write(self.vault, ".agents/registry/skills.json", encoded(registry))
        with self.assertRaisesRegex(Blocked, "RESERVED_PATH"):
            self.pkg("uninstall")

    def test_readonly_validation_detects_stale_registry(self):
        self.install()
        (self.vault / "GEMINI.md").unlink()
        before = inventory(self.vault)
        result = validate_installation(self.vault)
        self.assertTrue(any(i["rule"] == "CAPABILITY_STALE" for i in result))
        self.assertEqual(before, inventory(self.vault))


if __name__ == "__main__":
    unittest.main()
