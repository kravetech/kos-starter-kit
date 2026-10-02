# KOS Starter Kit 1.2 operation guide

`installer/release.json` is the authoritative version source. Starter Kit and
installer are 1.2.0; the KOS Community edition is 1.0.0; the KOS contract is
1.0.0; schema and adapter versions are 1.0.0. Package versions are independent. New installations use
`edition: community`. This is a KOS Starter Kit release for KOS Community, not a
KOS Core or KOS Pro release.

## Commands and approvals

PowerShell 5.1/7 remains native and requires no Python. Bash uses Python 3.10+.
Use `install.ps1 -Operation <operation> -Target <vault>` or
`./install.sh --operation <operation> --target <vault>`. The operation names are
`new`, `upgrade`, `enhance`, `pro`, `validate`, `repair`, and `rollback`. The
legacy `core` token remains accepted as an alias for the blocked `pro` operation;
it does not identify KOS Core as an edition.

Start with `-DryRun` / `--dry-run`. Plans are JSON on stdout. Add
`-PlanOutput <file>` / `--plan-output <file>` and `-Report <file>` / `--report
<file>` to export to a new destination outside the target. Neither dry-run nor
validation creates files in the vault. Output destinations are never overwritten.
Apply the reviewed operation with `-Approve` / `--approve`.
An existing-vault upgrade, enhancement, or repair always requires this explicit
approval (or confirmation in the interactive review). An answer file and the
legacy migration switch select inputs; they do not authorize writes.

Existing answer-file invocations still create a new installation, but a nonempty
target is refused. The old `Migration` switch maps to upgrade or enhancement and
never authorizes overwrite. `AllowOverwrite` and `allow_overwrite: true` are
rejected. Interrupted runs require journal review and rollback before replanning;
`Resume` no longer repeats unknown writes.

## Modes and migration

| Mode | Implemented behavior |
| --- | --- |
| New | Requires missing or empty directory; creates selected foundations and templates |
| Upgrade | Reconciles managed KOS and legacy 1.0.0/1.1.0 installations |
| Enhance | Requires an Obsidian vault; defaults to minimal profile; retains notes and `.obsidian` |
| Pro | Emits a blocked plan; KOS Pro code and commercial activation are not included |
| Validate | Reads state, hashes, registries, adapter routes, structure, privacy and capability paths |
| Repair | Reconciles missing foundations; does not reinstall optional packages |

KOS Pro vaults are not Community migration sources. The Community installer
refuses them even when the legacy migration switch is used. A supported
Community-to-Pro transition belongs to a future Pro installer.

Enhancement profiles are `minimal` and `complete` (`-Mode` / `--mode`). Minimal
creates System, Inbox, Templates, Archive and shared routing without every domain.
Complete creates missing numbered domains. Proposed folder mappings retain
content in place. Nothing moves notes. Existing profile and provider choices win
on upgrades. Unknown configuration keys survive object merges; arrays, including
empty arrays, are whole user choices. Type conflicts block changes.

Legacy installer state supplies version evidence, not overwrite authority. Exact
current-template matches can be adopted; all uncertain legacy assets remain
user-owned. The release includes provenance-tagged public 1.1.0 managed-template snapshots; exact rendered hashes (including known legacy UTF-8/BOM and line-ending variants) prove ownership. No unsupported 1.0.0 historical provenance is invented. Modified files are preserved and receive
proposals. No downgrade is supported.

## Plans and conflicts

Plans classify missing, identical, compatible existing, older managed,
user-modified, path, semantic, version, configuration, dependency, security,
reserved-path, unknown and blocked conditions. The action vocabulary includes
create, unchanged, safe update, preserve, adopt, propose, merge, skip and block.
Package uninstall is an explicitly approved removal of verified package files.

Filename equality is not identity. Content hashes, ownership records, capability
IDs, declared implementation paths and package identity are separate evidence.
Alternate capability paths need explicit adoption. Suspected alternate Skill or
Power-Up registries block creation pending review. Stale capability declarations
are findings, not proof that an implementation exists.

Use a decisions JSON file with relative paths and `keep`, `skip`, `propose`,
`adopt`, or `replace`, then pass `-Decisions` / `--decisions`. Replacement applies
only to previously tracked managed or managed-customizable files. User knowledge
cannot be replaced through this interface. Python and PowerShell also offer
item review in their interactive menus. Guided
text merging and side-by-side activation of conflicting capability IDs are not
implemented. Edit a proposal manually and revalidate.

The example answer file contains the supported conservative conflict policy.
Unsupported policies are rejected. There is no global overwrite setting.

## Ownership and transaction recovery

Installation state is `00 - System/Installation/kos-installation.json`. Assets
record relative paths, component IDs, ownership, source version, installed hashes
and last action; plans also carry assessed current hashes. Ownership classes are
managed, managed-customizable, user-owned, generated, runtime and extension-owned.
Metadata has no machine root, answer-file path or raw entitlement secret.

Each material operation creates `Installation/Runs/<run-id>/plan.json`,
`journal.json`, `report.md`, backups of changed files and proposals. An exclusive
operation lock prevents cooperating installers from running concurrently. Intent
is flushed before backup and each destination write. Hashes are checked before
writes and before registry activation. Journals and replacements use atomic
rename. The initial administrative directories/lock precede the journal; they
never replace existing user files.

Before upgrading or enhancing an existing vault, create and verify a complete
snapshot outside the target. Transaction backups cover only files the installer
changes; they are not a full-vault backup. The old `backup_before_migration`
answer is rejected because it never controlled a complete backup operation.

Rollback uses `-Operation rollback -RunId <id> -Approve` or the equivalent Python
options. It restores only this run's changes when current output still matches.
Post-install edits and newly created user-owned configuration/knowledge remain.
Incomplete recovery returns **4** and preserves metadata instead of pretending
the vault is fully restored. Empty directory skeletons and run evidence remain.
Uninstall similarly retains configuration, state, reports and generated data.

For a crash leaving `operation.lock`, stop the original writer, inspect the named
journal and backups, then remove only that lock after confirming no process is
active. Run a rollback dry-run before approving recovery. There is deliberately
no automatic stale-lock deletion or automatic resume.

## Links and concurrency limits

Inventory uses entry inspection before descent. Junctions, symlinks and reparse
points are recorded as user-owned entries and preserved, never traversed.
Only writes through or replacing those entries block. Target ancestors must not
be links. Archive traversal, absolute paths, alternate data streams, device
names, case-colliding entries and archive links are rejected.

Upgrade, enhance and repair dry-runs include a bounded `linkAudit`. It checks
existing Markdown wikilinks, embeds and Markdown links against the current file
set and the files the plan would add. Preexisting unresolved or ambiguous links
and new basename collisions are reported for review. A link that resolves to
one existing file but would resolve differently after installation blocks the
plan with `LINK_RESOLUTION_REGRESSION`. The installer does not rewrite existing
notes to resolve a conflict; qualify the affected link path in a backed-up test
vault, then replan. Existing note and attachment bytes remain untouched.

The audit refuses vaults above 20,000 files, 10,000 Markdown files, 1 MiB per
Markdown file, or 50,000 scanned references. It skips fenced and inline code,
external URLs and anchor-only links. It is a conservative file-target check,
not a full Obsidian parser: aliases, heading/block targets, plugin-specific
links, reference-style Markdown links and runtime plugin behavior still require
manual review in Obsidian. Use [Obsidian's internal-link guidance](https://help.obsidian.md/links)
when reviewing path-qualified links.

Close editors/sync clients during an approved operation. Hash guards detect
ordinary concurrent changes, but this is not a filesystem sandbox against a
hostile local process replacing directories between a check and an OS call.

## Gemini and shared routing

Set `installation.providers` to any subset of `codex`, `claude`, `gemini` in the
answer file. Gemini is optional and requires no executable for file installation.
All three thin adapters route through `AGENTS.md`, `CONTEXT-POLICY.md`, the same
capability registry, Skills registry, Power-Up registry, `me.md`, and project
context rules. Provider CLIs are only needed when launching an interactive agent.

## Exit codes and rules

| Exit | Meaning |
| --- | --- |
| 0 | Valid plan, successful approved operation, or unchanged result |
| 2 | Invalid input, blocked/conflicting plan, missing approval, validation failure |
| 3 | Unexpected I/O failure; journal inspection required |
| 4 | Incomplete rollback; retained changes require review |

Stable findings include `META_MISSING`, `ASSET_MISSING`, `ASSET_MODIFIED`,
`CAPABILITY_STALE`, `CAPABILITY_STATE_MISMATCH`, `PACKAGE_INTEGRITY`,
`ADAPTER_ROUTING`, `LINK_PRESERVED_NOT_TRAVERSED`, `SECRET_EXPOSURE`,
`MACHINE_PATH`, `STRUCTURE_MISSING`, and `VALIDATION_UNSAFE_OR_INVALID_METADATA`.
Diagnostics never include matched secret values. Secret scanning is heuristic;
it does not establish that a vault is safe to publish. Arbitrary Markdown link
resolution outside the bounded `linkAudit` and full validation of foreign
configuration schemas remain limited.

Git initialization is optional and appears as a journaled post-action. Rollback retains its runtime directory. Initial commits require manual content review; `create_initial_commit: true` is blocked. Synthetic examples, lean and custom module choices remain supported.

## Edition compatibility

KOS Core is the shared architecture and compatibility contract. KOS Community is
the open-source edition installed by this repository. `starter` and `core` remain
readable only as legacy edition identifiers and are canonicalized to `community`
and `pro` during reconciliation. KOS Enterprise is planned and is not installed
by this release.
