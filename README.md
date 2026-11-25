# KOS Community

KOS Community 1.1.0 is a portable Markdown workspace for notes, projects and AI-assisted workflows. Starter Kit 1.3.0 is its installer and handles upgrades from earlier releases.

Obsidian is optional. Choose a new or empty folder for KOS Community, then open it in your preferred Markdown editor. For an existing KOS vault, follow the [update instructions](INSTALL.md#update-an-existing-kos-vault).

## Where This Fits

**Kraven Knowledge OS (KOS)** is the overall product family:

- **KOS Core** — shared technical architecture and compatibility contract.
- **KOS Community** — free and open-source edition.
  - **KOS Starter Kit** — official open-source bootstrap distribution.
- **Commercial workflows** run as Power-Ups on the Community host. An individual purchase grants use of the purchased version. The combined Academy Pro + KOS Pro subscription covers eligible workflows included in the plan. A workflow marked for separate purchase requires its own purchase.
- **Legacy Pro 1.1.0** is an earlier commercial distribution with its own license.
- **KOS Enterprise** — planned organizational and multi-user edition.

The bundled Project Action List Power-Up and its local automation are free to use on Community.

## What It Generates

- Numbered Obsidian-compatible domain structure.
- Canonical `AGENTS.md` router and adapter instructions for Gemini CLI, Claude Code and Codex CLI.
- Durable `memory.md` and current-state `handoff.md`.
- Context, metadata, privacy, token, archive, and automation policies.
- Optional examples, Git initialization, and migration-safe conflict files.
- Installation state, privacy scan, and validation report.

## Installation and workflow clients

Use the direct installer with Windows PowerShell 5.1, PowerShell 7, or Bash with Python 3.10+. For agent-assisted setup, the initialize scripts accept `gemini`, `claude`, `codex` or `auto` and launch an installed CLI. The resulting Markdown vault opens in Obsidian or VS Code. [Installation guide](INSTALL.md)

After setup, Gemini CLI, Claude Code and Codex CLI can each call the same versioned Skill for the free Project Action List. Install the two packages, review permissions and opt in the selected project. The tutorial also includes an account-free local run. [Project Action List tutorial](docs/PROJECT-ACTION-LIST.md)

## Quick Start

Windows:

```powershell
.\initialize.ps1 -Agent codex
```

macOS or Linux:

```bash
./initialize.sh --agent codex
```

To preview a direct installation on Windows, prepare your own [answers file](QUESTIONNAIRE.md) and run:

```powershell
.\install.ps1 -Operation new -Target ..\DemoVault -Answers .\installer\answers.json -DryRun
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

This package contains KOS Community 1.1.0 and Starter Kit 1.3.0 with KOS Core contract 1.0.0. Follow [INSTALL.md](INSTALL.md) for installation and upgrade commands. See [Project context](docs/PROJECT-CONTEXT.md) to set up one project and search its selected notes.

## Learning and support

Start with the bundled free tutorial to turn selected meeting tasks into a cited action list, adapt the example and roll back an update. [Project Action List tutorial](docs/PROJECT-ACTION-LIST.md)

For ordinary bugs or documentation questions, search or open an issue. Include the kit and package versions, the command, the error and a small synthetic example. Community support is best effort. [Public issue tracker](https://github.com/kravetech/kos-starter-kit/issues)

Report suspected vulnerabilities or privacy leaks through the private route. [Security reporting instructions](SECURITY.md)

## License

This project is licensed under the Apache License 2.0.

See the [LICENSE](LICENSE) file for the full license text and the [NOTICE](NOTICE) file for attribution information.

## Installation and recovery

Start with a dry run. New installs create a vault, upgrades reconcile managed files, and Obsidian enhancements adopt an existing vault. [Installation, upgrade and recovery](docs/INSTALLER-V1.2.md) · [Local packages](docs/PACKAGES-V1.md)
