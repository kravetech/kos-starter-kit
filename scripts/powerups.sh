#!/usr/bin/env bash
set -euo pipefail
command="${1:?Usage: powerups.sh <discover|status> INSTALLATION_ROOT [--home DIR]}"
root="${2:?Usage: powerups.sh <discover|status> INSTALLATION_ROOT [--home DIR]}"
shift 2
case "$command" in
  discover|status) ;;
  register)
    printf '%s\n' 'ERROR: Legacy registration is read-only in v1.2. Use install.sh --package-command install after reviewing an immutable package.' >&2
    exit 2
    ;;
  *)
    printf 'ERROR: Unsupported Power-Up command: %s\n' "$command" >&2
    exit 2
    ;;
esac
exec "${PYTHON:-python3}" "$(dirname -- "${BASH_SOURCE[0]}")/tooling.py" "powerups-$command" --root "$root" "$@"
