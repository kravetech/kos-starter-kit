---
name: kos-community-fix
description: Install or update a KOS Community vault from https://github.com/kravetech/kos-community or a Community release ZIP. Diagnose missing files, broken links and extension issues in an existing Community vault.
---

# KOS Community setup

Use the Community guided installer to identify the vault and select a fresh install, supported update or already-current result. Keep the skill and downloads outside the target.

Use the supplied local ZIP as the selected version when there is an attachment. Otherwise use `https://github.com/kravetech/kos-community`. A URL or release attachment sent by itself starts the preview. If a surrounding request is about reading or explaining the repository, follow that request.

## Run the guided installer

Run the [bundled helper](scripts/start.py) from this trusted skill folder with Python 3.10 or newer. Use absolute paths for the helper and any supplied vault or ZIP. Pass each argument separately. Set the adapter to the active client (`codex`, `claude` or `gemini`) unless the user requested another. Adapter selection applies to fresh installs.

```sh
python -I -B "/path/to/kos-community-fix/scripts/start.py" "https://github.com/kravetech/kos-community" --target "/path/to/vault" --adapter codex
```

For an attachment, replace the URL with its local path. Keep the user's working directory when launching the helper. Omit `--target` to use the installer's normal folder proposal. If the user wants to update an existing vault and its location is unclear, ask for that folder. The helper verifies the selected release and locates a guided launcher. If a verified older release needs a launcher and none is available, relay that finding and stop.

## Handle approvals and results

1. Run setup interactively. Show the user its proposed target, version and settings. For an update, show the release changes and both proposed recovery paths. Ask for each decision when the installer reaches it. Forward only the user's answer to that pending prompt. If the client cannot keep stdin open across turns, give the user the exact helper command with their resolved paths to run in an interactive terminal. After a handoff, read the final result or local summary for the original vault before reporting completion. A rehearsal, cancellation or exit code alone cannot confirm a live update.
2. A fresh install has one approval. An update has two. The first approves the backup and rehearsal. Show the rehearsal result and ask separately before updating the original. Leave customizations, conflicting proposals and changes to recovery paths under the user's control.
3. For a current vault, report its version and path. For an applied run, show the previous and installed versions where available, actual changes, preserved skills and modules, proposals, link findings, validation, and local report. Include the retained backup and journal for an update. End a fresh install with the first action from its report.
4. If setup stops, report the reason and any journal and recovery paths it printed. A different edition requires its own installer.

## Diagnose a reported problem

For missing files, broken links, or an extension problem in an installed vault, start with a read-only check. This also applies when a vault is already current. Use the same trusted helper and selected source.

```sh
python -I -B "/path/to/kos-community-fix/scripts/start.py" "https://github.com/kravetech/kos-community" --target "/path/to/vault" --check
```

Report the validation and link or extension findings. Exit code 2 calls for review. A version update follows the normal backup and rehearsal workflow above. Repairing files, rolling back a run or merging proposals requires a separate decision on those specific changes.
