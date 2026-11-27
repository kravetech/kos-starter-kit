# Changelog

Starting with 1.3.1, the Community product, installer and distribution use one release number. Earlier bracketed headings identify distribution versions. Distribution `1.3.0` shipped KOS Community `1.1.0`.

## KOS Community 1.4.0

Release date: 2026-11-27

Distribution tag `v1.4.0`. Installer asset `kos-community-v1.4.0.zip`. KOS Core contract `1.0.0`.

- Guided setup accepts the official Community repository URL or a local release ZIP, verifies the stable release, and identifies the vault before writing.
- Fresh installs preview settings once. Updates show intervening release changes, propose backup and rehearsal locations, and request separate approval for the original vault.
- Update rehearsals check extension preservation and internal links. Each material run reports validation, actual writes, proposals, and recovery evidence.
- One copyable prompt handles installs and updates in Codex, Claude Code and Gemini CLI. The optional `kos-community-fix` skill accepts the official repository URL or a local Community release ZIP. Use `--check` to diagnose a recognized vault and list existing link or extension issues without applying changes.

## KOS Community 1.3.1

Release date: 2026-11-26

Distribution tag `v1.3.1`. KOS Core contract `1.0.0`.

- Download `kos-community-v1.3.1.zip` for this release. Older vaults with separate Community and installer versions keep their upgrade history. Historical downloads keep their original filenames.
- Installation and upgrade reports identify the Community version first. The installation record retains separate fields for reading older vaults.
- Upgrades preserve existing changelog history and offer a separate upgrade entry for review.
- Fresh installations use the computer’s local setup date unless the owner supplies a date. Upgrades and repairs preserve a known original installation date. The upgrade changelog entry uses the local day of the upgrade.
- Upgrades can recover the original installation date from an unchanged installer-created README with a multiline description. Repeating an enhancement with no new answers preserves the vault’s existing personalization and privacy settings.
- Legacy Power-Up discovery checks the recorded Core contract or the explicit Core contract in vault architecture. If neither identifies the contract, discovery reports that compatibility could not be checked.
- The Power-Up guides distinguish the v1 package format from the current installer. The upgrade guide identifies the distribution field used by managed vaults and the installer field used by legacy vaults.
- When original setup answers are unavailable, the installer can propose recognized version changes while preserving the vault’s identity and custom text. Validation reports identify each modified file and the severity of the finding.
- Downgrade checks cover each previously recorded version. Package compatibility uses the target vault’s Core contract.
- Guided setup checks the agent and answers file before launch and blocks automatic resume. Rollback checks approval, the run ID and export paths before changing the vault. Both installers can export validation findings and final rollback status as JSON and Markdown.
- The manifest utility now inventories the files in the customer ZIP. Setup flags that could never change scripts, placeholder files or external integrations are checked explicitly. Legacy Power-Up guides and commands now point authors to the installable package format, and retired registration returns exit code 2 on both shells.

## [1.3.0] — KOS Community 1.1.0

- Upgrade and repair now stop before writing when a legacy vault has no recorded installer version. Both installer implementations preserve the vault for manual review. The revised setup guide explains the optional editor, the original-version check and how to rehearse upgrades on a copy.
- Added a reusable meeting template and a worked example covering decisions, owners, dates and open questions. Updated the extension guides with the v1 authoring route, the three supported workflow clients, Community support and the distinction between current workflow offers and the legacy Pro distribution.

- Added the free Project Action List Power-Up and its versioned shared Skill. The customer ZIP includes a meeting-note fixture and a guide to reviewing permissions, activating the example for a project, saving a cited result, updating, rolling back and uninstalling.

- Community 1.1.0 adds draft initialization, review and explicit approval for the selected project's memory and handoff. When an approved note changes, the checker identifies the file. Review loads the last approved local snapshot and shows the changes before reapproval.
- Inspect selected Markdown sources and search them with line references, work limits and read-only commands. Installation records the selected folder restrictions. Existing project notes remain under owner control.
- Approval in Git worktrees verifies the snapshot and temporary file are ignored before storing original note bytes. Windows uses the on-disk project name for review identity.
- Review and search accept common Obsidian properties and apply the receipt's classification to the exact approved memory and handoff revisions. Windows source selections accept native path separators.
- Project checks distinguish pair approval from pending adoption of upgraded routing instructions and identify which proposal to review. Blocked initialization and review return exit code 2.

## [1.2.0] - 2026-10-02

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
