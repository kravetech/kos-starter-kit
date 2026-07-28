# Knowledge OS Questionnaire

Use interactive mode, JSON-answer mode, defaults, dry-run, resume, or migration mode. Questions with safe defaults are optional. The machine-readable contract is `installer/questionnaire.schema.json`.

## User Identity

| Key | Prompt | Default |
| --- | --- | --- |
| `user.preferred_name` | Preferred name? | Required |
| `user.full_name` | Full name? | Empty |
| `user.author_name` | Public author name? | Preferred name |
| `user.technical_username` | Technical username? | Normalized preferred name |
| `user.role` | Primary role? | Knowledge worker |
| `user.timezone` | IANA timezone? | UTC |
| `user.locale` | Country or locale? | en |
| `user.language` | Preferred language? | English |
| `user.communication_style` | Writing and communication style? | Direct, concise, practical |

## System Identity

Ask for system name, short name, root folder name, description, motto, and installation date. Defaults are `Knowledge OS`, `KOS`, a normalized folder name, a neutral description, no motto, and today's date.

## Intended Use and Tools

Select any of: business, projects, software development, personal management, content creation, research, learning, finance, hobbies, client management, product development.

Select installed or intended tools: Obsidian, VS Code, Codex, Claude Code, Git, GitHub, OneDrive, Google Drive, Gmail, Google Calendar, Telegram, n8n.

## Privacy

Choose default AI access plus business, personal, and linked-source access. List restricted folders and whether sensitive files should be excluded automatically. Recommended defaults: `internal`, personal `restricted`, linked sources `restricted`, automatic exclusion enabled.

## Operating Rhythm

Set daily review time, weekly review day, monthly review preference, and toggles for daily-note generation, inbox processing, memory maintenance, handoff maintenance, Git review, and project-health checks.

## Installation Mode

Choose `lean`, `standard`, `business`, `developer`, `creator`, `custom`, or `migration`.

## Installation Options

Set target directory, Git initialization, initial commit, sample files, `.gitkeep`, Windows scripts, Unix scripts, external integration definitions, overwrite permission, and backup-before-migration.

Target safety rules:

- Standard installation requires a new or empty directory.
- Migration mode is required for an existing non-empty vault.
- Resume mode requires an existing matching installer-state file.
- Filesystem roots, the user home/profile directory, starter-kit ancestors, protected/reference paths, and link/reparse-point targets are rejected.
- Git initialization never creates a remote or pushes. Keep generated remotes private unless their content receives a separate publication review.

## Execution Flags

- Dry run: do not generate the KOS; create a proposed manifest.
- Resume: continue from saved state without repeating completed phases.
- Migration: preserve existing content and create proposed conflict files.
- Default: use schema defaults and ask only for preferred name and target.
