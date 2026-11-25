"""Exercise bounded selection, policy and physical citations on disposable Markdown."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import project_context as command
import project_sources as sources


class SourceTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / "test-output"
        base.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="source-selection-", dir=base)
        self.addCleanup(temp.cleanup)
        self.vault = Path(temp.name)
        self.project = self.vault / "02 - Projects/Active/Field Notes"
        self.project.mkdir(parents=True)
        self.manifest = self.vault / sources.MANIFEST
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_bytes((ROOT / "templates/system/ai-context-manifest.yaml").read_bytes())

    def write(self, rel, body, header=b"ai_access: internal"):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = body if header is None else b"---\n" + header + b"\n---\n" + body
        path.write_bytes(data)
        return data

    def test_origin_revision_and_scope_on_each_call(self):
        first = self.write("Notes/A.md", b"First line\nMiXeD needle\n")
        self.write("B.md", b"mixed needle\n")
        paths = ["Notes/A.md", "B.md"]
        actual = sources.search_sources(self.project, paths, "mixed needle")
        self.assertEqual([item["line"] for item in actual["matches"]], [5, 4])
        self.assertEqual(actual["sources"][0]["sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(actual["sources"][0]["path"], "Notes/A.md")
        self.assertFalse(actual["truncated"])
        self.assertEqual(sources.inspect_sources(self.project, [])["sources"], [])
        self.write("Notes/A.md", b"New facts\n")
        changed = sources.search_sources(self.project, paths[:1], "mixed needle")
        self.assertEqual(changed["matches"], [])
        self.assertNotEqual(changed["sources"][0]["sha256"], actual["sources"][0]["sha256"])

    def invoke(self, *args):
        return command.run(command.arguments(["--vault", str(self.vault), "--project", self.project.name, *args]))

    def test_obsidian_descriptive_values_preserve_policy_and_line_numbers(self):
        header = b"\n".join((b"""title: "Owner's notes" """, b"date reviewed: 2026-11-24", b"tags:",
                             b'  - "Topic: weekly"', b"summary: >", b"  First line of summary.",
                             b"  Second line.", b"aliases: [Weekly, Meeting]", b"ai_access: internal"))
        self.write("note.md", b"Selected meeting decision.", header)
        self.write("memory.md", b"Selected meeting decision.", header)
        self.write("handoff.md", b"Pending.")
        (self.vault / "AGENTS.md").write_text("project_context.py", encoding="utf-8")
        review = self.invoke("review")
        self.assertEqual(review["status"], "draft")
        self.assertTrue(all(item["ai_access"] == "internal" for item in review["files"]))
        self.invoke("approve", "--review-token", review["review_token"])
        report = self.invoke("search", "--query", "decision", "--source", "note.md", "--source", "memory.md")
        self.assertEqual([(item["path"], item["line"]) for item in report["matches"]],
                         [("note.md", 12), ("memory.md", 12)])
        invalid_headers = [header + b"\nai_access: public", header.replace(b"internal", b"restricted"),
                           header.replace(b"internal", b"[internal]"), header + b"\nstatus: inactive"]
        for invalid in invalid_headers:
            with self.subTest(policy=invalid):
                self.write("note.md", b"WITHHELD_FIXTURE_CONTENT", invalid)
                self.write("memory.md", b"WITHHELD_FIXTURE_CONTENT", invalid)
                self.assertEqual(self.invoke("review")["status"], "blocked")
                result = sources.search_sources(self.project, ["note.md"], "WITHHELD")
                self.assertFalse(result["sources"])
                self.assertNotIn("WITHHELD_FIXTURE_CONTENT", json.dumps(result))

    def test_context_sources_and_search_share_exact_approved_revisions(self):
        (self.vault / "AGENTS.md").write_text("project_context.py", encoding="utf-8")
        legacy = b"\xef\xbb\xbfLegacy decision\r\nNext item\r\n"
        draft = b"ai_access: internal\nreview_status: draft"
        self.write("memory.md", legacy, None)
        self.write("handoff.md", b"Reviewed decision\n", draft)
        self.write("other-legacy.md", legacy, None)
        self.write("other-draft.md", b"Reviewed decision\n", draft)
        review = self.invoke("review")
        self.invoke("approve", "--review-token", review["review_token"], "--classify-unmarked")
        files = self.invoke("context")["files"]
        selected = ("--source", "memory.md", "--source", "handoff.md", "--source", "other-legacy.md",
                    "--source", "other-draft.md")
        report = self.invoke("sources", *selected)
        self.assertEqual([(s["path"], s["sha256"], s["access"]) for s in report["sources"]],
                         [(s["path"], s["sha256"], s["effective_access"]) for s in files])
        self.assertEqual([s["path"] for s in report["skipped"]], ["other-legacy.md", "other-draft.md"])
        result = self.invoke("search", "--query", "decision", *selected)
        self.assertEqual(report["sources"], result["sources"])
        self.assertEqual([(m["path"], m["line"]) for m in result["matches"]],
                         [("memory.md", 1), ("handoff.md", 5)])
        self.write("handoff.md", b"Changed decision", draft)
        for args in (("sources", *selected), ("search", "--query", "decision", *selected)):
            with self.assertRaisesRegex(ValueError, "Edited: handoff.md"):
                self.invoke(*args)

    def test_edit_during_selected_read_never_exposes_unapproved_revision(self):
        (self.vault / "AGENTS.md").write_text("project_context.py", encoding="utf-8")
        self.write("memory.md", b"Decision at approval.", None)
        self.write("handoff.md", b"Next meeting.")
        review = self.invoke("review")
        self.invoke("approve", "--review-token", review["review_token"], "--classify-unmarked")
        read_source = sources._read_source

        def edit_then_read(*args):
            self.write("memory.md", b"Changed decision.", None)
            return read_source(*args)

        with patch.object(sources, "_read_source", side_effect=edit_then_read):
            report = sources.search_sources(self.project, ["memory.md"], "decision")
        self.assertEqual(report["skipped"], [{"path": "memory.md", "reason": "source_changed"}])
        self.assertEqual(report["matches"], [])

    @unittest.skipUnless(os.name == "nt", "Windows path separators")
    def test_windows_native_separator_respects_folder_policy(self):
        native = os.path.join("Notes", "meeting.md")
        self.write("Notes/meeting.md", b"A decision.")
        self.assertEqual(sources.search_sources(self.project, [native], "decision")["matches"][0]["path"],
                         "Notes/meeting.md")
        self.manifest.write_text('restricted:\n  - "Notes/"\nnever_auto_load: []\n', encoding="utf-8")
        self.assertEqual(sources.inspect_sources(self.project, [native])["skipped"][0]["reason"],
                         "excluded_by_policy")

    def test_ineligible_headers_are_never_exposed(self):
        headers = [None, b"ai_access: restricted", b"ai_access: public\nai_access: public",
                   b"ai_access: public\nstatus: inactive", b"ai_access: internal\nenabled: false",
                   b"ai_access: public\nreview_status: draft", b"ai_access: internal\nDisabled: true",
                   b"ai_access: internal\n" + b"a" * 9000]
        names = [f"fixture-{i}.md" for i in range(len(headers))]
        for name, header in zip(names, headers):
            self.write(name, b"WITHHELD_FIXTURE_CONTENT\n", header=header)
        result = sources.search_sources(self.project, names, "WITHHELD")
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["matches"], [])
        self.assertEqual(len(result["skipped"]), len(names))
        self.assertNotIn("WITHHELD_FIXTURE_CONTENT", json.dumps(result))

    def test_installed_policy_and_user_folder_rules(self):
        lines = ["version: 1.0.0", "restricted:", '  - "02 - Projects/Active/*/Budget/**"',
                 "  - 'private notes/' # project-specific", "never_auto_load:",
                 '  - "**/history/**"']
        self.manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path = self.vault / sources.INSTALL_STATE
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"privacy": {"restricted_folders": ["Rights"]}}), encoding="utf-8")
        denied = ["Budget/Detail.md", "private notes/A.md", "history/x.md",
                  "sub/deep/history/y.md", "Rights/z.md", ".config/excluded.md"]
        for name in denied + ["Historical.md"]:
            self.write(name, b"needle\n")
        result = sources.search_sources(self.project, denied + ["Historical.md"], "needle")
        self.assertEqual([m["path"] for m in result["matches"]], ["Historical.md"])
        self.assertEqual({s["reason"] for s in result["skipped"]}, {"excluded_by_policy"})

    def test_incomplete_policy_blocks_even_a_previously_eligible_note(self):
        self.write("allowed.md", b"visible")
        self.manifest.write_text("restricted: []\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "never_auto_load"):
            sources.search_sources(self.project, ["allowed.md"], "visible")
        self.manifest.write_text("restricted: [PENDING]\nnever_auto_load: []\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            sources.search_sources(self.project, ["allowed.md"], "visible")

    def test_byte_and_selection_limits(self):
        header = b"---\nai_access: internal\n---\n"
        contents = b"a" * (sources.MAX_SOURCE_BYTES - len(header))
        names = [f"long-{i}.md" for i in range(9)]
        for name in names:
            self.write(name, contents)
        self.write("too-big.md", contents + b"x")
        report = sources.inspect_sources(self.project, names + ["too-big.md"])
        self.assertEqual(sum(item["bytes"] for item in report["sources"]), sources.MAX_TOTAL_BYTES)
        self.assertEqual([s["reason"] for s in report["skipped"]], ["total_byte_limit", "source_byte_limit"])
        self.assertTrue(report["truncated"])
        short = sources.inspect_sources(self.project, names, max_files=1)
        self.assertEqual(short["processed_count"], 1)
        self.assertTrue(short["truncated"])

    def test_clipped_matches_cite_unicode_crlf_lines_and_search_literal_text(self):
        data = b"\xef\xbb\xbf---\r\nai_access: internal\r\n---\r\n"
        self.write("note.md", data + ("é" * 500 + "[x]\r\n[x]\r\n").encode(), header=None)
        result = sources.search_sources(self.project, ["note.md"], "[x]", max_results=1)
        self.assertEqual(result["matches"][0]["line"], 4)
        self.assertIn("[x]", result["matches"][0]["snippet"])
        self.assertLessEqual(len(result["matches"][0]["snippet"]), sources.MAX_SNIPPET)
        self.assertTrue(result["truncated"])
        self.assertEqual(sources.search_sources(self.project, ["note.md"], "ai_access")["matches"], [])

    def test_hardlinks_never_qualify(self):
        self.write("original.md", b"fixture only\n")
        try:
            os.link(self.project / "original.md", self.project / "alias.md")
        except PermissionError:
            self.skipTest("The execution environment prevents creating test hardlinks.")
        report = sources.inspect_sources(self.project, ["original.md", "alias.md"])
        self.assertEqual(report["sources"], [])
        self.assertEqual(len(report["skipped"]), 2)

    def test_non_files_never_qualify(self):
        (self.project / "folder.md").mkdir()
        paths = ["folder.md", "../external.md", "missing.md", "foo.json"]
        result = sources.inspect_sources(self.project, paths)
        self.assertEqual(result["sources"], [])
        self.assertEqual(len(result["skipped"]), len(paths))


if __name__ == "__main__":
    unittest.main()
