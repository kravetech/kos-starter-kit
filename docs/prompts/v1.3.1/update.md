# Upgrade an existing vault to KOS Community 1.3.1

For the [latest release and automatic backup preparation](../update.md), use the current prompt. This archived 1.3.1 procedure expects a verified backup and separate test copy. For a new vault, use the [install prompt](install.md). Copy the entire block into Codex CLI or Claude Code.

```text
Help me update my existing KOS vault to KOS Community 1.3.1.

Ask me for the paths to my original vault, a verified full backup stored outside the vault, and a disposable test copy. Confirm that the three paths are distinct. Work on the copy first.

Download the named release asset kos-community-v1.3.1.zip from the official KOS Community release:
https://github.com/kravetech/kos-community/releases/tag/v1.3.1

Before extracting it, calculate the ZIP’s SHA-256 and compare it with the checksum published on the release page. The expected SHA-256 is:
296f7a4ceda957d6c04242331c664988688eea789979d1881ef1cfda9c362376

Stop if the published checksum is unavailable or any value differs. Extract the verified ZIP into a separate folder outside the original vault, backup, and test copy.

Read the release metadata and the vault’s installer records locally. Compare the recorded distribution version (starterKitVersion for a managed vault or installer_version for a legacy vault) with supportedUpgradeVersions in installer/release.json. Show me the installed edition, recorded version, target version and supporting records. If the identity is unclear, the installed version is unsupported or newer, or a legacy Pro installer owns the vault, stop for review. If this is a plain Obsidian vault, offer the existing-vault enhancement guide and wait. If the vault is already current, offer read-only validation and wait.

For a supported older Starter Kit or Community vault, check my existing privacy exclusions and provider choices. Use my original installer answers locally if needed. Run the packaged installer on the disposable copy with the upgrade operation and explicit -DryRun or --dry-run. If previousVersion is null or the installer reports LEGACY_VERSION_UNKNOWN, stop and explain which original installer record or backup I should locate. Never invent or edit version metadata to clear a blocker.

Show me the resolved target path, planned updates, files that will be preserved, proposed changes for manual review, and any link conflicts. Check that owner edits and the recorded setup date are preserved. Review the separate proposed upgrade changelog entry. Stop and ask for my approval of that exact plan.

After I approve, apply the plan only to the disposable copy using the same inputs, then validate it. Help me check representative notes, links, settings, privacy exclusions, and any installed Power-Ups. Leave unresolved proposals for my review.

Before updating the original vault, reconfirm the verified backup and ask me to close editors and pause sync. Run a fresh dry run against the exact original path, show me that plan, and ask for separate approval. Apply it only after I approve. Then validate the original vault and report the result, run ID, and local recovery instructions. If any step fails, stop and preserve the run journal.
```
