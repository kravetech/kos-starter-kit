#!/usr/bin/env bash
set -euo pipefail

# TODO: implement the sequence in docs/uninstall.md -- disable first, show
# affected files/workspaces, remove the runtime only after approval, preserve
# user data by default, and never touch canonical KOS files.

dry_run="false"
if [[ "${1:-}" == "--dry-run" ]]; then dry_run="true"; fi

if [[ "$dry_run" == "true" ]]; then
  printf '%s\n' "Dry run: kos-example uninstall would run here. No changes made."
  exit 0
fi

printf '%s\n' "kos-example: uninstall not yet implemented (template stub)."
