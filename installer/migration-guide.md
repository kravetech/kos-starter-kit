# Migration from 1.0.0 and 1.1.0

Use [the v1.2 operation guide](../docs/INSTALLER-V1.2.md) and upgrade dry-run.
Legacy state identifies version, not ownership. Uncertain files remain user-owned;
exact current-template matches may be adopted. Customized routers and knowledge
receive proposals, never automatic replacement.

An unreleased staging vault already stamped with `kosContractVersion: 1.1.0` is blocked by the `1.0.0` Core baseline. Do not silently rewrite its installed contract state or treat its packages as compatible. Review that disposable staging vault separately; no customer release carried this stamp.

Obsidian vaults use enhance. Minimal adoption creates the control plane while
retaining content/settings. Alternate Skills/Power-Up registries require review
before creating a canonical registry. Retain run journals and backups until the
owner accepts the migration. Downgrades and automatic resume are blocked.

Review `linkAudit` in the dry-run plan before approving an existing vault.
Preexisting broken links remain visible; a newly ambiguous or redirected
previously resolved link blocks the plan. The check covers common file-target
wikilinks, embeds and Markdown links within documented scan limits. It does not
rewrite notes or replace an in-app Obsidian review on a backed-up test vault.
Create and verify a complete vault snapshot outside the target before applying
an upgrade or enhancement. Installer run backups cover only files it changes.
Remove the obsolete `backup_before_migration` field from old answer files; the
installer rejects it rather than implying a full-vault backup was made.
