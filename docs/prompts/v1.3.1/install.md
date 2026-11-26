# Install KOS Community 1.3.1 in a new folder

Use this for a new or empty folder. For an existing KOS vault, use the [upgrade prompt](update.md). Copy the entire block into Codex CLI or Claude Code.

```text
Help me install KOS Community 1.3.1.

Ask me for the path where I want to create my new KOS vault. It must be a new or empty folder. Resolve the full path and check for existing contents, including hidden files. If the folder contains anything, stop and offer the existing-vault guide. Obsidian is optional.

Download the named release asset kos-community-v1.3.1.zip from the official KOS Community release:
https://github.com/kravetech/kos-community/releases/tag/v1.3.1

Calculate the ZIP’s SHA-256 before extracting it. Both the calculated value and the checksum published on the release page must match this expected value:
296f7a4ceda957d6c04242331c664988688eea789979d1881ef1cfda9c362376

Stop if the published checksum is unavailable or any value differs. Extract the verified ZIP into a separate package folder outside the vault.

Read INSTALL.md and installer/release.json from the extracted package. Use installer/answers.example.json to prepare my answers file outside the vault. Ask which preferred name or alias to use, which folders AI should exclude, and which AI adapters I want: Codex, Claude, Gemini, or none. Let me enter personal details locally. Leave Git initialization off unless I request it. Keep automatic commits and external integrations off.

Run the packaged PowerShell or Bash installer with the new operation. Explicitly pass -DryRun or --dry-run, even when using an answers file. Show me the full target path, Community and installer versions, selected adapters, privacy exclusions, planned file changes, and any blockers. Stop and wait for my approval of that exact plan.

Only after I approve, apply the installation to the same target using the same answers and the explicit -Approve or --approve flag. If the target, its contents, or the answers have changed since the preview, run a fresh dry run and ask me to approve the revised plan.

After installation, run the validate operation. Tell me whether validation passed, where the local report is, and which folder to open in my preferred Markdown editor. If installation or validation fails, stop and show me the error and the local report or run journal.
```
