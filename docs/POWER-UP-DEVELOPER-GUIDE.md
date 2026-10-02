# Power-Up Developer Guide

Start from `templates/power-up-template/` (copy it out to its own repository
and rename `kos-example` throughout).

## Package Structure

```text
kos-<name>/
├── .agents/skills/kos-<name>/SKILL.md   # canonical, provider-neutral skill
├── adapters/{claude,codex,gemini}/      # thin per-agent entry points only
├── config/{defaults.yaml,schemas/}      # provider-neutral defaults + schemas
├── docs/{architecture,installation,usage,upgrade,uninstall}.md
├── installer/{install,initialize,upgrade,uninstall}.{ps1,sh}
├── runtime/                             # the actual implementation
├── templates/                           # reusable content templates, if any
├── tests/
├── CHANGELOG.md
├── LICENSE
├── manifest.yaml
├── README.md
└── VERSION
```

Not every lifecycle script needs a working implementation at `v0.1.0` — the
contract (the file existing, at the path `manifest.yaml` declares) matters
more than completeness on day one. Undeclared or missing lifecycle commands
surface as warnings during discovery, not errors.

## The Manifest

Write `manifest.yaml` against `docs/POWER-UP-MANIFEST-SPECIFICATION.md` and
`installer/power-up-manifest.schema.json` in the starter kit. Key
decisions to make explicitly:

- **`id`** — lowercase, hyphenated, and stable for the life of the Power-Up;
  the registry, the workspace folder name, and the KOS environment variable
  convention all key off it.
- **`installation.default_mode`** — almost always `external`. Only declare
  `embedded` support if you have a real reason a user might want the runtime
  inside their vault.
- **`permissions`** — declare every folder scope you read or write. Default
  `canonical_kos_writes.allowed` to `false` unless this Power-Up genuinely
  needs to propose edits to `memory.md`/`handoff.md`/policy files, and if it
  does, `requires_explicit_approval` must stay `true`.

## Keep Adapters Thin

`adapters/claude/`, `adapters/codex/`, `adapters/gemini/` exist only to tell
each agent where the canonical skill is. Business logic, validation,
schemas, and runtime behavior belong in `runtime/` and are referenced from
`.agents/skills/kos-<name>/SKILL.md`, never duplicated per adapter. This
mirrors how the KOS core itself keeps `CLAUDE.md`/`CODEX.md` thin against the
canonical `AGENTS.md`.

## Workspace Modes

Declare which of `embedded-target` / `centralized` your Power-Up supports in
`manifest.yaml` -> `workspace`:

- **`embedded-target`** (default): `<Target Folder>/.kos/power-ups/kos-<name>/`
  per KOS folder it is initialized for — `config.yaml`, `inbox/`, `review/`,
  `approved/`, `rejected/`, `state/`, `README.md` as needed.
- **`centralized`**: one workspace under this Power-Up's own external install
  directory, referencing initialized targets by path instead of duplicating a
  workspace per folder.

Either way, initialization must never duplicate the shared runtime itself —
only the lightweight per-target workspace.

## Implementing `initialize`

`installer/initialize.*` must:

- accept a target KOS folder and verify it exists;
- reject paths outside explicitly approved locations unless the user
  overrides that explicitly;
- preserve existing files, creating only what's missing;
- support safe re-initialization (running it twice is a no-op on already
  correct state);
- support `--dry-run` / `-DryRun` that reports what it would do without
  writing anything;
- leave recording the target in the registry's `initialized_targets` to the
  KOS-side registration flow, or update it itself if you extend the registry
  helpers — either way, never write anywhere in the vault outside the
  workspace you were asked to create.

## Implementing `upgrade`

Check `kos_compatibility` against the target's installed `kosContractVersion`
before changing anything; back up the current manifest/config; preserve
`approved/` (or equivalent) data; run a migration only if this release
declares one; update the registry `version`/`updated_at` only after
validation passes; roll back on failure. See `docs/upgrade.md` in the
template.

## Implementing `uninstall`

Disable first (a registry-side `status: disabled`, not a script action).
Then, on explicit approval: remove the runtime; separately, on separate
explicit approval, offer to clean up initialized-target workspaces. Never
delete canonical KOS files. See `docs/uninstall.md` in the template.

## Security Checklist Before Publishing

- No default read/write scope beyond explicitly declared folders.
- No credentials anywhere in the repository, manifest, or generated
  workspace files that might get committed — read secrets from environment
  variables or OS secret storage.
- `canonical_kos_writes.allowed` is `false` unless genuinely needed, and
  `requires_explicit_approval` stays `true` whenever it is `true`.
- Destructive actions (uninstall, overwrite) require explicit confirmation
  and support a dry-run.
- Generated state, caches, and logs are excluded from your own `.gitignore`
  guidance to consumers (mirror KOS's own exclusion list — see
  `docs/KOS-POWER-UPS.md` -> Context and Token Budget).

## Distribution

The starter kit does not implement a marketplace, license server, or payment
system. It leaves the extension points open: a Power-Up can be a free
open-source repository, a private company package, installed from a local
folder, a Git repository, or a packaged release. Publish it however fits —
the only requirement KOS itself enforces is a valid `manifest.yaml`.
