# KOS Community setup questions

Use this guide with the packaged installer. Set personal values in a local answers file outside the target vault. The supplied example is fictional. A direct installation works without an AI account. The machine-readable contract is [the questionnaire schema](installer/questionnaire.schema.json).

## New installation

1. Which new or empty folder should contain the workspace? Obsidian is optional. Choose any Markdown editor.
2. Which preferred name or alias should appear in the workspace? Replace the example identity and check the author name, technical username and installation date in your local answers.
3. Which AI adapters should the installer configure? Select any of `codex`, `claude` and `gemini` in `installation.providers`, or use an empty list. Include Gemini explicitly when selected. The default list contains Codex and Claude.
4. Which folders should AI exclude? Review the access settings for business, personal and linked-source content, along with any additional restricted folders.
5. Would you like to customize the workspace? Optional settings include the system name, language, timezone, daily and weekly routines, intended uses, profile, samples, scripts and local Git initialization. Keep external integrations and Git off unless requested.
6. Does the preview show the intended target, providers and files? Always pass `-DryRun` or `--dry-run` for the preview, even when supplying an answers file. Wait for approval before applying the reviewed plan, then run validation.

## Update an existing workspace

1. Where are the original vault, its verified full backup outside that vault, and the separate disposable test copy?
2. What edition and installer version do the records identify? Check the supported versions in the new kit's `installer/release.json`. An unknown legacy version requires manual review. Plain Obsidian folders use the enhancement route. Legacy Pro vaults use their own maintenance tools.
3. Which existing privacy exclusions, provider choices, packages and custom instructions need to survive? Reuse the owner's existing choices. Consult the original answers file if an older installation did not retain a setting.
4. Does the owner approve the preview for the test copy? Apply and validate only after approval. Check notes, links, settings, proposals and installed workflows in the copy.
5. After the copy is accepted, does the owner approve a fresh preview for the original vault? Close other writers, apply, validate and keep the run ID. The installer backs up changed files. An exact full-vault restore uses the verified external backup.

For an interruption, inspect the journal and use the [recovery procedure](docs/INSTALLER-V1.2.md). The installer blocks automatic resume, global overwrite, the obsolete `backup_before_migration` setting and automatic initial commits.
