# Changelog

## [1.2.0] - Unreleased

- Added a frozen, fingerprinted source-candidate gate and a separate positive client ZIP payload list. The exact client files are staged in a reviewable folder and tested for new installation, legacy upgrade and Obsidian enhancement before any archive is created.
- Added bounded migration link auditing for existing Obsidian wikilinks, embeds and Markdown links. Dry-runs report baseline unresolved links and new basename collisions; newly ambiguous or redirected previously resolved links block apply.
- Aligned legacy Power-Up discovery across Bash/Python and PowerShell as read-only. Removed the unused migration backup flag and require a verified external full-vault snapshot while retaining transaction backups for changed files.
- Clarified independent Starter Kit, Community, Core and Pro version increments: unreleased candidate edits remain under 1.2.0, and later immutable releases follow MAJOR.MINOR.PATCH with separate source history, changelog and artifact hashes.
- Required explicit approval for existing-vault migration even when an answer file and legacy migration switch are supplied; added Pro-vault detection so Community upgrade/enhancement refuses Pro installations and Pro edition state.
- Aligned the Community KOS Core contract stamp with the declared Core 1.0.0 baseline and Pro compatibility major 1. This corrects package compatibility comparisons without enabling a Community-to-Pro transition.
- Added `communityVersion`, the KOS Community edition architecture version, starting at `1.0.0`. It is recorded in `installer/release.json`, installation state, the installation schema and generated `README.md`/`ARCHITECTURE.md`; upgrades reject a Community version downgrade and record the version on older installations.
- Added release-time version drift checks across release metadata, the state template, architecture, changelog, publication guide, root templates and CI; the release archive name now derives from `installer/release.json`.
- Power-Up `kos_compatibility` is now evaluated against the installed `kosContractVersion` instead of the vault's `ARCHITECTURE.md` version, which tracks the Starter Kit.
- Corrected stale architecture release metadata: status, release date and the contract section title.
- Added deterministic reconciliation, ownership, immutable package lifecycle, transaction journals and conservative rollback.
- Added Obsidian adoption, optional Gemini routing, shared registries and a blocked KOS Pro compatibility boundary.
- Removed global overwrite and restricted release packaging to an explicit allowlist.
- Added synthetic migration/security tests and PowerShell/Python golden-plan parity.
- Clarified KOS Starter Kit as the open-source bootstrap distribution for KOS Community and KOS Core as the shared architecture.
- Changed canonical new-install edition metadata from `starter` to `community`, while retaining legacy metadata compatibility.
- Documented KOS Pro as the commercial edition and KOS Enterprise as the planned organizational edition.

## [1.1.0] - Not released separately; included in 1.2.0

### Changed

- Aligned the architecture and both installer engines on version `1.1.0`.
- Hardened installer targets against filesystem roots, home/profile targets, starter-kit ancestors, links/reparse points, and accidental non-empty standard installations.
- Standardized invalid-input exits as code `2` and unexpected failures as code `3`.
- Deferred optional initial commits until validation and report generation complete.
- Added private-by-default Git guidance for generated Knowledge OS repositories.
- Added Apache-2.0 licensing and public-release documentation.
- Strengthened privacy scanning with an ignored local denylist and tracked-file release audit.
- Added Windows and Ubuntu CI with a commit-pinned checkout action, PowerShell/Python validation, installation tests, ShellCheck, and release auditing.
- Sanitized the pre-existing `ARCHITECTURE-updated.md` and promoted it to the canonical root `ARCHITECTURE.md`.
- Replaced reference-system branding with neutral product naming.
- Replaced absolute machine paths with `<reference-kos>`, `<starter-kit-root>`, and `<installation-target>` placeholders.
- Replaced the live-vault structure section with the structure the installer generates.
- Removed dangling wikilinks that pointed into the private reference vault.

### Removed

- `ARCHITECTURE-updated.md` (superseded by root `ARCHITECTURE.md`).

### Security

- Generated `.gitignore` now excludes installation state, installation reports, and migration backups.
- Release audit rejects tracked answers, local configuration, local denylist, logs, build output, and test output.

## [1.0.0] - 2026-07-28

### Added

- Private Markdown-driven Knowledge OS starter-kit installer.
- Standard numbered domain architecture and neutral templates.
- Interactive, JSON, default, dry-run, resume, custom, and migration workflows.
- Cross-platform initialization, installation, validation, privacy, and manifest scripts.
- Synthetic test installation and validation evidence.
