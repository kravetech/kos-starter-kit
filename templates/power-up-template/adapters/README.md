# Adapters

Thin, provider-specific entry points only. Every adapter must point at the
canonical skill (`.agents/skills/kos-example/SKILL.md`) rather than
duplicating capabilities, validation, schemas, or business logic. If an
adapter file starts holding real logic, move that logic into `runtime/` or
the canonical skill and shrink the adapter back down.

- `claude/` — Claude Code integration point.
- `codex/` — Codex CLI integration point.
- `gemini/` — Gemini CLI integration point.

Not every Power-Up needs every adapter at first release. Add one when that
agent needs to invoke this Power-Up.
