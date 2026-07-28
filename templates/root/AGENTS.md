---
title: "{{system_short_name}} AI Router"
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

# {{system_short_name}} AI Router

`AGENTS.md` is the canonical shared AI router. `CONTEXT-POLICY.md` is the retrieval and privacy authority.

## Bootstrap

1. Confirm the root by locating this file and `00 - System/Config/ai-context-manifest.yaml`.
2. Read `me.md`.
3. Classify the task.
4. Load only the matching authority or selected project context.
5. Stop loading when enough verified context exists.

## Task Bundles

- Quick task: `AGENTS.md`, `me.md`.
- Normal active work: add root `memory.md` and `handoff.md`.
- Active project: add `02 - Projects/Active/<Project>/PROJECT-CONTEXT.md`; add project `memory.md`/`handoff.md` only when present and needed.
- Architecture/design/product: load only the matching root authority and relevant project context.
- Business: load `01 - Business/Business-MOC.md` and the exact required file.

## Default Exclusions

Never broadly load reports, state, linked-source inventories, attachments, archives, histories, logs, credentials, secrets, entire daily history, entire project trees, or large generated data.

## Write Rules

- Preserve existing content and use reversible edits.
- Never store credentials in Markdown.
- Treat missing `ai_access` as restricted.
- AI-generated operational knowledge starts as draft.
- `memory.md` is durable and approved; `handoff.md` is current and replace-and-refresh.
- Do not commit, publish, configure remotes, or push without explicit authorization.
