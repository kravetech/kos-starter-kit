# Reference KOS Analysis

## Executive Summary

The reusable architecture is a file-first, Obsidian-compatible operating system with stable numbered domains, a private system control plane, progressive AI context routing, explicit separation of durable memory from current execution state, template-driven lifecycle management, and generated-state isolation.

Recommendation: preserve the information architecture and governance contracts, but ship a smaller neutral baseline. Advanced linked-source monitoring, provider connectors, portable skills, and organization-specific workflows should remain optional and unconfigured.

## Root Contracts

- `AGENTS.md` is the canonical compact AI router.
- Tool adapters remain thin and point to shared policy.
- `ARCHITECTURE.md`, `DESIGN.md`, and `PRODUCT.md` are task authorities, not bootstrap files.
- `memory.md` stores approved durable context.
- `handoff.md` stores current replace-and-refresh execution continuity.
- `CHANGELOG.md` is release history and is loaded only in bounded slices.

## Folder Hierarchy

| Prefix | Responsibility | Starter classification |
| --- | --- | --- |
| `00` | System control plane, policies, automation definitions, state, reports | Required |
| `01` | Business | Recommended |
| `02` | Project lifecycle | Required |
| `03` | Personal | Recommended, restricted by default |
| `04` | Hobbies and creator work | Optional |
| `05` | Curated knowledge and research | Recommended |
| `06` | Capture and processing queue | Required |
| `07` | Daily and periodic reviews | Required |
| `08` | Reusable templates | Required |
| `09` | Binary attachments | Required structure, excluded context |
| `99` | Inactive historical information | Required structure, excluded context |

## System Control Plane

The control plane owns routing, metadata, naming, automation definitions, local configuration, generated state, reports, and installation evidence. Canonical knowledge stays separate from replaceable runtime state.

## Bootstrap and Task Classification

The effective pattern is:

1. Confirm the root contract.
2. Load the working profile.
3. Classify the task.
4. Select one small context bundle.
5. Inspect an MOC or bounded manifest.
6. Search narrowly.
7. Stop once sufficient evidence exists.

## Memory and Handoff

- Root memory target: below 3,000 tokens; review at 4,000; hard warning at 6,000.
- Root handoff target: below 2,000 tokens.
- Project-level context is created only for active or complex work.
- Completed handoff state becomes an immutable history snapshot only at meaningful boundaries.
- Durable AI-authored facts require human review.

## Project Lifecycle

`Idea -> Incubating -> Active -> On-Hold or Completed -> Archive`

Active projects may use `PROJECT-CONTEXT.md`, `DECISIONS.md`, `memory.md`, and `handoff.md`. Empty project folders do not receive persistent context automatically.

## Domain Workflows

- Business: route through a Business MOC and isolate sensitive organizational records.
- Personal: restricted by default and loaded only for explicit tasks.
- Hobbies: optional, with creator workflows separated from business obligations.
- Knowledge: store verified synthesis rather than raw source dumps.
- Inbox: clarify, classify, route, preserve source/privacy context, then empty on rhythm.
- Daily: daily execution plus weekly/monthly/annual review.
- Archive: preserve history without routine context exposure.

## Attachments and External Sources

Attachments and raw linked-source inventories are large-context and privacy risks. They are never normal bootstrap material. External sources default to read-only and `Not configured`; bounded summaries are preferred to inventories.

## Maintenance and Validation

The reference uses idempotent initialization, bounded search, context manifests, secret/path checks, adapter checks, project-context checks, and aggregate reporting. The starter kit adopts the contract using dependency-free cross-platform scripts and leaves provider-specific monitoring optional.

## Risks

- A full reference clone would copy private content and excessive operational complexity.
- Automatic project context everywhere creates stale, low-value files.
- Duplicated adapter policies drift.
- Broad linked-source discovery can expose large private datasets.
- Migration overwrite is unacceptable; conflict proposals and backups are required.
- Git automation must not configure remotes or push.
