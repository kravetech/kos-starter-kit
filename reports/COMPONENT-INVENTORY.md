# Component Inventory

## Classification Summary

| Component | Class | Purpose | Canonical location | Load timing | Installer | Starts empty | Populated by | Privacy | Token impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI router | Required | Task classification and bootstrap | `AGENTS.md` | Every AI session | Yes | No | System identity | Internal | Low |
| Working profile | Required | User preferences and role | `me.md` | Tier 0 | Yes | No | User answers | Internal/restricted | Low |
| Root memory | Required | Durable approved context | `memory.md` | Normal active work | Yes | Nearly | System answers/review | Internal | Medium |
| Root handoff | Required | Current execution continuity | `handoff.md` | Normal active work | Yes | No | Installation/current work | Internal | Medium |
| Context policy | Required | Retrieval and access rules | `CONTEXT-POLICY.md` | Policy questions and routing | Yes | No | Privacy answers | Internal | Low |
| Token policy | Required | Size and loading limits | `TOKEN-OPTIMIZATION.md` | Context maintenance | Yes | No | Defaults | Public-safe | Low |
| Architecture | Required | Stable system contract | `ARCHITECTURE.md` | Architecture tasks | Yes | No | System answers | Internal | Medium |
| Design | Recommended | Interface direction | `DESIGN.md` | Design tasks | Yes | No | Neutral defaults | Internal | Low |
| Product | Recommended | Purpose and success | `PRODUCT.md` | Product tasks | Yes | No | System/user answers | Internal | Low |
| Claude adapter | Required | Claude entry behavior | `CLAUDE.md` | Claude startup | Yes | No | None | Internal | Very low |
| Codex adapter | Required | Codex entry behavior | `CODEX.md` | Codex startup | Yes | No | None | Internal | Very low |
| Domain MOCs | Recommended | Navigation without duplication | Domain roots | Matching domain task | Yes | Mostly | Privacy/mode answers | Mixed | Low |
| Project context | Recommended | Persistent project scope | Active project root | Selected project | Template only | Yes | Project activation | Internal | Medium |
| Decisions log | Recommended | Durable decision index | Active project root | Decision/architecture task | Template only | Yes | Approved decisions | Internal | Low |
| Project memory/handoff | Optional | Complex-project continuity | Active project root | Selected project | Template only | Yes | Active project work | Internal | Medium |
| Daily templates | Recommended | Operating rhythm | `08 - Templates/Reviews` | Review tasks | Yes | No | Rhythm answers | Internal | Low |
| Automation registry | Required | Manual/external workflow definitions | `00 - System/Automations` | Automation work | Yes | No | Rhythm/tool answers | Internal | Medium |
| State | Generated | Installer/runtime continuity | `00 - System/State` and Installation | Troubleshooting only | Structure/state | Yes | Scripts | Restricted | Excluded |
| Reports | Generated | Validation evidence | `00 - System/Reports` | Audit/validation only | Structure | Yes | Scripts | Internal | Excluded |
| Attachments | Large-context risk | Binary assets | `09 - Attachments` | Exact selection only | Structure | Yes | User | Restricted | Excluded |
| Archive | Large-context risk | Historical preservation | `99 - Archive` | Explicit history task | Structure | Yes | Lifecycle | Mixed | Excluded |
| Linked-source inventories | Private-only, Generated | External-source state | `00 - System/Linked Sources` | Bounded summary only | Structure | Yes | Integration | Restricted | Excluded |
| Provider connectors | Advanced | External automation | External configuration | Explicit setup | Definitions only | Yes | User configuration | Restricted | Excluded |
| Reference-specific skills | Excluded | Private operational workflows | Reference control plane | Never | No | N/A | N/A | N/A |
| Reference reports/history | Excluded | Private operational evidence | Reference reports/history | Never | No | N/A | N/A | N/A |
| Legacy duplicated adapters | Deprecated | Repeated policy | Root adapters | Never | No | N/A | N/A | N/A |

## Installation Mode Mapping

- Lean: required control plane, projects, inbox, daily, templates, attachments, archive.
- Standard: all numbered domains.
- Business: Standard plus business-oriented examples/templates.
- Developer: Standard plus project and ADR scaffolds.
- Creator: Standard plus content/review structures.
- Custom: core contract plus selected domains.
- Migration: selected mode applied additively with backup and conflict proposals.
