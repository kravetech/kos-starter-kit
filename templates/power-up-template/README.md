# kos-example

<description>

This scaffold describes a legacy YAML Power-Up for read-only discovery.
Validate `manifest.yaml` against `installer/power-up-manifest.schema.json` in
the extracted Community installer. To build an installable Power-Up, use the
[v1 package format](../../docs/PACKAGES-V1.md) and the
[working example](../../docs/PROJECT-ACTION-LIST.md).

## Status

Template / starting point. Replace every `<placeholder>` before publishing,
and remove this section.

## Package Structure

```text
kos-example/
├── .agents/skills/kos-example/SKILL.md   # canonical, provider-neutral skill
├── adapters/                             # thin per-agent adapters only
├── config/                               # defaults + validation schemas
├── docs/                                 # architecture, install, usage, upgrade, uninstall
├── installer/                            # install/initialize/upgrade/uninstall scripts
├── runtime/                              # the actual Power-Up code
├── templates/                            # reusable content templates, if any
├── tests/
├── CHANGELOG.md
├── manifest.yaml
├── README.md
└── VERSION
```

## Installation

Keep the legacy example outside the vault while reviewing it. The
[discovery instructions](docs/installation.md) also explain the route to an
installable package. The lifecycle scripts in this scaffold are placeholders.

## Compatible Agents

Codex, Claude Code, Gemini CLI, and other filesystem-capable agents, via the
canonical skill at `.agents/skills/kos-example/SKILL.md`. Provider adapters
under `adapters/` stay thin; they point at the canonical skill rather than
duplicating its logic.

## License

<license>
