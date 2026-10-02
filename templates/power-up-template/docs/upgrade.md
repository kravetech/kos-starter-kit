# Upgrade

1. Check `kos_compatibility` in the new `manifest.yaml` against the target
   KOS's `ARCHITECTURE.md` version before changing any files.
2. Back up the current manifest and configuration.
3. Preserve user-created data and previously approved outputs.
4. Run migrations only when this release declares one.
5. Update the registry entry's `version` and `updated_at` only after the
   upgrade validates successfully.
6. Roll back to the backed-up state if validation fails.

`installer/upgrade.ps1` / `installer/upgrade.sh` implement this sequence.
