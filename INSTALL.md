# Installation Guide

## Recommendation

Use answer-file mode for repeatable installations. Use interactive agent mode for first-time design decisions. Always run a dry run before a migration.

Use a new or empty target for standard installations. Existing non-empty targets require migration mode; interrupted installations require resume mode. Filesystem roots, the user profile/home directory, starter-kit ancestors, and link/reparse-point targets are rejected.

## Requirements

- Windows: PowerShell 7+ recommended; Windows PowerShell 5.1 is supported by the installer.
- macOS/Linux: Bash 4+ and Python 3.
- Optional: Codex CLI, Claude Code, Git, Obsidian, VS Code.

## Codex

```powershell
.\initialize.ps1 -Agent codex -Answers .\installer\answers.json
```

The initializer invokes the locally supported `codex -C <starter-kit> "<prompt>"` form.

## Claude

```powershell
.\initialize.ps1 -Agent claude -Answers .\installer\answers.json
```

The initializer invokes the locally supported `claude --add-dir <starter-kit> "<prompt>"` form.

## Windows

```powershell
.\install.ps1 -Answers .\installer\answers.json -DryRun
.\install.ps1 -Answers .\installer\answers.json
.\install.ps1 -Answers .\installer\answers.json -Resume
.\install.ps1 -Answers .\installer\answers.json -Migration
```

## macOS and Linux

```bash
chmod +x initialize.sh install.sh scripts/*.sh
./install.sh --answers ./installer/answers.json --dry-run
./install.sh --answers ./installer/answers.json
./install.sh --answers ./installer/answers.json --resume
./install.sh --answers ./installer/answers.json --migration
```

## Modes

- Interactive: an AI agent asks only questions without safe defaults.
- Answer file: loads validated JSON.
- Default: uses conservative Standard-mode defaults.
- Dry run: creates only a proposed manifest.
- Resume: continues from installer state.
- Migration: preserves existing files and creates `.new.md` proposals for conflicts.

## Conflicts

Existing files are preserved. If intended content differs, the installer creates `<name>.new.md` (or `<name>.new`) and records the conflict. Overwrite occurs only when explicitly enabled.

## Rollback

For a new installation, delete only the exact target after reviewing the installation report. For migration, restore the timestamped backup created before changes. Git initialization never configures a remote or pushes.

Generated repositories should use private remotes. Installation state, installation reports, and backups are ignored because they contain local path and operational metadata.

## Troubleshooting

- Exit `2`: invalid input, unsafe path, missing requirement, or validation failure.
- Exit `3`: unexpected script failure.
- Review `00 - System/Installation/installer-state.json`.
- Run the platform validation and privacy scripts against the target.
