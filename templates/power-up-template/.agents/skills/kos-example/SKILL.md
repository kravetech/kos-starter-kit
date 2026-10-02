# kos-example

## Role

Canonical, provider-neutral skill definition for the `kos-example` Power-Up.
Every adapter under `adapters/` (Claude, Codex, Gemini, or any other
filesystem-capable agent) points here instead of duplicating this content.

## When To Load This File

Only when this specific Power-Up is being invoked for a task. Do not load it
during routine KOS bootstrap, and do not load it just because the Power-Up is
registered in `00 - System/Power-Ups/registry.yaml` — registration only means
it is *available*.

## Capabilities

- <example-capability>

## Inputs

- The KOS folder(s) this Power-Up was initialized for (see
  `00 - System/Power-Ups/registry.yaml` -> `initialized_targets` for this
  Power-Up's id).
- Its own workspace (`<target>/.kos/power-ups/kos-example/` in embedded-target
  mode, or a centralized workspace under this Power-Up's install directory).

## Constraints

- Read only the KOS folders this Power-Up was explicitly initialized for, plus
  its own workspace. Do not scan the whole vault.
- Never write to canonical KOS files (`memory.md`, `handoff.md`, policies,
  requirements) unless `manifest.yaml` declares
  `permissions.canonical_kos_writes.allowed: true`, and even then only with
  explicit user approval for that specific change.
- Treat generated state, caches, and logs as excluded from routine context.
- Review-first: write extracted or generated content to a review location
  before anything is treated as approved.

## Outputs

- <describe what this Power-Up produces and where>
