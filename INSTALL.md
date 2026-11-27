# Install KOS Community

KOS Community 1.4.0 includes the installer for new and existing vaults. Obsidian is optional. Choose a new or empty folder for a new workspace, then open it in your preferred Markdown editor.

For guided setup, paste the [Community setup prompt](docs/prompts/setup.md) into Codex, Claude Code or Gemini CLI. Your agent retrieves the verified release and proposes the locations for you to review.

For manual setup, download the named installer from the [Community release page](https://github.com/kravetech/kos-community/releases/latest). The named asset for this release is `kos-community-v1.4.0.zip`. Compare its SHA-256 with the checksum for that release. Extract the verified ZIP outside the target vault. Run the commands from the extracted package using Windows PowerShell 5.1 or PowerShell 7, or Bash with Python 3.10 or newer.

## Guided setup

From a trusted checkout or verified installer that includes `setup.py`, run the command with Python 3.10 or newer. The target defaults to the current directory. Starting in the installer folder or your home directory proposes an unused `My KOS` folder under your home directory. Use `--target` to choose another location.

```sh
python setup.py https://github.com/kravetech/kos-community --target "../My KOS"
```

For an existing local release ZIP, pass its path in place of the repository URL. Setup verifies local ZIPs with a known published checksum offline. Other versions require GitHub to verify their exact tag. The repository URL always resolves the published stable release, even when this launcher is run from a newer checkout.

Review the proposed settings in the preview. For a new vault, use `--adapter codex`, `claude`, `gemini` or `none` to set the adapter, or `--answers FILE` to supply local preferences. One approval creates and validates the vault. A current vault exits immediately.

For an update, review all intervening release notes and the suggested backup and test-copy paths. Use `--recovery-parent DIR` to change the private location. Approve the backup and rehearsal, review the actual result, and approve a fresh plan for the original. Enter `details` at an approval to see its full file list. If the original changes, rerun setup for a fresh rehearsal. Each applied run prints the local summary and journal paths. After an interruption, inspect the reported journal and retained backup before retrying.

### First run with an agent

The copyable prompt works before a vault or Skill exists. The agent needs terminal access and Python 3.10 or newer.

1. Resolve the folder the user named, or use the original working directory. If they started in their home directory, the filesystem root or the installer folder and gave no target, let the launcher propose an unused `My KOS` location.
2. Resolve the official [latest stable release metadata](https://api.github.com/repos/kravetech/kos-community/releases/latest) once. Keep its `vX.Y.Z` tag. Select the single named installer asset `kos-community-vX.Y.Z.zip` for that tag, download it to a new private temporary directory outside the vault, and compare its SHA-256 with the asset's published `sha256:` digest. GitHub's generated source archives use a different format. Stop if the official package or digest is missing, ambiguous or mismatched.
3. Extract the verified installer into that private directory. Check that the release version in `installer/release.json` matches the selected tag and that `setup.py` exists. A release missing the guided launcher requires a compatible published launcher before proceeding.
4. From the original working directory, launch the verified entry point in an interactive terminal. Pass the same downloaded file as the source so the installer uses exactly the release already selected. For a supplied Community release ZIP, pass its path as the source to the trusted launcher. The launcher verifies the attachment before using its contents.

   ```sh
   python -I -B "/path/to/verified/installer/setup.py" "/path/to/selected-release.zip" --target "/path/to/vault" --adapter codex
   ```

   Substitute the actual absolute paths. Omit `--target` to use the launcher's proposed location in step 1. Use `claude` or `gemini` for those clients. The adapter selection applies only to a fresh install.
5. Relay each live approval to the user and send their answer only to that prompt. If the client cannot keep an interactive session open, give the user the exact prepared command to run in their terminal and keep the verified files available until that command finishes. An interrupted or blocked run ends at its reported checkpoint. Read the completion receipt for the actual changes, preserved customizations, unresolved proposals, validation and recovery paths.

### Reuse the setup Skill

For repeated setups, copy the full `skills/kos-community-fix` directory from a verified Community kit into a tools workspace you control. Keep its `scripts` folder beside `SKILL.md`. Choose an unused destination.

| Client | Destination in the tools workspace |
| --- | --- |
| Codex or Gemini CLI | `.agents/skills/kos-community-fix/` |
| Claude Code | `.claude/skills/kos-community-fix/` |

Start a fresh session in the tools workspace. Gemini CLI discovers local skills after you trust that workspace. Ask for `kos-community-fix`, paste the official Community repository URL or attach a local Community release ZIP, and give the absolute path of your separate vault or new vault folder. Pass that path as `--target` whenever running from the tools workspace. An attached ZIP selects that exact published version. The Skill runs the same guided workflow and returns the local report.

To diagnose missing files, links or extension problems in an installed vault, use the helper's read-only check with an explicit target. It reports validation and compatibility findings, including for a vault already on the selected version. Exit code 2 calls for review. [Skill instructions](skills/kos-community-fix/SKILL.md)

```sh
python -I -B "/path/to/kos-community-fix/scripts/start.py" https://github.com/kravetech/kos-community --target "/path/to/vault" --check
```

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

In guided setup, approve the proposed backup and test-copy locations together. For a manual update, create a verified full backup outside the original vault and prepare a disposable copy. Check its edition, privacy exclusions, selected providers and enabled packages. If an older installation record omits custom settings, use the original reviewed answers for preview and apply.

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
