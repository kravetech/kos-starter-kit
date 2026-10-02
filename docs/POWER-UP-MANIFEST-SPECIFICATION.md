# Power-Up Manifest Specification

This describes the legacy YAML format used for read-only discovery. KOS
Community 1.0.0 installs Power-Ups through the immutable `manifest.json`
contract in [PACKAGES-V1.md](PACKAGES-V1.md). YAML discovery does not install
or register a Power-Up.

Every Power-Up ships a `manifest.yaml` at its package root. The authoritative
machine-readable contract is `installer/power-up-manifest.schema.json`
(JSON Schema, draft 2020-12); this document explains it in prose.

## File Format

`manifest.yaml` (and `registry.yaml`/`settings.yaml`) use a **constrained
YAML subset**: block mappings, block sequences (including sequences of
mappings), flow lists (`[a, b]` / `[]`), quoted or bare scalars, and `#`
comments. Flow *mappings* (`{ key: value }`), anchors, tags, and multi-line
scalars are **not** supported by the starter kit's dependency-free reader
(`installer/powerups.py` / `installer/powerups.ps1`). Always write nested
maps in block style.

## Required Fields

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | string | Currently `"1.0"`. |
| `id` | string | Lowercase, hyphenated, matches `^[a-z][a-z0-9-]*$`. Unique across a KOS instance's registry. |
| `name` | string | Human-readable name. |
| `version` | string | Semantic version of the Power-Up itself. |
| `kos_compatibility.minimum_version` | string | Lowest KOS Core contract version this Power-Up supports, compared with `kosContractVersion` in the target's `00 - System/Installation/kos-installation.json` (installations without state fall back to the `ARCHITECTURE.md` `version`). |
| `kos_compatibility.maximum_version` | string or `null` | Optional upper bound. |
| `installation.supported_modes` | array | One or both of `external`, `embedded`. |
| `installation.default_mode` | string | Must be one of `supported_modes`. |
| `agents.canonical_skill` | string | Path to the provider-neutral skill definition, matching `.agents/skills/<id>/SKILL.md`. |
| `permissions.read` | array | Locations this Power-Up may read. |
| `permissions.write` | array | Locations this Power-Up may write. |
| `permissions.canonical_kos_writes.allowed` | boolean | Defaults to `false`. |
| `permissions.canonical_kos_writes.requires_explicit_approval` | boolean | Must be `true` whenever `allowed` is `true`. |
| `lifecycle.install_command` | string | Path to the install script, relative to the Power-Up root. |
| `lifecycle.initialize_command` | string | Path to the initialize script. |
| `lifecycle.upgrade_command` | string | Path to the upgrade script. |
| `lifecycle.uninstall_command` | string | Path to the uninstall script. |

Every `lifecycle` key must be present so tooling can detect the intended
contract, even if the script behind it is a stub — see
`templates/power-up-template/`.

## Optional Fields

`description`, `publisher`, `license`, `kos_compatibility.maximum_version`,
`installation.requires_shared_runtime`, `workspace.supported_modes`,
`workspace.default_mode`, `agents.supported`, `capabilities`,
`dependencies.runtime`, `dependencies.optional`, `lifecycle.repair_command`,
`integrity.checksum_file`, `integrity.signature_file`.

## Validation Rules Enforced by Tooling

`installer/powerups.py` (`validate_manifest_dict`) and
`installer/powerups.ps1` (`Test-KosPowerUpManifest`) apply the same rules:

- **Errors** (invalid discovery candidates): missing/invalid `schema_version`; `id` not
  lowercase-hyphenated; `version` not semver; missing or non-semver
  `kos_compatibility.minimum_version`; a non-null, non-semver
  `maximum_version`; installed KOS version older than `minimum_version` or
  newer than `maximum_version`; empty or invalid `installation.supported_modes`;
  `default_mode` not among `supported_modes`; missing `permissions.read` or
  `permissions.write`; `canonical_kos_writes.allowed: true` without
  `requires_explicit_approval: true`.
- **Warnings** (reported without failing discovery): missing
  `agents.canonical_skill`; any missing `lifecycle.*` command.

Discovery additionally reports, as errors or warnings:

- a duplicate `id` across two candidate directories, or against an
  already-registered `id` (warning: "already registered; discovery will not
  overwrite it");
- a `lifecycle.*` command path that does not exist on disk (warning — the
  file is checked for existence only; it is never executed during discovery).

## Example

```yaml
schema_version: "1.0"

id: kos-lang-extract
name: KOS Lang Extract
description: Extracts structured, source-grounded information from supported documents.
version: 1.0.0
publisher: kravetech
license: Apache-2.0

kos_compatibility:
  minimum_version: 1.0.0
  maximum_version: null

installation:
  supported_modes:
    - external
    - embedded
  default_mode: external
  requires_shared_runtime: true

agents:
  canonical_skill: ".agents/skills/kos-lang-extract/SKILL.md"
  supported:
    - codex
    - claude-code
    - gemini-cli
    - generic-filesystem-agent

capabilities:
  - document-extraction
  - structured-review
  - folder-initialization

permissions:
  read:
    - selected-kos-folders
    - power-up-workspace
  write:
    - power-up-workspace
    - kos-power-up-registry
  canonical_kos_writes:
    allowed: false
    requires_explicit_approval: true

dependencies:
  runtime: []
  optional: []

lifecycle:
  install_command: "installer/install.ps1"
  initialize_command: "installer/initialize.ps1"
  upgrade_command: "installer/upgrade.ps1"
  uninstall_command: "installer/uninstall.ps1"

integrity:
  checksum_file: null
  signature_file: null
```

## Registry Entry Contract

Once approved, a manifest produces a `registry.yaml` entry:

```yaml
schema_version: "1.0"

power_ups:
  - id: kos-lang-extract
    name: KOS Lang Extract
    version: 1.0.0
    status: enabled
    installation_mode: external
    install_path: "${KOS_POWERUPS_HOME}/kos-lang-extract"
    manifest: "manifests/kos-lang-extract.yaml"
    initialized_targets:
      - "01 - Business/Companies/Example Company"
      - "02 - Projects/Active/Example Project"
    installed_at: "2026-08-01T10:00:00Z"
    updated_at: "2026-08-01T10:00:00Z"
```

`status` is `enabled` or `disabled`. `installation_mode` is `external` or
`embedded`. `manifest` is a path relative to `00 - System/Power-Ups/`,
pointing at the locally stored copy of that Power-Up's manifest. The legacy
`register` commands are blocked in v1.2. Review and repackage a candidate
under the immutable package contract before installation.
