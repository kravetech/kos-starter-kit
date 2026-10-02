#!/usr/bin/env bash
set -euo pipefail

# TODO: implement the sequence in docs/upgrade.md -- check kos_compatibility,
# back up current manifest/config, preserve user data, migrate only when
# declared, update the registry version only after validation passes.

dry_run="false"
if [[ "${1:-}" == "--dry-run" ]]; then dry_run="true"; fi

if [[ "$dry_run" == "true" ]]; then
  printf '%s\n' "Dry run: kos-example upgrade would run here. No changes made."
  exit 0
fi

printf '%s\n' "kos-example: upgrade not yet implemented (template stub)."
