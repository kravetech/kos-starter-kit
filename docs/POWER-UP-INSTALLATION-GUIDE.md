# Power-Up Installation Guide

KOS Community 1.0.0 installs Power-Ups through the immutable local package
lifecycle in [PACKAGES-V1.md](PACKAGES-V1.md). The YAML workflow below is
legacy context for read-only discovery. It must not be used for v1.2 installs.

This guide covers package installation, activation, and lifecycle operations
against an existing KOS instance, plus read-only review of older YAML Power-Ups.

## 1. Keep package source outside the vault

Recommended (external, default) layout:

```text
<workspace-root>/
├── Obsidian/<Your KOS Vault>/
└── KOS Power-Ups/
    └── kos-example/          # this Power-Up's own repository/package
```

For older YAML discovery only, set the environment variable your KOS instance
is configured to look for
(`00 - System/Power-Ups/settings.yaml` -> `power_ups.home_environment_variable`,
`KOS_POWERUPS_HOME` by default) to the parent directory (`KOS Power-Ups/`
above), or pass `-HomeDirectory` / `--home` explicitly to the commands below.

## 2. Discover

```powershell
./scripts/powerups.ps1 discover -InstallationRoot "<path-to-your-kos>"
```

```bash
./scripts/powerups.sh discover "<path-to-your-kos>"
```

This scans the configured home directory for subdirectories containing a
`manifest.yaml`, validates each one (unique id, semantic version, KOS
compatibility, declared permissions, lifecycle commands), and reports
`PASS`, `WARNING`, or `ERROR` per candidate. **Nothing in the candidate
directory is ever executed.** Nothing is registered by this step.

## 3. Install a reviewed v1.2 package

The legacy `register` command is blocked in both wrappers. Repackage a YAML
candidate with `manifest.json` and integrity-checked `payload/` before using
the v1.2 package installer. Validate and dry-run it first:

```powershell
./install.ps1 -Target "<path-to-your-kos>" -PackageCommand validate -Package "<package-directory-or-kospkg>"
./install.ps1 -Target "<path-to-your-kos>" -PackageCommand install -Package "<package-directory-or-kospkg>" -DryRun
```

```bash
./install.sh --target "<path-to-your-kos>" --package-command validate --package "<package-directory-or-kospkg>"
./install.sh --target "<path-to-your-kos>" --package-command install --package "<package-directory-or-kospkg>" --dry-run
```

Review identity, integrity, compatibility, dependencies, permissions, and
planned file changes. Apply with `-Approve` / `--approve`; nonempty permission
requests additionally need `-ApprovePermissions` / `--approve-permissions`.
The package installer does not execute package entrypoints or discovered scripts.

## 4. Activate for a project

If the package supports project scope, record its exact installed identity in
`02 - Projects/Active/<Project>/power-ups.json` using the shipped project
activation schema. Review the package's requested permissions for that project.
Runtime consumers must enforce global enabled status and installed integrity.

## 5. Use

Invoke the approved package's declared entrypoint only when the Power-Up is
needed for a task. The package installer does not run it automatically.

## Disable

Use `-PackageCommand disable -Id <id>` or
`--package-command disable --id <id>` after reviewing a dry-run plan.

## Upgrade

Use `-PackageCommand update -Package <new-package>` or its Bash equivalent.
The v1.2 engine keeps the prior immutable version for reviewed rollback and
preserves user configuration. See [the package lifecycle](PACKAGES-V1.md).

## Repair

For a legacy YAML registry, the read-only `status` command reports entries and
missing local manifests or external runtimes:

```powershell
./scripts/powerups.ps1 status -InstallationRoot "<path-to-your-kos>"
```

```bash
./scripts/powerups.sh status "<path-to-your-kos>"
```

`status` never modifies files. For v1.2 packages, use `-PackageCommand list`
or `--package-command list`, then validate the KOS installation.

## Uninstall

Dry-run `-PackageCommand uninstall -Id <id>` or the Bash equivalent, then
approve the reviewed plan. Only unchanged, manifest-declared package code is
removed; configuration, state, reports, and generated user data remain.

## Enabling Power-Up Support Later

If an existing KOS instance has no Power-Ups integration structure, dry-run an
upgrade with the v1.2 installer and review the missing assets:

```powershell
./install.ps1 -Target "<path-to-your-kos>" -Operation upgrade -DryRun
```

Approved reconciliation creates only the missing compatible structure and
preserves existing files. Older YAML registries require manual review before
adoption into the immutable package registry.
