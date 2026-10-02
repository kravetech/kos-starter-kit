# KOS Starter Kit

The official open-source bootstrap distribution for KOS Community, built on the shared KOS Core architecture.

KOS Starter Kit provides a Markdown-first, AI-ready installer for creating a portable Knowledge OS for business, projects, personal work, research, learning, and AI-assisted execution.

## Where This Fits

**Kraven Knowledge OS (KOS)** is the overall product family:

- **KOS Core** — shared technical architecture and compatibility contract.
- **KOS Community** — free and open-source edition.
  - **KOS Starter Kit** — official open-source bootstrap distribution.
- **KOS Pro** — separately licensed commercial edition.
- **KOS Enterprise** — planned organizational and multi-user edition.

KOS Community remains independently useful and does not require a KOS Pro entitlement.

## What It Generates

- Numbered Obsidian-compatible domain structure.
- Canonical `AGENTS.md` router with thin Claude and Codex adapters.
- Durable `memory.md` and current-state `handoff.md`.
- Context, metadata, privacy, token, archive, and automation policies.
- Optional examples, Git initialization, and migration-safe conflict files.
- Installation state, privacy scan, and validation report.

## Supported Execution

- Codex CLI
- Claude Code
- PowerShell 7+
- Bash 4+ with Python 3
- Obsidian and VS Code
- Any capable agent that can execute `KOS-INSTALLER.md`

## Quick Start

Windows:

```powershell
.\initialize.ps1 -Agent codex
```

macOS or Linux:

```bash
./initialize.sh --agent codex
```

Direct answer-file installation:

```powershell
.\install.ps1 -Answers .\installer\answers.example.json -DryRun
.\install.ps1 -Answers .\installer\answers.example.json
```

## Privacy Model

The reference system is used only to derive reusable architecture and behavior. Its private notes, identities, organizations, projects, histories, inventories, credentials, and operational state are not included. Generated sensitive material defaults to internal or restricted handling. External integrations start as `Not configured`.

Generated Knowledge OS repositories are private by default. They may contain identity, business, project, daily, personal, attachment, and installation metadata. Do not connect a generated system to a public remote without a separate content review.

## Project Structure

- `KOS-INSTALLER.md`: canonical agent-executable installer contract.
- `QUESTIONNAIRE.md`: interactive and answer-file questions.
- `installer/`: schema, examples, state template, and installation engine.
- `templates/`: neutral source templates.
- `scripts/`: installation validation, privacy, manifest, and Power-Up utilities.

## Status

Starter Kit 1.2.0 targets KOS Community 1.0.0 and KOS Core contract 1.0.0. Follow [INSTALL.md](INSTALL.md) for current installation and upgrade commands.

## License

This project is licensed under the Apache License 2.0.

See the [LICENSE](LICENSE) file for the full license text and the [NOTICE](NOTICE) file for attribution information.

## v1.2 safe operations

See [installation, upgrade and recovery](docs/INSTALLER-V1.2.md) and [local packages](docs/PACKAGES-V1.md). Start with a dry-run. New installs create; upgrades reconcile; Obsidian enhancements adopt. The public installer does not implement KOS Pro activation.
