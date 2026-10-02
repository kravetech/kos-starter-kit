# kos-example

<description>

This is a KOS Power-Up: an optional, independently installed and versioned
extension that integrates with a Knowledge OS through the manifest-driven
contract defined by the KOS Starter Kit (`docs/POWER-UP-MANIFEST-SPECIFICATION.md`
in the starter kit, or the copy under `00 - System/Power-Ups/` in a KOS
instance). It does not become part of the KOS core and is never installed
automatically.

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

This Power-Up is installed **outside** any KOS vault, typically as a sibling
directory (for example `<workspace-root>/KOS Power-Ups/kos-example/`). See
`docs/installation.md`.

## Compatible Agents

Codex, Claude Code, Gemini CLI, and other filesystem-capable agents, via the
canonical skill at `.agents/skills/kos-example/SKILL.md`. Provider adapters
under `adapters/` stay thin; they point at the canonical skill rather than
duplicating its logic.

## License

<license>
