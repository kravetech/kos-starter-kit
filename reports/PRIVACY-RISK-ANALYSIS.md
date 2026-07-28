# Privacy Risk Analysis

## Boundary

The starter kit derives architecture and behavior only. No reference identity, organization, client, employee, contact, financial, health, credential, project, daily-note, memory, handoff, report, inventory, external-source, Git-history, machine, or reusable absolute-path content is copied.

## Risk Register

| Risk | Severity | Control |
| --- | --- | --- |
| Personalization leaks through templates | High | Exact neutral placeholders; synthetic example answers |
| Answer files committed | High | Local answer/config files ignored |
| Secrets stored in Markdown | Critical | Documentation prohibition, Git ignore, heuristic scanner |
| Personal/business folders broadly loaded | High | Restricted defaults and task-specific access |
| Linked-source inventory exposure | Critical | Read-only, unconfigured, excluded context and Git |
| Attachments scanned automatically | High | Exact-selection-only policy |
| Migration destroys existing notes | Critical | Backup, preserve, `.new` conflict proposals |
| External automation falsely active | High | Every external entry starts `Not configured` |
| Machine paths become reusable content | Medium | Template path scan; local paths limited to ignored configuration/state/reports |
| AI-generated facts become authoritative | High | Draft review status and explicit human approval |
| Generated reports become durable context | Medium | Reports classified generated and excluded from bootstrap |

## Scanner Scope

The scanner checks reusable text assets for known private reference terms, credential-like patterns, private-key blocks, and absolute machine paths in templates. Logs, build output, and disposable test output are excluded from reusable-content scanning.

## Residual Risks

- Heuristic secret detection cannot identify every credential format.
- A user can intentionally place sensitive data in an answer file.
- Connector permissions and provider-side retention require separate review.
- Migration conflicts require human merging.
