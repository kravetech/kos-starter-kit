# Privacy Model

## Stored Questionnaire Data

The answer file may store identity, locale, workflow preferences, enabled modules, privacy choices, and installation options. Keep real answer files local and untracked. The generated `me.md` contains the selected working profile.

## Sensitive Locations

- `03 - Personal/`
- `01 - Business/` when business access is restricted
- `00 - System/State/`
- `00 - System/Linked Sources/`
- `09 - Attachments/`
- `credentials/`, `secrets/`, and local integration configuration

## AI Access

Allowed values are `public`, `internal`, and `restricted`. Missing classification is treated as restricted. Restricted files are never loaded automatically. Folder policy narrows access; it never expands a file's classification.

## Linked Sources

External sources start unconfigured and read-only. Inventories are generated state, excluded from normal AI context and Git, and must be summarized through bounded reports rather than loaded wholesale.

## Reference Boundary

The starter kit does not copy private reference-system notes, identity content, memory, handoff state, companies, clients, employees, contacts, finance, health, credentials, projects, daily notes, reports, inventories, Git history, machine names, or reusable absolute paths.

For a private build review, add known sensitive names to a local, ignored denylist or run an exact scoped search. The reusable scanner intentionally does not embed private reference identifiers.

Copy `installer/private-terms.example.txt` to the ignored `installer/private-terms.txt`, replace its examples with private names, organizations, usernames, hostnames, and project identifiers, then run:

```powershell
.\scripts\privacy-scan.ps1
```

Before publication, stage the intended Git content and run `scripts/public-release-audit.ps1`. Git ignore rules do not protect manually created archives or force-added files.
