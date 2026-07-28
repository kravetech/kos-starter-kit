# Context Load Analysis

## Recommendation

Use a four-tier progressive model and keep only the router plus working profile in the default quick-task bundle.

## Bundles

| Task | Load | Explicitly avoid |
| --- | --- | --- |
| Quick note/domain routing | `AGENTS.md`, `me.md` | Root context, authorities, histories |
| Normal active work | Quick bundle + root `memory.md`, `handoff.md` | All projects |
| Active project | Router/profile + selected project context | Other projects and duplicated hub context |
| Architecture | Router + `ARCHITECTURE.md` + relevant project context | Full changelog |
| Design | Router + `DESIGN.md` + relevant project context | Unrelated product/history |
| Product | Router + `PRODUCT.md` + relevant project context | Architecture unless decision requires it |
| Business | Router/profile + Business MOC + exact file | Whole business domain |
| Validation | Exact target, validators, bounded metadata | Raw inventories |
| History/release | Bounded changelog section or exact snapshot | Full history by default |

## Large-File Protection

- Warning: 20 KB.
- Large: 50 KB.
- Very large: 200 KB.
- Inspect headings first, search terms second, read sections third.
- Prefer MOCs, manifests, and summaries.

## Excluded Normal Context

- Reports and runtime state.
- Attachments and archives.
- Raw linked-source inventories.
- Logs, databases, CSV/XML datasets, and binary content.
- Entire daily-note history.
- Entire project directories.
- Full changelog.

## Risks and Controls

| Risk | Control |
| --- | --- |
| Router bloat | Keep procedures in task authorities |
| Duplicate adapters | Canonical `AGENTS.md`; thin pointers |
| Memory drift | Human approval and size thresholds |
| Handoff history growth | Replace/refresh and meaningful snapshots |
| Cross-project contamination | One selected project context |
| Linked-source exposure | Read-only, bounded summaries, excluded raw state |
| False certainty | Running implementation or primary source wins |
