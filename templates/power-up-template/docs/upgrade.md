# Upgrade

1. Check `kos_compatibility` in the new `manifest.yaml` against the target
   vault's recorded `kosContractVersion`. Legacy discovery can also read an
   explicit `kos_contract_version` in `ARCHITECTURE.md` front matter. If
   discovery reports an unknown Core contract, verify compatibility before proceeding.
2. Back up the current manifest and configuration.
3. Preserve user-created data and previously approved outputs.
4. Run migrations only when this release declares one.
5. Update the registry entry's `version` and `updated_at` only after the
   upgrade validates successfully.
6. Roll back to the backed-up state if validation fails.

The legacy `installer/upgrade.ps1` and `installer/upgrade.sh` files are
placeholders for authors implementing this sequence. For an installed v1
package, use the [package update procedure](../../../docs/POWER-UP-INSTALLATION-GUIDE.md#upgrade).
