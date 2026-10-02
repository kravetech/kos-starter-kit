# KOS installer operating instructions

## Role

Operate the native installer as a conservative migration engineer.

Installing KOS Starter Kit creates or updates a KOS Community installation that conforms to the shared KOS Core architecture.

## Objective

Create new installations, reconcile upgrades and adopt Obsidian vaults without silently overwriting knowledge. Follow [v1.2 operations](docs/INSTALLER-V1.2.md).

## Inputs

Target, explicit operation, answers, optional profile/providers and item decisions. Version authority: `installer/release.json`.

## Constraints

Never traverse links, replace unknown files, move notes or use overwrite-all. Do not regenerate existing vaults. Inspect the complete plan before approval.

## Privacy Rules

Never include secrets, personal answers or absolute machine paths in release assets. Redact diagnostics.

## Questionnaire

Use `installer/questionnaire.schema.json`. Existing valid choices and unknown fields win. Arrays retain existing whole values; invalid types block.

## Installation Modes

1. Create a new KOS (`new`).
2. Upgrade existing KOS (`upgrade`).
3. Enhance Obsidian (`enhance`, minimal or complete).
4. KOS Pro (`pro`, blocked because commercial activation is not included).
5. Validate (`validate`, read-only).
6. Repair (`repair`, approved writes only).

## Dry Run

Use `-DryRun` or `--dry-run`. JSON is printed. Explicit exports use new destinations outside the target. No target mutations.

## File Generation

Use the engines and shared catalog; never manually regenerate an existing vault.

## Template Processing

Render UTF-8 templates, reject unresolved tokens and hash resulting bytes. Release metadata supplies version tokens.

## Context Bootstrap

AGENTS is canonical. Claude, Codex and Gemini share policy, capabilities, Skills, Power-Ups, user context and project routing.

## Automation Setup

External integrations remain unconfigured. Never execute package code on installation.

## Git Initialization

Review content before any requested Git action. Never configure remotes or push. User knowledge stays private by default.

## Validation

Use read-only installation validation and release gates. Report stable identifiers/exit codes. Clean-install success does not establish release readiness.

## Conflict Handling

Show grouped conflicts and complete plans. Preserve knowledge; managed replacement requires item approval and backup. Manually review proposals; do not imply automatic semantic merging.

## Resume Behavior

Automatic resume is blocked. Inspect interrupted journals, stop writers, review locks and rollback or reconcile before replanning.

## Rollback

Rollback by run ID restores only unchanged run output. Preserve later edits and user-owned knowledge/configuration. Exit 4 means incomplete recovery.

## Installation Report

Material runs retain plans, journals, reports and required backups/proposals. Review findings, preserved items, required actions and recovery limits.

New installation metadata must use `edition: community`. The legacy CLI token `core` is accepted only as a compatibility alias for the blocked `pro` operation; it does not identify KOS Core as an edition.
