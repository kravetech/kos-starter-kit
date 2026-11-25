import json
import base64
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import project_lifecycle as context


class ProjectLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "My vault"
        (self.vault / context.ACTIVE).mkdir(parents=True)
        self.manifest = self.vault / "00 - System/Config/ai-context-manifest.yaml"
        self.manifest.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "templates/system/ai-context-manifest.yaml", self.manifest)
        (self.vault / "AGENTS.md").write_text("# Owner router\n", encoding="utf-8")
        self.project = context.project_path(self.vault, "Sample Á")

    def test_receipt_preserves_legacy_bytes_and_pins_both_notes(self):
        self.project.mkdir()
        owner_note = b"\xef\xbb\xbf# Decisions\r\nKeep original formatting.\r\n"
        path = self.project / "memory.md"
        path.write_bytes(owner_note)
        initialized = context.initialize(self.project)
        self.assertEqual(initialized["created"], ["handoff.md"])
        self.assertEqual(context.initialize(self.project)["created"], [])
        with self.assertRaises(ValueError):
            context.read_context(self.project)
        token = context.review(self.project)["review_token"]
        with self.assertRaisesRegex(ValueError, "classify-unmarked"):
            context.approve(self.project, token)
        self.assertFalse((self.project / context.RECEIPT).exists())
        result = context.approve(self.project, token, True)
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["files"][0]["effective_access"], "internal")
        self.assertEqual(path.read_bytes(), owner_note)
        self.assertIn("Keep original formatting.", context.read_context(self.project)["files"][0]["content"])
        path.write_bytes(owner_note + b"New decision.\r\n")
        self.assertEqual(context.check(self.project)["status"], "stale")
        with self.assertRaisesRegex(ValueError, "changed"):
            context.approve(self.project, token, True)
        with self.assertRaises(ValueError):
            context.read_context(self.project)

    @unittest.skipUnless(shutil.which("git"), "requires Git")
    def test_git_privacy_checks_actual_rules_temp_file_and_index(self):
        subprocess.run(["git", "init", "-q", str(self.vault)], check=True)
        ignore = self.vault / ".gitignore"
        original = b"# Owner choices\n*.scratch\n!.kos-context-*\n"
        ignore.write_bytes(original)
        token = context.initialize(self.project)["review_token"]
        self.assertIn("snapshot_warning", context.review(self.project))
        with self.assertRaisesRegex(ValueError, "untracked"):
            context.approve(self.project, token)
        self.assertEqual(ignore.read_bytes(), original)
        self.assertEqual(list(self.project.glob(".kos-context-*")), [])

        # Protecting only the final path still leaves the temporary copy visible.
        ignore.write_bytes(original + context.RECEIPT.encode() + b"\n")
        with self.assertRaisesRegex(ValueError, "Git can track"):
            context.approve(self.project, token)
        self.assertEqual(list(self.project.glob(".kos-context-*")), [])
        ignore.write_bytes(original + b".kos-context-*\n")
        self.assertEqual(context.approve(self.project, token)["status"], "active")
        self.assertNotIn("snapshot_warning", context.check(self.project))

        receipt = self.project / context.RECEIPT
        before = receipt.read_bytes()
        subprocess.run(["git", "-C", str(self.project), "add", "-f", "--", context.RECEIPT], check=True)
        self.assertIn("snapshot_warning", context.check(self.project))
        with self.assertRaisesRegex(ValueError, "untracked"):
            context.approve(self.project, token)
        with (self.project / "handoff.md").open("ab") as stream:
            stream.write(b"Edited locally.\n")
        replacement = context.review(self.project)["review_token"]
        with self.assertRaisesRegex(ValueError, "untracked"):
            context.approve(self.project, replacement)
        self.assertEqual(receipt.read_bytes(), before)

    def test_missing_git_only_blocks_git_vault_approval(self):
        token = context.initialize(self.project)["review_token"]
        with patch.object(context.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(context.approve(self.project, token)["status"], "active")
            (self.vault / ".git").write_text("gitdir: local-worktree\n", encoding="utf-8")
            self.assertIn("snapshot_warning", context.check(self.project))
            with self.assertRaisesRegex(ValueError, "Make Git available"):
                context.approve(self.project, token)

    @unittest.skipUnless(sys.platform == "win32", "Windows physical path resolution")
    def test_project_folder_case_alias_preserves_review_identity(self):
        token = context.initialize(self.project)["review_token"]
        context.approve(self.project, token)
        typed = self.project.name.swapcase()
        if not (self.project.parent / typed).exists():
            self.skipTest("volume distinguishes case")
        project = context.project_path(self.vault, typed)
        self.assertEqual(project.name, self.project.name)
        self.assertEqual(context.check(project)["status"], "active")
        # Older releases used the caller's spelling when writing an approval.
        path = project / context.RECEIPT
        old = json.loads(path.read_bytes())
        old["project"] = typed
        hashes = {name: entry["sha256"] for name, entry in old["approved_files"].items()}
        old["review_token"] = context._pair_token(typed, hashes)
        path.write_text(json.dumps(old), encoding="utf-8")
        previous = path.read_bytes()
        self.assertEqual(context.check(self.project)["status"], "active")
        self.assertEqual(path.read_bytes(), previous)
        with (project / "handoff.md").open("ab") as stream:
            stream.write(b"Edited locally.\n")
        self.assertEqual(context.check(project)["status"], "stale")
        next_token = context.review(project)["review_token"]
        self.assertEqual(context.approve(project, next_token)["status"], "active")
        self.assertEqual(context.check(self.project)["status"], "active")
        self.assertEqual(json.loads(path.read_bytes())["project"], self.project.name)

    def test_restricted_and_invalid_metadata_never_disclose_or_reclassify(self):
        context.initialize(self.project)
        for header in ("ai_access: restricted", "ai_access: public\nai_access: internal",
                       "ai_access: unclassified", "ai_access: internal\nstatus: inactive",
                       "ai_access: internal\nai_context: never", "ai_access: internal\nenabled: false"):
            with self.subTest(header=header):
                (self.project / "memory.md").write_text(f"---\n{header}\n---\nPRIVATE MARKER\n",
                                                     encoding="utf-8")
                result = context.review(self.project)
                self.assertEqual(result["status"], "blocked")
                self.assertNotIn("PRIVATE MARKER", json.dumps(result))
                self.assertIsNone(result["review_token"])
                with self.assertRaises(ValueError):
                    context.approve(self.project, "bad", True)

    def test_corrupt_existing_receipt_is_preserved(self):
        self.project.mkdir()
        path = self.project / context.RECEIPT
        path.write_text("custom data", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Inspect and recover"):
            context.initialize(self.project)
        self.assertEqual(path.read_text(encoding="utf-8"), "custom data")
        self.assertEqual(list(self.project.iterdir()), [path])

    def test_minimal_vault_creates_project_foundations_only_on_init(self):
        (self.vault / context.ACTIVE).rmdir()
        (self.vault / "02 - Projects").rmdir()
        project = context.project_path(self.vault, "New project")
        with self.assertRaisesRegex(ValueError, "Initialize"):
            context.review(project)
        self.assertFalse((self.vault / "02 - Projects").exists())
        self.assertEqual(context.initialize(project)["status"], "draft")
        self.assertEqual(set(path.name for path in project.iterdir()), {"memory.md", "handoff.md"})

    def test_review_supports_obsidian_block_lists_and_preserves_bytes(self):
        context.initialize(self.project)
        data = b"\r\n".join((b"---", b"tags:", b"  - delivery", b"  - planning", b"aliases:",
                              b"- Our notes", b"ai_access: internal", b"---", b"Meeting decision.", b""))
        path = self.project / "memory.md"
        path.write_bytes(data)
        token = context.review(self.project)["review_token"]
        self.assertEqual(context.approve(self.project, token)["status"], "active")
        self.assertEqual(path.read_bytes(), data)
        policy_list = b"\n".join((b"---", b"ai_access:", b"  - internal", b"---", b""))
        self.assertEqual(context.frontmatter_access(policy_list), "invalid")

    def test_busy_project_and_invalid_project_names(self):
        context.initialize(self.project)
        (self.project / context.WRITE_LOCK).mkdir()
        with self.assertRaisesRegex(ValueError, "writer"):
            context.review(self.project)
        with self.assertRaisesRegex(ValueError, "write"):
            context.initialize(self.project)
        for name in ("..", "a/b", "a\\b", "NUL", "trailing.", ".hidden"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                context.project_path(self.vault, name)

    def test_review_compares_verified_original_before_stale_approval(self):
        initial = context.initialize(self.project)
        old_token = initial["review_token"]
        context.approve(self.project, old_token)
        path = self.project / "handoff.md"
        original = path.read_bytes()
        approved = json.loads((self.project / context.RECEIPT).read_bytes())
        self.assertEqual(base64.b64decode(approved["approved_files"]["handoff.md"]["content_b64"]), original)
        path.write_bytes(original + b"New action item.")
        checked = context.check(self.project)
        self.assertEqual(checked["status"], "stale")
        self.assertIsNone(checked["review_token"])
        self.assertEqual([c["path"] for c in checked["changed_files"]], ["handoff.md"])
        change = checked["changed_files"][0]
        self.assertNotEqual(change["previous_sha256"], change["current_sha256"])
        self.assertNotIn("original_content", change)
        self.assertNotIn("New action item", json.dumps(checked))
        with self.assertRaisesRegex(ValueError, "handoff.md"):
            context.read_context(self.project)
        receipt = (self.project / context.RECEIPT).read_bytes()
        review = context.review(self.project)
        self.assertEqual((self.project / context.RECEIPT).read_bytes(), receipt)
        self.assertEqual(review["changed_files"][0]["original_content"], original.decode())
        self.assertIn("+New action item.", review["changed_files"][0]["diff"])
        with self.assertRaisesRegex(ValueError, "changed"):
            context.approve(self.project, old_token)
        # A second edit invalidates the stale-review token for the first edit.
        path.write_bytes(original + b"Changed again.")
        with self.assertRaisesRegex(ValueError, "changed"):
            context.approve(self.project, review["review_token"])
        current = context.review(self.project)
        self.assertEqual(context.approve(self.project, current["review_token"])["status"], "active")
        self.assertEqual(path.read_bytes(), original + b"Changed again.")

    def test_snapshot_privacy_after_classification_change_and_project_copy(self):
        context.initialize(self.project)
        handoff = self.project / "handoff.md"
        original = b"---\nai_access: internal\n---\nPrivate before edit.\n"
        handoff.write_bytes(original)
        context.approve(self.project, context.review(self.project)["review_token"])
        other = context.project_path(self.vault, "Other project")
        shutil.copytree(self.project, other)
        with self.assertRaisesRegex(ValueError, "different project"):
            context.review(other)
        for data in (b"---\nai_access: restricted\n---\nHidden text.",
                     b"---\nai_access: internal\nstatus: inactive\n---\nHidden text.", b"Unmarked."):
            handoff.write_bytes(data)
            result = context.review(self.project)
            self.assertIsNone(result["review_token"])
            self.assertNotIn("Private before edit.", json.dumps(result))
            self.assertNotIn("Hidden text.", json.dumps(result))
            self.assertNotIn("Unmarked.", json.dumps(result))
        handoff.unlink()
        self.assertEqual(context.review(self.project)["status"], "blocked")
        self.assertNotIn("Private before edit.", json.dumps(context.review(self.project)))

    def test_damaged_snapshot_and_v1_migration(self):
        original_token = context.initialize(self.project)["review_token"]
        path = self.project / context.RECEIPT
        path.write_text(json.dumps({"schema": "kos-context-approval/v1", "review_token": original_token,
                                    "classify_unmarked": False}), encoding="utf-8")
        self.assertEqual(context.check(self.project)["status"], "active")
        note = self.project / "handoff.md"
        original = note.read_bytes()
        note.write_bytes(original + b"Edited before upgrade.")
        result = context.review(self.project)
        self.assertIsNone(result["changed_files"])
        self.assertIsNone(result["review_token"])
        self.assertIn("backup", result["guidance"])
        note.write_bytes(original)
        context.approve(self.project, original_token)
        receipt = json.loads(path.read_bytes())
        self.assertEqual(receipt["schema"], "kos-context-approval/v2")
        receipt["approved_files"]["handoff.md"]["content_b64"] = base64.b64encode(b"Corrupt.").decode()
        path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Inspect and recover"):
            context.review(self.project)


if __name__ == "__main__":
    unittest.main()
