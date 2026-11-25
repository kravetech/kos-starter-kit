"""Exercise the installed Community commands as a vault owner on disposable data."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = Path("00 - System/Tools/ProjectContext/project_context.py")
ACTIVE = Path("02 - Projects/Active")


def snapshot(folder):
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in folder.rglob("*") if path.is_file()
    }


def note(body, access="internal"):
    return f"---\nai_access: {access}\n---\n{body}\n".encode("utf-8")


class ProjectContextJourneys(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "test-output"
        scratch.mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="c1-", dir=scratch)
        self.addCleanup(fixture.cleanup)
        self.vault = Path(fixture.name) / "My Vault"
        installed = subprocess.run(
            [sys.executable, str(ROOT / "installer/install.py"), "--target", str(self.vault),
             "--answers", str(ROOT / "installer/answers.example.json"), "--operation", "new"],
            capture_output=True, timeout=90,
        )
        self.assertEqual(installed.returncode, 0, (installed.stdout + installed.stderr)[-2000:])
        self.script = self.vault / ENTRYPOINT
        self.assertTrue(self.script.is_file(), "C1 command missing from installed vault")
        self.project = self.vault / ACTIVE / "Coastal Study"
        self.project.mkdir()

    def invoke(self, *args, accepted=(0,)):
        result = subprocess.run(
            [sys.executable, str(self.script), "--vault", str(self.vault), "--project",
             self.project.name, *args],
            cwd=self.vault.parent, capture_output=True, timeout=30,
        )
        self.assertIn(result.returncode, accepted, (args, result.stdout[-1500:], result.stderr[-1500:]))
        return json.loads(result.stdout.decode("utf-8-sig"))

    def activate(self):
        self.invoke("init")
        review = self.invoke("review")
        self.invoke("approve", "--review-token", review["review_token"])
        self.assertEqual(self.invoke("check")["status"], "active")

    def test_routing_recognizes_active_rules_outside_examples(self):
        self.activate()
        self.assertEqual(self.invoke("check")["routing"]["status"], "ready")
        names = ("AGENTS.md", "CONTEXT-POLICY.md")
        for name, fence in zip(names, ("````", "~~~")):
            path = self.vault / name
            rules = path.read_text(encoding="utf-8")
            # An example can contain a shorter fence without closing the outer one.
            path.write_text(f"{fence}markdown\n```\n{rules}\n{fence}\n", encoding="utf-8")
        routing = self.invoke("check")["routing"]
        self.assertEqual(routing["status"], "adoption_pending")
        self.assertEqual([item["path"] for item in routing["pending"]], list(names))

    def test_customized_legacy_project_is_preserved_and_stale_review_is_rejected(self):
        memory = self.project / "memory.md"
        original = b"\xef\xbb\xbf# Owner's notes\r\n\r\nCoastal legacy record\r\n"
        memory.write_bytes(original)
        preference = self.vault / ".obsidian" / "workspace.json"
        preference.parent.mkdir(exist_ok=True)
        preference.write_bytes(b'{"view":"custom"}')
        before = snapshot(self.vault)
        self.invoke("init")
        initialized = snapshot(self.vault)
        self.assertTrue(all(initialized.get(path) == value for path, value in before.items()))
        self.invoke("init")
        self.assertEqual(snapshot(self.vault), initialized)
        self.assertNotEqual(self.invoke("check", accepted=(2,))["status"], "active")
        self.assertNotIn("Coastal legacy record", json.dumps(self.invoke("context", accepted=(2,))))
        self.invoke("search", "--query", "Coastal", "--source", "memory.md", accepted=(2,))
        token = self.invoke("review")["review_token"]
        self.invoke("approve", "--review-token", token, accepted=(2,))
        self.assertEqual(snapshot(self.vault), initialized)
        memory.write_bytes(original + b"Another owner edit\r\n")
        changed = snapshot(self.vault)
        self.invoke("approve", "--review-token", token, "--classify-unmarked", accepted=(2,))
        self.assertEqual(snapshot(self.vault), changed)
        token = self.invoke("review")["review_token"]
        self.invoke("approve", "--review-token", token, "--classify-unmarked")
        self.assertEqual(self.invoke("check")["status"], "active")
        self.assertEqual(memory.read_bytes(), original + b"Another owner edit\r\n")
        approved = snapshot(self.vault)
        self.assertIn("Coastal legacy record", json.dumps(self.invoke("context")))
        self.invoke("review")
        self.assertEqual(snapshot(self.vault), approved)
        memory.write_bytes(original + b"An edit after approval\r\n")
        self.assertNotEqual(self.invoke("check", accepted=(2,))["status"], "active")
        self.assertNotIn("An edit after approval", json.dumps(self.invoke("context", accepted=(2,))))

    def test_source_selection_gives_traceable_results_and_never_expands_on_omission(self):
        self.activate()
        selected = self.project / "Field notes.md"
        selected.write_bytes(note("Decision Ready"))
        (self.project / "Personal.md").write_bytes(note("Decision PRIVATE_CONTENT", "restricted"))
        (self.project / "Unknown.md").write_bytes(b"Decision UNCLASSIFIED_CONTENT")
        (self.project / "history").mkdir()
        (self.project / "history" / "Draft.md").write_bytes(note("Decision HISTORICAL_CONTENT"))
        neighbor = self.project.parent / "Other survey"
        neighbor.mkdir()
        (neighbor / selected.name).write_bytes(note("Decision UNRELATED_CONTENT"))
        before = snapshot(self.vault)
        chosen = ["--source", selected.name, "--source", "Personal.md", "--source", "Unknown.md",
                  "--source", "history/Draft.md"]
        inventory = self.invoke("sources", *chosen)
        self.assertEqual(len(inventory["sources"]), 1)
        self.assertEqual(inventory["sources"][0]["sha256"], hashlib.sha256(selected.read_bytes()).hexdigest())
        hit = self.invoke("search", "--query", "decision", *chosen)
        self.assertEqual(len(hit["matches"]), 1)
        self.assertEqual(hit["matches"][0]["line"], 4)
        self.assertIn("Decision Ready", hit["matches"][0]["snippet"])
        for marker in ["PRIVATE_CONTENT", "UNCLASSIFIED_CONTENT", "HISTORICAL_CONTENT", "UNRELATED_CONTENT"]:
            self.assertNotIn(marker, json.dumps(hit))
        self.assertEqual(self.invoke("search", "--query", "decision")["matches"], [])
        self.assertEqual(before, snapshot(self.vault))
        selected.write_bytes(note("Decision revised"))
        revised = self.invoke("sources", "--source", selected.name)
        self.assertNotEqual(inventory["sources"][0]["sha256"], revised["sources"][0]["sha256"])
        selected.write_bytes(note("Decision now restricted", "restricted"))
        self.assertEqual(self.invoke("search", "--query", "decision", "--source", selected.name)["matches"], [])

    def test_many_notes_stay_bounded_and_parallel_readers_leave_same_hashes(self):
        self.activate()
        candidates = []
        for index in range(180):
            path = self.project / f"Observation {index:03}.md"
            path.write_bytes(note("\n".join(f"Sample line {number}" for number in range(12))))
            candidates.append(path.name)
        args = [item for name in candidates[:24] for item in ("--source", name)]
        before = snapshot(self.vault)
        hit = self.invoke("search", "--query", "Sample", "--max-results", "7", *args)
        self.assertTrue(hit["truncated"])
        self.assertEqual(len(hit["matches"]), 7)
        limited = self.invoke("search", "--query", "absent", "--max-files", "6", *args)
        self.assertTrue(limited["truncated"])
        self.assertLessEqual(limited["processed_count"], 6)
        self.assertEqual(limited["matches"], [])
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda _: self.invoke("search", "--query", "Sample", "--max-results", "7", *args),
                range(16),
            ))
        self.assertTrue(all(item["matches"] == hit["matches"] for item in results))
        self.assertEqual(before, snapshot(self.vault))

    def test_first_run_converges_for_two_users_opening_the_same_project(self):
        self.project.rmdir()  # The two users both start before this project has been created.
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.invoke("init", accepted=(0, 2)), range(8)))
        self.invoke("init")
        after = snapshot(self.vault)
        self.invoke("init")
        self.assertEqual(after, snapshot(self.vault))
        self.assertTrue((self.project / "memory.md").is_file())
        self.assertTrue((self.project / "handoff.md").is_file())
        token = self.invoke("review")["review_token"]
        self.invoke("approve", "--review-token", token)
        self.assertEqual(self.invoke("check")["status"], "active")

    def test_owner_can_tighten_the_selected_projects_policy_between_reads(self):
        self.activate()
        selected = self.project / "Weekly note.md"
        selected.write_bytes(note("Public within this exercise"))
        options = ("search", "--source", selected.name, "--query", "exercise")
        self.assertEqual(len(self.invoke(*options)["matches"]), 1)
        manifest = self.vault / "00 - System/Config/ai-context-manifest.yaml"
        old = manifest.read_bytes()
        self.assertEqual(old.count(b"restricted:"), 1)
        marker = f"\n  - '{ACTIVE.as_posix()}/{self.project.name}/{selected.name}'".encode()
        manifest.write_bytes(old.replace(b"restricted:", b"restricted:" + marker))
        before = snapshot(self.vault)
        withdrawn = self.invoke(*options)
        self.assertEqual(withdrawn["matches"], [])
        self.assertEqual(withdrawn["skipped"][0]["reason"], "excluded_by_policy")
        self.assertEqual(before, snapshot(self.vault))

    def test_reviewer_recovers_the_approved_handoff_after_an_edit(self):
        memory = self.project / "memory.md"
        handoff = self.project / "handoff.md"
        memory.write_bytes(note("Unchanged project decision"))
        old = note("Friday: send the first draft")
        new = note("Monday: send the revised draft")
        handoff.write_bytes(old)
        self.activate()
        handoff.write_bytes(new)
        before = snapshot(self.vault)
        check = self.invoke("check", accepted=(2,))
        self.assertEqual(check["status"], "stale")
        self.assertEqual([item["path"] for item in check["changed_files"]], ["handoff.md"])
        self.assertIsNone(check["review_token"])
        self.assertNotIn("Friday: send", json.dumps(check))
        self.assertNotIn("Monday: send", json.dumps(check))
        self.assertEqual(check["changed_files"][0]["previous_sha256"], hashlib.sha256(old).hexdigest())
        self.assertEqual(check["changed_files"][0]["current_sha256"], hashlib.sha256(new).hexdigest())
        review = self.invoke("review")
        change, = review["changed_files"]
        self.assertEqual(change["path"], "handoff.md")
        self.assertEqual(change["original_content"], old.decode())
        self.assertIn("-Friday: send the first draft", change["diff"])
        self.assertIn("+Monday: send the revised draft", change["diff"])
        self.assertNotIn("Unchanged project decision", json.dumps(review))
        self.assertNotIn("Friday: send", json.dumps(self.invoke("context", accepted=(2,))))
        self.assertEqual(snapshot(self.vault), before)
        self.invoke("approve", "--review-token", review["review_token"])
        active = json.dumps(self.invoke("context"))
        self.assertIn("Monday: send the revised draft", active)
        self.assertNotIn("Friday: send the first draft", active)
        self.assertEqual(handoff.read_bytes(), new)
        handoff.write_bytes(note("Tuesday: next update"))
        second_review = json.dumps(self.invoke("review"))
        self.assertIn("Monday: send the revised draft", second_review)
        self.assertNotIn("Friday: send the first draft", second_review)

    def test_reclassifying_handoff_suppresses_its_stored_original(self):
        handoff = self.project / "handoff.md"
        handoff.write_bytes(note("PREVIOUS_INTERNAL_HANDOFF"))
        self.activate()
        handoff.write_bytes(note("RECLASSIFIED_HANDOFF", "restricted"))
        before = snapshot(self.vault)
        for command, codes in (("check", (2,)), ("review", (0, 2)), ("context", (2,))):
            with self.subTest(command=command):
                report = json.dumps(self.invoke(command, accepted=codes))
                self.assertNotIn("PREVIOUS_INTERNAL_HANDOFF", report)
                self.assertNotIn("RECLASSIFIED_HANDOFF", report)
        self.assertEqual(before, snapshot(self.vault))

    def test_missing_or_invalid_approval_snapshot_cannot_supply_an_original(self):
        handoff = self.project / "handoff.md"
        handoff.write_bytes(note("PREVIOUS_VERIFIED_HANDOFF"))
        self.activate()
        receipt_path = self.project / ".kos-context-approval.json"
        receipt = json.loads(receipt_path.read_bytes())
        handoff.write_bytes(note("NEW_HANDOFF"))
        legacy = {key: receipt[key] for key in ("review_token", "classify_unmarked")}
        legacy["schema"] = "kos-context-approval/v1"
        for label, baseline in (
            ("legacy without snapshot", json.dumps(legacy).encode()),
            ("corrupt snapshot", b'{"schema":"kos-context-approval/v2","approved_files":null}'),
            ("removed receipt", None),
        ):
            with self.subTest(label=label):
                if baseline is None:
                    receipt_path.unlink()
                else:
                    receipt_path.write_bytes(baseline)
                before = snapshot(self.vault)
                checked = self.invoke("check", accepted=(2,))
                self.assertNotEqual(checked["status"], "active")
                review = self.invoke("review", accepted=(0, 2))
                self.assertNotIn("PREVIOUS_VERIFIED_HANDOFF", json.dumps(review))
                if baseline is not None:
                    self.assertFalse(review.get("review_token"))
                self.assertNotIn("PREVIOUS_VERIFIED_HANDOFF", json.dumps(self.invoke("context", accepted=(2,))))
                self.assertEqual(before, snapshot(self.vault))


if __name__ == "__main__":
    unittest.main()
