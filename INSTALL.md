# Install KOS Community

KOS Community 1.3.1 includes the installer for new and existing vaults. Obsidian is optional. Choose a new or empty folder for a new workspace, then open it in your preferred Markdown editor.

Download the installer ZIP from the release linked by [Get KOS](https://getkos.io/get-started/). For tag `v1.3.1`, choose `kos-community-v1.3.1.zip`. Compare its SHA-256 with the checksum for that release. Extract the verified ZIP outside the target vault. Run the commands from the extracted package using Windows PowerShell 5.1 or PowerShell 7, or Bash with Python 3.10 or newer.

## Create a new workspace

Copy `installer/answers.example.json` to `installer/answers.json` and set your own values there. Select your preferred name, providers and restricted folders using the [setup questions](QUESTIONNAIRE.md). For a preview, run the command for your shell.

```powershell
./install.ps1 -Answers ./installer/answers.json -Target ../My-KOS -Operation new -DryRun
```

```bash
bash install.sh --answers installer/answers.json --target ../My-KOS --operation new --dry-run
```

Check the target and planned files. After approval, repeat the same command with `-Approve` in PowerShell or `--approve` in Bash in place of the dry-run flag. Validate the installed workspace with the validation command below, using the same target. The distribution supplies its standard placeholder files and both script sets. Configure external integrations or scheduled jobs manually after setup.

## Update an existing KOS vault

Create a verified full backup outside the original vault and prepare a disposable copy. Check its edition, privacy exclusions, selected providers and enabled packages. If an older installation record omits custom settings, use the original reviewed answers for preview and apply.

Check upgrade eligibility against `supportedUpgradeVersions` in the extracted installer's `installer/release.json`. Both vault records described below are under `00 - System/Installation/`.

| Vault record | Version to compare with the supported list |
| --- | --- |
| Managed Community vault with `kos-installation.json` | `starterKitVersion`, the installed distribution version. The installer also checks `installerVersion`, `communityVersion` when present, and `kosContractVersion` to prevent downgrades. |
| Legacy vault with `installer-state.json` | `installer_version`, the recorded legacy installer version. If it is missing, recover it from a verified backup before continuing. |

Preview the disposable copy first. Substitute its path for `../KOS-Test-Copy`.

```powershell
./install.ps1 -Target ../KOS-Test-Copy -Operation upgrade -DryRun
```

```bash
bash install.sh --target ../KOS-Test-Copy --operation upgrade --dry-run
```

Without an answers file, the installer can update recognized version information while preserving the vault’s name, owner, timezone and original installation date. The plan identifies personalized files it could not safely regenerate. Supply the original reviewed answers with `-Answers` or `--answers` if you want proposals for those files.

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

For an interrupted operation, inspect the run journal before planning a rollback. Rollback preserves later user edits and can return exit code 4 for partial recovery. Validation and rollback can export both JSON and Markdown to separate new files outside the vault. The rollback exports record the final recovery status. To reproduce the entire original vault, restore the verified full backup into a fresh folder. See the [operation and recovery guide](docs/INSTALLER-V1.2.md) and [package management](docs/PACKAGES-V1.md).
