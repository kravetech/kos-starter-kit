# Changelog

## [Unreleased]

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
