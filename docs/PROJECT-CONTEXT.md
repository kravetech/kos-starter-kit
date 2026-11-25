# Work with one project

Run the following commands from the vault root with Python 3.9 or newer. On macOS or Linux, use `python3` if that is your local Python command. The tool runs locally without an account or a network connection.

## Set up and review

Replace `Atlas` with a single project folder name under `02 - Projects/Active`. On Windows the command uses the folder's on-disk spelling for its approval, so changing the capitalization of the same folder in a command preserves its approval.

```text
python "00 - System/Tools/ProjectContext/project_context.py" --project Atlas init
```

Open `memory.md` and `handoff.md` in that project with your editor. Put durable facts in memory and the current objective, status and next action in the handoff. Running `init` again preserves existing notes. A new pair starts in draft.

```text
python "00 - System/Tools/ProjectContext/project_context.py" --project Atlas review
python "00 - System/Tools/ProjectContext/project_context.py" --project Atlas approve --review-token REVIEW_TOKEN
python "00 - System/Tools/ProjectContext/project_context.py" --project Atlas check
python "00 - System/Tools/ProjectContext/project_context.py" --project Atlas context
```

Inspect both files and copy the current `review_token` from the review output into the approval command. Approval saves the exact reviewed bytes and checksums of both notes together in the project's `.kos-context-approval.json`. Each approval replaces the last snapshot. For a reviewed legacy note without an access classification, either add `ai_access` yourself and review again, or explicitly accept the proposed internal classification with `--classify-unmarked` on approval. A restricted or excluded note blocks activation.

When either note changes, `check` reports stale and names the edited file under `changed_files`. Run `review` again. It automatically loads the verified original from the local approval snapshot and shows the differences for each changed, permitted note. To accept the edit, approve the review token returned alongside that comparison. To revise it, edit the note and run review again. To keep the original, restore the exact reviewed bytes with your editor or backup and run `check`. Operational reads and search pause until the pair matches a valid approval. You can edit and read your own Markdown throughout.

Keep the snapshot with its original project. If you recovered a snapshot from another project or its checksum fails, restore the matching project backup. The snapshot contains recoverable note content. In a Git worktree, approval uses Git to confirm that the receipt and temporary snapshot path are ignored before it writes original note bytes. The supplied ignore rule is `.kos-context-*`. If `check` or `review` includes a `snapshot_warning`, follow its guidance before the next approval. Check the effective ignore rules and whether Git already tracks the receipt. An ignore rule alone cannot protect an already tracked file. Review any previous sharing before clearing it from the index. Configure any separate file-sync tool to exclude these paths too.

`context` is the agent-facing command to load the approved pair. A blocked operation returns exit code 2, including a blocked `init` or `review`. A successful review can return 0 with a draft or stale pair ready for owner review. Use `check` when a script requires active approval. It returns 0 only for an active pair. For a different working directory, pass `--vault "path to vault"` before the operation.

## Select and search sources

In the selected project, create a UTF-8 Markdown note such as `Notes/meeting.md` with an explicit access classification.

```markdown
---
ai_access: internal
---
# Meeting
Decision: schedule the pilot after the review.
```

```text
python "00 - System/Tools/ProjectContext/project_context.py" --project Atlas sources --source Notes/meeting.md
python "00 - System/Tools/ProjectContext/project_context.py" --project Atlas search --source Notes/meeting.md --query "pilot"
```

Repeat `--source` for each allowed project-relative Markdown path. Windows also accepts its native path separator. Omit a path on the next request to withdraw it. An empty selection searches zero files. `sources` reports the accepted paths and SHA-256 revisions. `search` returns matching line numbers and bounded excerpts. Check `skipped` and `truncated` alongside `matches` before drawing conclusions from an empty result. Use `--max-files` and `--max-results` for smaller searches.

Review and search accept common Obsidian properties, including quoted titles, property names with spaces, tag and alias lists, and folded or literal descriptions. Policy properties such as `ai_access` and `review_status` require a single value. Ambiguous or duplicate keys block access.

The tool enforces folder exclusions and each file's classification. Only `public` and `internal` qualify. Selecting `memory.md` or `handoff.md` uses the active receipt's exact approved revision and effective classification, including a reviewed draft or an explicitly classified legacy note. Other draft or unclassified notes remain ineligible even if their bytes match an approved note. Linked paths and external files stay outside project search. A CLI agent's broader filesystem access is configured separately.

## Existing installations

Use the installer upgrade preview, backup and approval process. Check the tool in `00 - System/Tools/ProjectContext`. Read both `status` and `routing.status` in `check` output. The first describes the project pair. The second checks the shipped instructions in `AGENTS.md`, `CONTEXT-POLICY.md` and the active context manifest. An active pair can have `routing.status` set to `adoption_pending`.

For each entry under `routing.pending`, open its active `path` and compare it with the corresponding `proposal` under `00 - System/Installation/Runs/<upgrade-run>/proposals/`. Replace `<upgrade-run>` with the applicable run. Merge the approved-pair command into the active project rule in `AGENTS.md`, adopt the owner-review requirement in `CONTEXT-POLICY.md`, and set the manifest's top-level `project_loaded` list to `[]`. Preserve your exclusions and run `check` again. A result of `ready` means the check recognized the shipped routing markers. Review any additional custom instructions yourself for conflicts. Independently written equivalent rules can require manual review.

The released 1.2.0 installer did not save the questionnaire's restricted-folder list in its installation state. Supply your original privacy choices during upgrade and check `restricted` and `never_auto_load` in the active context manifest before approving a project. Existing installed restrictions and restrictions supplied to the updated installer are combined.
