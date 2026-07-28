# Metadata Standards

Use metadata when it improves routing, governance, or review. Do not force it onto every casual note.

```yaml
---
ai_access: internal
ai_generated: false
review_status: draft
status: active
owner: "{{preferred_name}}"
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

Allowed `ai_access`: `public`, `internal`, `restricted`.

Allowed `review_status`: `draft`, `reviewed`, `approved`.

Restricted files are never automatically loaded. AI-generated public or operational content begins as draft. Missing access classification is restricted. Never store secrets in metadata.
