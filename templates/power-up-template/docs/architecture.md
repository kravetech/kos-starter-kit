# Architecture

<Describe what this Power-Up does, its major components under `runtime/`,
and how it fits into the standard Power-Up lifecycle: Discover -> Validate ->
Install -> Register -> Initialize -> Use -> Disable/Upgrade/Repair -> Uninstall.>

## Workspace Modes

- `embedded-target`: `<Target Folder>/.kos/power-ups/kos-example/` per initialized folder.
- `centralized`: a single workspace under this Power-Up's own install directory.

## Boundaries

- Runs entirely outside the KOS vault (external installation mode) unless the
  user explicitly opts into embedded installation.
- Never edits canonical KOS files unless `manifest.yaml` declares
  `permissions.canonical_kos_writes.allowed: true`, and even then only with
  explicit approval per change.
