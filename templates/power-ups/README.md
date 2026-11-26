---
title: "{{system_short_name}} Power-Ups"
type: system-policy
status: active
owner: "{{preferred_name}}"
created: {{installation_date}}
updated: {{installation_date}}
ai_access: internal
ai_generated: true
review_status: draft
canonical: true
---

# {{system_short_name}} legacy YAML Power-Up registry

This template describes the layout of an older YAML registry. The Community
installer supports read-only discovery and status for that layout. Current
packages use `manifest.json` and the vault’s `Registry/power-ups.json`.
Follow `docs/POWER-UP-INSTALLATION-GUIDE.md` in the extracted installer to
install, enable, update or remove a package.

## What a Power-Up Is

A KOS Power-Up is an optional, independently versioned extension that connects to
{{system_short_name}} through a manifest-driven contract. Power-Ups are never a
required part of the core Knowledge OS. {{system_short_name}} works completely
without any Power-Up installed.

## What Belongs in This Folder

Only KOS-side integration metadata:

- `registry.yaml` — the list of Power-Ups this {{system_short_name}} instance knows
  about, their status, and where their runtime lives.
- `settings.yaml` — shared Power-Up configuration for this installation
  (installation mode, discovery, environment variable name, allowed agents).
- `manifests/` — copies or references of each registered Power-Up's `manifest.yaml`
  used for offline validation and compatibility checks.
- This `README.md`.

## External runtimes in the legacy layout

The actual Power-Up software — code, dependencies, adapters, runtime state,
caches, logs, and inbox/review queues — must **not** live inside this folder or
anywhere else in the numbered vault structure by default. In the recommended
external installation mode it lives in a sibling directory such as:

```text
<workspace-root>/
├── Obsidian/<Vault>/            # this Knowledge OS
└── KOS Power-Ups/               # Power-Up runtimes, one folder per Power-Up
    └── kos-example/
```

This folder only ever stores a pointer (`install_path`) to that location, plus
the metadata needed to validate and route to it. Never copy an entire Power-Up
runtime into this folder or commit machine-specific absolute paths here — use
the `{{power_ups_home_environment_variable}}` environment variable or a path
relative to the workspace root instead.

## How historical registrations were recorded

1. Older tools discovered the Power-Up at its `install_path`.
2. They checked its `manifest.yaml` for a unique `id`, semantic `version`, a
   compatible `kos_compatibility` range, declared permissions, and lifecycle
   commands.
3. After validation and approval, older tools could append an entry to
   `registry.yaml`. The current discovery and status commands only read it.

See `docs/POWER-UP-INSTALLATION-GUIDE.md` in the Community installer package (or your
{{system_short_name}} copy of it under this folder, if you keep documentation
in-vault) for the full command sequence.

## Historical lifecycle fields and scripts

- **Enable/disable** — flip `status` in the Power-Up's `registry.yaml` entry.
  Disabling stops adapters from invoking it; it does not remove files.
- **Upgrade** — the Power-Up's own `installer/upgrade.*` script checks
  compatibility, backs up its manifest/config, preserves your approved data,
  and only then updates the registry's `version`/`updated_at` fields.
- **Repair** — recreate missing generated or standard files only; user data in
  `approved/`, `review/`, and similar workflow folders is never overwritten
  without explicit approval.
- **Uninstall** — disable first, show what will be affected, remove the
  runtime only after approval, and remove the registry entry only once the
  runtime is gone. Cleaning up any per-folder workspaces
  (`<Target>/.kos/power-ups/<id>/`) is a separate, opt-in step.

## Credentials

`registry.yaml`, `settings.yaml`, and any manifest copied into `manifests/`
must never contain API keys, tokens, passwords, or other secrets. Power-Ups
that need credentials must read them from environment variables or OS secret
storage — never from tracked KOS configuration.

## Local Absolute Paths

Do not hand-edit an absolute, machine-specific path into `registry.yaml`.
Prefer an `install_path` built from the `{{power_ups_home_environment_variable}}`
environment variable (for example `{{power_ups_home_environment_variable}}/<power-up-id>`,
rendered by an agent as `${{power_ups_home_environment_variable}}/<power-up-id>` in shell
form) so the registry stays portable across machines. If a literal path is
unavoidable, keep it out of anything you intend to publish or share.

## Folder Initialization

A Power-Up is installed once but may be initialized for any number of KOS
folders you explicitly approve (for example, one client folder under
`01 - Business/Companies/` and one project under `02 - Projects/Active/`).
Initialization creates a small `.kos/power-ups/<id>/` workspace inside the
target folder — it never duplicates the Power-Up's runtime or dependencies.
Every initialized target is recorded in this Power-Up's `registry.yaml` entry
under `initialized_targets`.

## Context Loading

Agents must not load every installed Power-Up during routine bootstrap. Load
`registry.yaml` (or `settings.yaml`) only when Power-Up availability is
relevant, and load a specific Power-Up's `SKILL.md`/manifest only when that
Power-Up is actually being invoked. See `CONTEXT-POLICY.md` and
`00 - System/Config/ai-context-manifest.yaml`.
