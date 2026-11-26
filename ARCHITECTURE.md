---
title: KOS Community Installer Architecture
type: architecture
status: active
area: system
version: 1.3.1
community_version: 1.3.1
kos_contract_version: 1.0.0
author: Kraven
created: 2026-07-15
updated: 2026-11-26
tags:
  - knowledge-os
  - architecture
  - starter-kit
  - token-optimization
aliases:
  - KOS Starter Kit Architecture
related:
  - "[[README]]"
  - "[[KOS-INSTALLER]]"
---

# KOS Community Installer Architecture

## Release

| Field | Value |
| --- | --- |
| Product | KOS Community |
| Community version | `1.3.1` |
| Installer version | `1.3.1` |
| Distribution version | `v1.3.1` |
| KOS Core contract | `1.0.0` |
| Author | `Kraven` |
| Release status | Repository tags and GitHub Releases record published state |
| Release date | See the corresponding GitHub Release |

## Purpose

KOS Community is the free, open-source edition of KOS. It stores notes, projects and operating records as portable Markdown. Users can open a workspace in Obsidian or another Markdown editor. This document describes the Community installer and the shared KOS Core contract it implements.

## Product Hierarchy

| Layer | Meaning |
| --- | --- |
| KOS Core | Shared technical architecture and compatibility contract; not an edition |
| KOS Community | Free and open-source edition |
| KOS Community installer distribution | Packages the installer, templates, scripts and documentation. The customer ZIP uses the Community version. Distribution tags and the historical `starterKitVersion` metadata field identify the distribution version. |
| Official commercial workflows | Individually purchased Power-Ups or eligible packages under the combined subscription. Both run on the Community host. |
| Legacy Pro 1.1.0 | Separately licensed distribution retained for compatibility with existing installations |
| KOS Enterprise | Planned organizational and multi-user edition |

KOS Community and its installer are distributed under Apache-2.0. Previously released Starter Kit versions retain their original license terms.

The architecture separates:

- system rules and operational state;
- business, project, personal, hobby, and knowledge domains;
- rapid capture from curated knowledge;
- reusable templates from live records;
- active information from archived history;
- durable AI context from temporary execution state.

## Architecture Principles

1. Markdown is the canonical, portable data format. Templates support Obsidian conventions.
2. Top-level numeric prefixes provide stable navigation and ordering.
3. Durable knowledge and temporary execution state remain separate.
4. Active or sufficiently complex AI-ready projects contain `memory.md` and `handoff.md`; empty or simple folders do not receive them automatically.
5. Templates define repeatable structures without requiring Obsidian plugins.
6. Historical context is archived rather than deleted or retained in active files.
7. Credentials, secrets, and sensitive personal or company data are never committed.
8. External-source configuration is provider-neutral and local state is replaceable.
9. AI agents use progressive, task-specific context loading instead of broad recursive scans.
10. The reference KOS, installer source, test output and user installation occupy separate locations.

<a id="starter-kit-project-boundary"></a>

## Installer Project Boundary

The KOS installer and reusable templates are developed outside any live reference KOS.

| Purpose | Location | Access rule |
| --- | --- | --- |
| Live reference KOS | `<reference-kos>` | Read-only during installer development |
| Installer project | `<installer-root>` | Contains the installer source, templates, scripts and reports |
| Disposable validation output | `<installer-root>/test-output` | Holds test installations |
| Final generated KOS | User-selected during installation | Must never default to the live reference KOS |

When version control is enabled, the installer project uses a Git repository separate from the reference KOS.

Local machine paths belong only in an ignored file such as `installer/local-config.json`. Reusable templates and this document must use placeholders and remain machine-independent.

### Required Isolation Checks

Before an installer or builder writes files, it must:

1. Resolve the reference KOS, installer source, test output and installation target paths.
2. Confirm that the installer source is outside the live KOS.
3. Confirm that the installation target is not the live KOS.
4. Stop when any output path resolves inside the reference KOS.
5. Write analysis reports, templates, scripts, logs and test files only under the installer project.
6. Treat the live KOS as an architectural reference, not as distributable content.

<a id="starter-kit-repository-structure"></a>

## Installer Repository Structure

```text
<installer-root>/
├── README.md
├── ARCHITECTURE.md
├── INSTALL.md
├── INITIALIZE.md
├── KOS-INSTALLER.md
├── QUESTIONNAIRE.md
├── MANIFEST.md
├── PRIVACY.md
├── LICENSE-NOTICE.md
├── CHANGELOG.md
├── install.ps1
├── install.sh
├── initialize.ps1
├── initialize.sh
├── installer/
│   ├── answers.example.json
│   ├── local-config.example.json
│   ├── questionnaire.schema.json
│   ├── structure.manifest.json
│   ├── installer-state.template.json
│   ├── validation-checklist.md
│   └── migration-guide.md
├── templates/
│   ├── root/
│   ├── system/
│   ├── projects/
│   ├── business/
│   ├── personal/
│   ├── hobbies/
│   ├── knowledge/
│   ├── inbox/
│   ├── daily/
│   ├── automations/
│   ├── archive/
│   └── attachments/
├── scripts/
│   ├── tooling.py
│   ├── generate-manifest.ps1
│   ├── generate-manifest.sh
│   ├── privacy-scan.ps1
│   ├── privacy-scan.sh
│   ├── validate-installation.ps1
│   ├── validate-installation.sh
│   ├── validate-starter-kit.ps1
│   └── validate-starter-kit.sh
├── examples/
├── reports/
├── build/
├── logs/
└── test-output/
```

The installer may distribute the architecture, policies, workflows and neutral templates of KOS. It must exclude private notes, business records, personal information, credentials, linked-source inventories, generated reports, absolute paths and existing project content.

## Installer Execution Model

`KOS-INSTALLER.md` is the tool-neutral installation specification. The initialization scripts can launch Codex CLI, Claude Code or Gemini CLI. The direct PowerShell and Bash installers work independently of these clients.

The initialization flow is:

```text
initialize.ps1 or initialize.sh
        ↓
Select an installed CLI
        ↓
Read KOS-INSTALLER.md
        ↓
Run questionnaire or load answers JSON
        ↓
Produce dry-run manifest
        ↓
Generate the selected KOS structure
        ↓
Validate privacy, structure, and bootstrap rules
        ↓
Write installation report
```

The KOS Community installer supports interactive and answer-file input, dry-run plans,
new installations, supported Community upgrades and additive Obsidian enhancement
with selected profiles. Existing-vault writes require explicit approval.
Customized files are preserved or proposed for review; global overwrite and
automatic resume are rejected. Pro vaults are not Community migration targets.
Existing-vault plans audit common Obsidian wikilinks, embeds and Markdown links
against files the installer would add. A newly ambiguous or redirected resolved
link blocks apply. The audit is bounded and does not replace an in-app Obsidian
review. A full vault snapshot must be verified outside the target before an
upgrade or enhancement; transaction backups cover only changed files.

## Token-Efficient Bootstrap

AI agents must not load the entire vault at startup. The default normal-task bootstrap is limited to:

```text
AGENTS.md
me.md
memory.md
handoff.md
```

For quick tasks, load only `AGENTS.md` and `me.md` unless additional context is genuinely required.

Files and folders excluded from automatic bootstrap include:

- `ARCHITECTURE.md`;
- `DESIGN.md`;
- `PRODUCT.md`;
- `CHANGELOG.md`;
- `Schedule.md`;
- `00 - System/Reports/`;
- `00 - System/State/Linked Sources/`;
- linked-source inventories;
- generated JSON files;
- attachment folders;
- daily-note history;
- entire project or business directories.

### Progressive Context Loading

Agents follow this sequence:

1. Classify the task.
2. Load the smallest context bundle.
3. Inspect MOCs, indexes, filenames, or headings.
4. Read only directly relevant files or ranges.
5. Stop loading once enough context is available.

Recommended size controls:

| Control | Default |
| --- | --- |
| Large-file warning | 20 KB |
| Large-file threshold | 50 KB |
| Very-large-file threshold | 200 KB |
| Root `memory.md` target | Below 3,000 tokens |
| Root `memory.md` review threshold | 4,000 tokens |
| Root `memory.md` hard warning | 6,000 tokens |
| Root `handoff.md` target | Below 2,000 tokens |

Large files are searched or read by relevant section rather than injected in full. Generated linked-source inventories are never loaded automatically.

`AGENTS.md` owns canonical shared behavior. `CLAUDE.md` and `CODEX.md` remain thin adapters and must not duplicate the full shared policy.

## Generated KOS Structure

This is the structure the installer produces. Domain subfolders below the numbered top level are defaults and may be extended by the user after installation.

```text
<installation-target>/
├── 00 - System/                         # KOS control plane and documentation
│   ├── AI/                              # Agent operating procedure and rules
│   ├── Automations/                     # Manual automation registry
│   ├── Config/                          # Provider-neutral system configuration
│   ├── Installation/                    # Installer state and installation report
│   ├── Linked Sources/                  # External-source registration
│   ├── Reports/                         # Generated operational reports
│   ├── State/                           # Local runtime and integration state
│   ├── Archive-Policy.md
│   ├── Home.md                          # Primary vault navigation hub
│   ├── Metadata-Standards.md
│   └── Naming-Conventions.md
├── 01 - Business/                       # Business operating knowledge
│   ├── Clients/
│   ├── Companies/
│   ├── Meetings/
│   ├── Operations/
│   ├── People/
│   ├── Products/
│   ├── Strategy/
│   └── Business-MOC.md
├── 02 - Projects/                       # Initiative lifecycle management
│   ├── Active/
│   │   └── <Project>/
│   │       ├── docs/
│   │       │   ├── decisions/
│   │       │   └── history/
│   │       │       ├── decisions/
│   │       │       └── handoffs/
│   │       ├── architecture.md
│   │       ├── backlog.md
│   │       ├── changelog.md
│   │       ├── handoff.md               # Current execution state (required)
│   │       ├── memory.md                # Durable approved context (required)
│   │       ├── README.md
│   │       ├── requirements.md
│   │       └── roadmap.md
│   ├── Archive/
│   ├── Completed/
│   ├── Incubating/
│   ├── On-Hold/
│   └── Projects-MOC.md
├── 03 - Personal/                       # Personal operating context
│   ├── Finance/
│   ├── Goals/
│   ├── Health/
│   ├── Learning/
│   ├── Life-Admin/
│   └── Personal-MOC.md
├── 04 - Hobbies/                        # Interests and creative pursuits
│   ├── Content-Creation/
│   ├── Interests/
│   └── Hobbies-MOC.md
├── 05 - Knowledge/                      # Curated durable knowledge
│   ├── AI/
│   ├── Architecture/
│   ├── Business/
│   ├── DevOps/
│   ├── Product-Design/
│   ├── References/
│   ├── Research/
│   ├── Software-Development/
│   └── Knowledge-MOC.md
├── 06 - Inbox/                          # Capture and processing queue
│   ├── Imports/
│   ├── Quick-Notes/
│   ├── Unprocessed/
│   └── Inbox.md
├── 07 - Daily/                          # Time-based operating rhythm
│   ├── Annual-Reviews/
│   ├── Daily-Notes/
│   ├── Monthly-Reviews/
│   └── Weekly-Reviews/
├── 08 - Templates/                      # Reusable, plugin-independent assets
│   ├── Business/
│   ├── Decisions/
│   ├── General/
│   ├── Knowledge/
│   ├── Meetings/
│   ├── Project/
│   │   └── Project-Folder-Template/     # Canonical AI-ready project scaffold
│   └── Reviews/
├── 09 - Attachments/                    # Non-Markdown assets
│   ├── Documents/
│   ├── Exports/
│   ├── Images/
│   └── Temporary/
├── 99 - Archive/                        # Inactive historical material
│   ├── Knowledge/
│   ├── Meetings/
│   ├── Projects/
│   └── System/
├── AGENTS.md                            # Canonical agent router
├── ARCHITECTURE.md                      # Versioned architecture baseline
├── CLAUDE.md                            # Thin Claude adapter
├── CODEX.md                             # Thin Codex adapter
├── CONTEXT-POLICY.md
├── TOKEN-OPTIMIZATION.md
├── handoff.md                           # KOS-level current execution state
├── me.md                                # Working profile
├── memory.md                            # KOS-level durable context
└── README.md                            # Entry point
```

Empty folders are intentional. They preserve the information architecture before content exists.

## Information Lifecycle

```text
Capture → Process → Connect → Apply → Review → Archive
   │          │          │         │         │
Inbox     Domain area  Links    Projects   99 - Archive
```

| Information type | Canonical destination |
| --- | --- |
| Unprocessed idea or input | `06 - Inbox` |
| Active initiative | `02 - Projects/Active` |
| Durable technical or research knowledge | `05 - Knowledge` |
| Business operations and organizational context | `01 - Business` |
| Personal planning and records | `03 - Personal` |
| Hobbies and creative work | `04 - Hobbies` |
| Periodic notes and reviews | `07 - Daily` |
| Reusable content structures | `08 - Templates` |
| Binary files and exports | `09 - Attachments` |
| Completed, obsolete, or inactive material | `99 - Archive` |

## AI Context Model

Every AI-ready project uses two mandatory context files:

| File | Responsibility |
| --- | --- |
| `memory.md` | Durable, reviewed project knowledge, decisions, constraints, and intent |
| `handoff.md` | Current work state, next actions, blockers, and gaps between intent and implementation |

Running code remains the source of truth for implementation reality. `memory.md` represents approved intent; `handoff.md` explains the current transition between the two.

## Community Power-Up invocation

Project Action List uses the v1 local package engine. The Power-Up declares an exact Skill dependency. Its binding identifies the Skill entrypoint and SHA-256 digest. The kit command verifies both installed packages, project activation, context approval and selected sources before returning the shared instructions and cited input. It rechecks that state before saving a new result in the project's Results folder. Gemini, Claude and Codex use the same binding. A provider name in a local run records the selected route. Live provider qualification requires a separate observed client invocation.

The Power-Up and Skill each start at 1.0.0 and carry their own version history. The example first shipped with KOS Community 1.1.0 and installer 1.3.0.

## Versioning Policy

KOS uses [Semantic Versioning](https://semver.org/) for public releases:

```text
MAJOR.MINOR.PATCH
```

| Increment | Use when |
| --- | --- |
| `MAJOR` | The folder contract, required project files, metadata contract, or core workflow changes incompatibly |
| `MINOR` | A backward-compatible domain, template, automation, or workflow capability is added |
| `PATCH` | Documentation, template, script, or structure defects are corrected without changing the public contract |

### Version lines

`installer/release.json` defines the Community release and the contracts it supports. From 1.3.1 onward, the Community product, installer and distribution advance together. A release that changes only documentation or installer behavior also receives a new Community version.

| Field | Tracks | Increment when |
| --- | --- | --- |
| `communityVersion` | The KOS Community product release | Each release uses the MAJOR/MINOR/PATCH rules above |
| `installerVersion` | The installer delivered with that release | Set to the Community release number |
| `starterKitVersion` | The distributed installer, templates, scripts and documentation | Set to the Community release number |
| `kosContractVersion` | The shared KOS Core compatibility contract that Community conforms to | Community adopts a new contract published by KOS Core |
| `schemaVersion` | Machine-readable state, plan and manifest schemas | A schema changes shape |
| `adapterVersion` | Provider adapter files for Codex, Claude and Gemini | Adapter content changes |

Every installed vault records `edition`, `communityVersion`, `starterKitVersion`, `installerVersion` and `kosContractVersion` in `00 - System/Installation/kos-installation.json`. The fields retain their original meanings, so upgrades can read and check older releases whose numbers differed. The generated README and architecture document lead with the Community version. The architecture front matter preserves the distribution number in its existing `version` field. `python scripts/release.py` checks the current release metadata and documentation.

For an unpublished candidate, record notable changes under its unreleased changelog heading. Published artifacts are immutable. Use a PATCH for a compatible fix, a MINOR for a compatible feature, or a MAJOR for an incompatible contract change. Git history records source changes. `CHANGELOG.md` records customer-visible changes, and the release archive hash identifies the distributed bytes. KOS Pro has its own product version and changelog.

### Tags

The GitHub release title names KOS Community and its release number. Its annotated Git tag uses `vMAJOR.MINOR.PATCH` and its customer ZIP uses `kos-community-vMAJOR.MINOR.PATCH.zip`. Earlier tags and filenames retain their historical meanings. See the [publication procedure](PUBLICATION.md).

Each release should:

1. Update the version and date in this document.
2. Record user-visible changes in a root `CHANGELOG.md`.
3. Validate templates and initialization scripts against a clean vault.
4. Confirm that private data, generated state, and credentials are excluded.
5. After exact artifact review and owner authorization, create an annotated Git tag matching the distribution version.

## Distribution and Publication Boundary

The KOS Community installer source is prepared for public distribution under Apache-2.0. Publication requires the review in `PUBLICATION.md`, including privacy validation of the exact staged Git content. The release tools freeze the source, stage the customer files in a separate folder and test installations from that folder. The customer ZIP contains the tested installer files. Maintainer procedures and test sources stay in the repository. Generated Knowledge OS instances are private by default. The following paths require sanitization or exclusion from any public release:

| Path or content | Recommendation |
| --- | --- |
| `.obsidian/` | Include only intentionally supported, portable workspace settings |
| `.agents/` and `.codex-staging/` | Exclude local AI tooling and staging state |
| `00 - System/State/` | Exclude runtime state; publish an example schema if needed |
| `00 - System/Reports/` | Exclude generated and potentially sensitive reports |
| `01 - Business/` | Ship structural placeholders or synthetic examples only |
| `02 - Projects/Active/` | Review each project independently before inclusion |
| `03 - Personal/` | Exclude personal records; retain empty directory structure only |
| `09 - Attachments/` | Exclude private and oversized assets by default |
| Root operational notes | Review `memory.md`, `handoff.md`, schedules, and other local context before release |
| Linked-source configuration | Remove machine paths, identifiers, tokens, and provider-specific private values |
| Installer `logs/`, `build/`, `test-output/` | Exclude from Git and release archives |
| Absolute machine paths in any document | Replace with placeholders such as `<installer-root>` |

## Community Architecture Contract

Community 1.1.0 introduced a local project context command. Approval binds the exact memory and handoff to the selected project. Retrieval takes an explicit list of Markdown sources, applies the installed access rules and returns bounded, line-referenced results. See [Project context](docs/PROJECT-CONTEXT.md).

KOS Community `1.0.0` established the following baseline on KOS Core contract `1.0.0`. It shipped as Starter Kit distribution `v1.2.0`.

- numbered top-level domains from `00` through `09`, plus `99 - Archive`;
- Markdown-first, Obsidian-compatible storage;
- `memory.md` and `handoff.md` as the minimum AI-ready project contract;
- project lifecycle states under `02 - Projects`;
- plugin-independent templates under `08 - Templates`;
- archive-over-delete operating behavior;
- no credentials or secrets in the vault;
- separate locations for the reference KOS and the installer project;
- Markdown-driven installation through Codex or Claude;
- progressive context loading and thin tool adapters.

The shared Core baseline is 1.0.0. Community records it as `kosContractVersion: 1.0.0`. Legacy Pro 1.1.0 records Core `1.0.0` and the compatibility major as `core_contract_version: 1`. Each distribution handles its own maintenance. The Community installer blocks conversion to legacy Pro and refuses a vault with a newer Core contract. Current commercial workflows use separately licensed Power-Ups on the Community host.

Changes that break these guarantees require a new major Community version.

## Installer version contract

`installer/release.json` records the Community release number for the product, installer and distribution. Package compatibility uses the separately versioned KOS Core contract. The [Community operation guide](docs/INSTALLER-V1.2.md) covers installation and recovery. The [package guide](docs/PACKAGES-V1.md) describes package compatibility.
