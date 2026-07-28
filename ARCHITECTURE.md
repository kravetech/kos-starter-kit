---
title: Knowledge OS Starter Kit Architecture
type: architecture
status: active
area: system
version: 1.1.0
author: Kraven
created: 2026-07-15
updated: 2026-07-28
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

# Knowledge OS Starter Kit Architecture

## Release

| Field | Value |
| --- | --- |
| System | Knowledge OS (KOS) Starter Kit |
| Version | `v1.1.0` |
| Author | `Kraven` |
| Release status | Private starter-kit architecture baseline |
| Release date | 2026-07-28 |

## Purpose

Knowledge OS is an Obsidian-based operating system for durable knowledge, business operations, projects, personal context, research, periodic reviews, and AI-assisted work. This document defines the architecture contract that the starter kit implements and generates.

The architecture separates:

- system rules and operational state;
- business, project, personal, hobby, and knowledge domains;
- rapid capture from curated knowledge;
- reusable templates from live records;
- active information from archived history;
- durable AI context from temporary execution state.

## Architecture Principles

1. Obsidian Markdown is the canonical, portable data format.
2. Top-level numeric prefixes provide stable navigation and ordering.
3. Durable knowledge and temporary execution state remain separate.
4. Active or sufficiently complex AI-ready projects contain `memory.md` and `handoff.md`; empty or simple folders do not receive them automatically.
5. Templates define repeatable structures without requiring Obsidian plugins.
6. Historical context is archived rather than deleted or retained in active files.
7. Credentials, secrets, and sensitive personal or company data are never committed.
8. External-source configuration is provider-neutral and local state is replaceable.
9. AI agents use progressive, task-specific context loading instead of broad recursive scans.
10. The reference KOS, starter-kit source, test output, and final user installation remain physically separated.

## Starter-Kit Project Boundary

The KOS installer and reusable templates are developed outside any live reference KOS.

| Purpose | Location | Access rule |
| --- | --- | --- |
| Live reference KOS | `<reference-kos>` | Read-only during starter-kit analysis |
| Starter-kit project | `<starter-kit-root>` | All installer source, templates, scripts, and reports are written here |
| Disposable validation output | `<starter-kit-root>/test-output` | Test installations only; safe to recreate |
| Final generated KOS | User-selected during installation | Must never default to the live reference KOS |

The starter-kit project must contain its own Git repository when version control is enabled. It must not share or alter the Git history of the reference KOS.

Local machine paths belong only in an ignored file such as `installer/local-config.json`. Reusable templates and this document must use placeholders and remain machine-independent.

### Required Isolation Checks

Before an installer or builder writes files, it must:

1. Resolve the source KOS, starter-kit, test-output, and installation target paths.
2. Confirm that the starter-kit path is not inside the live KOS.
3. Confirm that the installation target is not the live KOS.
4. Stop when any output path resolves inside the reference KOS.
5. Write analysis reports, templates, scripts, logs, and test files only under the starter-kit project.
6. Treat the live KOS as an architectural reference, not as distributable content.

## Starter-Kit Repository Structure

```text
<starter-kit-root>/
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

The starter kit may reproduce the architecture, policies, workflows, and neutral templates of KOS. It must not copy private notes, business records, personal information, credentials, linked-source inventories, generated reports, absolute paths, or existing project content.

## Installer Execution Model

`KOS-INSTALLER.md` is the canonical, tool-neutral installation specification. It must be executable by either Codex CLI or Claude Code.

The initialization flow is:

```text
initialize.ps1 or initialize.sh
        ↓
Detect Codex or Claude
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

Supported modes must include interactive, answer-file, dry-run, resume, standard, lean, creator, business, developer, custom, and migration modes. Existing customized files are preserved by default; proposed replacements use a `.new.md` suffix unless overwrite is explicitly enabled.

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

Release tags must use the `vMAJOR.MINOR.PATCH` form, starting with `v1.0.0`. Pre-releases may use identifiers such as `v1.1.0-alpha.1` or `v2.0.0-rc.1`.

Each release should:

1. Update the version and date in this document.
2. Record user-visible changes in a root `CHANGELOG.md`.
3. Validate templates and initialization scripts against a clean vault.
4. Confirm that private data, generated state, and credentials are excluded.
5. Create an annotated Git tag matching the documented version.

## Distribution and Publication Boundary

The starter kit source is prepared for public distribution under Apache-2.0. Publication still requires the owner-controlled release gate in `PUBLICATION.md`, including privacy validation of the exact staged Git content. Generated Knowledge OS instances remain private by default. The following paths require sanitization or exclusion from any public release:

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
| Starter-kit `logs/`, `build/`, `test-output/` | Exclude from release archives, not only from Git |
| Absolute machine paths in any document | Replace with placeholders such as `<starter-kit-root>` |

## Architecture Contract for v1.1.0

The following are stable in `v1.1.0`:

- numbered top-level domains from `00` through `09`, plus `99 - Archive`;
- Markdown-first, Obsidian-compatible storage;
- `memory.md` and `handoff.md` as the minimum AI-ready project contract;
- project lifecycle states under `02 - Projects`;
- plugin-independent templates under `08 - Templates`;
- archive-over-delete operating behavior;
- no credentials or secrets in the vault;
- strict separation between the reference KOS and the starter-kit project;
- Markdown-driven installation through Codex or Claude;
- progressive context loading and thin tool adapters.

Changes that break these guarantees require a new major version.
