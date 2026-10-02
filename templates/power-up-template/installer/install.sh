#!/usr/bin/env bash
set -euo pipefail

# TODO: install this Power-Up's own runtime dependencies (if any) into its
# external install directory. Do not touch any KOS vault from here -- vault
# registration and folder initialization are separate steps (see
# initialize.sh and docs/installation.md).

dry_run="false"
if [[ "${1:-}" == "--dry-run" ]]; then dry_run="true"; fi

if [[ "$dry_run" == "true" ]]; then
  printf '%s\n' "Dry run: kos-example install would run here. No changes made."
  exit 0
fi

printf '%s\n' "kos-example: nothing to install yet (template stub)."
