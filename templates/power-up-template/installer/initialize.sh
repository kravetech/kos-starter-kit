#!/usr/bin/env bash
set -euo pipefail

target="${1:?Usage: initialize.sh TARGET_FOLDER [--dry-run]}"
dry_run="false"
if [[ "${2:-}" == "--dry-run" ]]; then dry_run="true"; fi

# TODO: verify $target exists inside the approved KOS vault, then create only
# the declared workspace (see manifest.yaml -> workspace) under
# "$target/.kos/power-ups/kos-example/" without touching existing files.

if [[ "$dry_run" == "true" ]]; then
  printf '%s\n' "Dry run: would initialize kos-example for '$target'. No changes made."
  exit 0
fi

printf '%s\n' "kos-example: initialization not yet implemented for '$target' (template stub)."
