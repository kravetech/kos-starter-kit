---
title: AI Context Policy
type: ai-instruction
status: active
owner: "{{preferred_name}}"
created: {{installation_date}}
updated: {{installation_date}}
ai_access: internal
ai_generated: true
review_status: draft
canonical: true
---

# AI Context Policy

## Tiers

- Tier 0: `AGENTS.md`, `me.md`.
- Tier 1: root context or one active project's context.
- Tier 2: task-specific authority or instruction.
- Tier 3: architecture history, changelog slices, reports, state, archives, or troubleshooting evidence.

## Progressive Loading

Classify the task, inspect an MOC, search within a bounded scope, read only the relevant section, and stop when enough evidence exists.

## Access

Allowed `ai_access`: `public`, `internal`, `restricted`. Missing classification is restricted. Folder policy can narrow but not expand access.

## Exclusions

Never automatically load `00 - System/Reports`, `00 - System/State`, `00 - System/Linked Sources`, `09 - Attachments`, `99 - Archive`, history, logs, databases, generated inventories, or large data files.

## Linked Sources

External sources are read-only until explicitly configured. Use indexes and bounded summaries instead of raw inventories.
