# KOS Community setup questions

Use this guide with the packaged installer. Set personal values in a local answers file outside the target vault. The supplied example is fictional. A direct installation works without an AI account. The machine-readable contract is [the questionnaire schema](installer/questionnaire.schema.json).

## New installation

The [Community setup prompt](docs/prompts/setup.md) shows the proposed target, adapter and privacy defaults for one approval. Personalization can wait. Use the questions below to prepare a custom answers file or run a manual installation.

1. Use the supplied target or propose an unused `My KOS` folder under the user’s local home directory. Check the full path and hidden contents. Obsidian is optional.
2. Which preferred name or alias should appear in the workspace? Replace the example identity and check the author name and technical username in your local answers.
3. Which AI adapters should the installer configure? Select any of `codex`, `claude` and `gemini` in `installation.providers`, or use an empty list. Include Gemini explicitly when selected. The default list contains Codex and Claude.
4. Which folders should AI exclude? Review the access settings for business, personal and linked-source content, along with any additional restricted folders.
5. Would you like to customize the workspace? Optional settings include the system name, language, timezone, daily and weekly routines, intended uses, profile, samples and local Git initialization. Configure external integrations and scheduled jobs yourself after setup.
6. Does the preview show the intended target, providers and files? Always pass `-DryRun` or `--dry-run` for the preview, even when supplying an answers file. Wait for approval before applying the reviewed plan, then run validation.

The installation date defaults to the installer computer's local calendar date. The preview includes `installationDate`. Set `system.installation_date` to an explicit `YYYY-MM-DD` in your answers to use a different timezone's date or to keep the reviewed date when applying after midnight. Upgrades and repairs keep the original date. For older installations, supply the original date if the installer cannot verify it from the vault.

New answer files can omit four legacy `installation` fields. Older answers remain valid with `include_gitkeep: true`, `enable_windows_scripts: true`, `enable_unix_scripts: true` and `configure_external_integrations: false`. The distribution supplies both sets of scripts and its standard placeholder files. A request to change any of these four values stops setup for review.

## Update an existing workspace

1. Use the supplied vault or the current folder if its installer records identify it. Ask which vault only when ambiguous.
2. Which edition and distribution does the vault record? For a managed Community vault, compare `starterKitVersion` in `kos-installation.json` with `supportedUpgradeVersions` in the new installer’s `installer/release.json`. For a legacy vault recorded in `installer-state.json`, compare its `installer_version` with that list. A missing legacy version requires manual review. Plain Obsidian folders use the enhancement route. Legacy Pro vaults use their own maintenance tools.
3. Which existing privacy exclusions, provider choices, packages and custom instructions need to survive? Reuse the owner's existing choices. Consult the original answers file if an older installation did not retain a setting.
4. Dry-run the original read-only. Show the planned rehearsal changes and exact original, backup and test-copy paths together. Propose a new private `<vault-name>-recovery/<timestamp>/` sibling with `backup` and `test-copy` children, or a private local alternative outside sync. Ask once for permission to create and verify the backup and rehearse there. Close editors and pause sync. Use fresh, nonoverlapping destinations outside the vault. Include hidden files and preserve links without following them. Verify paths, file hashes and link targets before creating the independent test copy. Dry-run the copy, apply only the approved rehearsal changes there and validate it. If the plan differs materially, get approval again. Check notes, links, settings, proposals and installed workflows.
5. Check the original still matches the verified snapshot. Repeat preparation if it drifted. Obtain separate approval for the fresh original-vault plan, then apply, validate and keep the run ID. The installer backs up changed files. An exact full-vault restore uses the verified external backup.

For an interruption, inspect the journal and use the [recovery procedure](docs/INSTALLER-V1.2.md). The installer blocks automatic resume, global overwrite, the obsolete `backup_before_migration` setting and automatic initial commits.
