# Inspect a legacy Power-Up

Place this scaffold under the external Power-Ups home configured for the vault.
From the extracted Community installer, select the appropriate read-only command.

```powershell
./scripts/powerups.ps1 discover -InstallationRoot "<vault>"
```

```bash
bash scripts/powerups.sh discover "<vault>"
```

For installation, convert the reviewed manifest and payload to the
[v1 package format](../../../docs/PACKAGES-V1.md). Follow the
[Power-Up installation guide](../../../docs/POWER-UP-INSTALLATION-GUIDE.md) to
validate the package, preview the changes and approve installation.
