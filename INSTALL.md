# Install KOS Community

KOS Community 1.1.0 uses Starter Kit and installer 1.3.0. Obsidian is optional. Choose a new or empty folder for KOS Community, then open it in your preferred Markdown editor.

Download the customer ZIP from the release linked by [Get KOS](https://getkos.io/get-started/). Compare its SHA-256 with the checksum for that release. Extract the verified ZIP outside the target vault. Run the commands from the extracted package using Windows PowerShell 5.1 or PowerShell 7, or Bash with Python 3.10 or newer.

## Create a new workspace

Copy `installer/answers.example.json` to `installer/answers.json` and set your own values there. Select your preferred name, providers and restricted folders using the [setup questions](QUESTIONNAIRE.md). For a preview, run the command for your shell.

```powershell
./install.ps1 -Answers ./installer/answers.json -Target ../My-KOS -Operation new -DryRun
```

```bash
bash install.sh --answers installer/answers.json --target ../My-KOS --operation new --dry-run
```

Check the target and planned files. After approval, repeat the same command with `-Approve` in PowerShell or `--approve` in Bash in place of the dry-run flag. Validate the installed workspace with the validation command below, using the same target.

## Update an existing KOS vault

Create a verified full backup outside the original vault and prepare a disposable copy. Check the original edition, recorded installer version, privacy exclusions, selected providers and enabled packages. If older custom settings are missing from the installation record, use the original reviewed answers when you preview and apply. Stop if you cannot establish the original version.

Preview the disposable copy first. Substitute its path for `../KOS-Test-Copy`.

```powershell
./install.ps1 -Target ../KOS-Test-Copy -Operation upgrade -DryRun
```

```bash
bash install.sh --target ../KOS-Test-Copy --operation upgrade --dry-run
```

Review managed updates, preserved files, proposals, links and blockers. After approval, repeat the command with the approval flag. Once apply succeeds, validate the same target.

```powershell
./install.ps1 -Target ../KOS-Test-Copy -Operation validate
```

```bash
bash install.sh --target ../KOS-Test-Copy --operation validate
```

Open representative notes in your editor, inspect links and proposals, verify privacy settings and exercise existing workflows. Before updating the original, close editors and sync clients, preview its exact path and obtain separate approval. Keep the run ID and validation result.

## Other starting points and recovery

Use `enhance` for a recognized plain Obsidian vault. Minimal enhancement is the default. The complete profile also adds missing numbered folders. Existing notes stay in place. An unrelated nonempty notes folder requires manual review.

For an interrupted operation, inspect the run journal before planning a rollback. Rollback preserves later user edits and can return exit code 4 for partial recovery. To reproduce the entire original vault, restore the verified full backup into a fresh folder. See the [operation and recovery guide](docs/INSTALLER-V1.2.md) and [package management](docs/PACKAGES-V1.md).
