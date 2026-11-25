# Power-Up Installation Guide

For a first installation, use the two packages in the extracted kit and follow the walkthrough from permission review through your first result. [Free Project Action List tutorial](PROJECT-ACTION-LIST.md)

## Install a v1 package

Keep the package source outside the target vault. The installer accepts a package directory or a `.kospkg` archive containing `manifest.json` and integrity-checked files under `payload/`. Validate the package, then preview the install.

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

## Enable and opt in a project

After installation, enable each dependency and the Power-Up with `-PackageCommand enable -Id <id> -Approve` or `--package-command enable --id <id> --approve`. For a project-scoped workflow, record the opt-in in `02 - Projects/Active/<Project>/power-ups.json`. A missing opt-in or global disable blocks the bundled workflow. [Project activation example](PROJECT-ACTION-LIST.md#install-and-opt-in)

## Run the workflow

For Project Action List, select the source notes and use the same shared Skill with Gemini CLI, Claude Code or Codex CLI. The tutorial also includes an account-free local route. [Prepare and save the result](PROJECT-ACTION-LIST.md#run-the-shared-skill)

## Disable

Use `-PackageCommand disable -Id <id>` or
`--package-command disable --id <id>` after reviewing a dry-run plan.

## Upgrade

Use `-PackageCommand update -Package <new-package>` or its Bash equivalent.
The v1.2 engine keeps the prior immutable version for reviewed rollback and
preserves user configuration. See [the package lifecycle](PACKAGES-V1.md).

## Inspect installed packages

Use `-PackageCommand list` or `--package-command list`, then validate the KOS installation.

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

## Legacy YAML discovery

Use these commands only when inspecting an older `manifest.yaml` layout. Point `KOS_POWERUPS_HOME` or the configured home environment variable at the parent of the external package directories. The wrappers also accept an explicit home directory.

```powershell
./scripts/powerups.ps1 discover -InstallationRoot "<path-to-your-kos>"
./scripts/powerups.ps1 status -InstallationRoot "<path-to-your-kos>"
```

```bash
./scripts/powerups.sh discover "<path-to-your-kos>"
./scripts/powerups.sh status "<path-to-your-kos>"
```

Discovery checks manifests and reports findings. Status inspects registered entries and reports missing files. Both operations are read-only. To install a reviewed legacy package, migrate its manifest and payload to the v1 format. [Package format](PACKAGES-V1.md)
