#!/usr/bin/env bash
set -euo pipefail
root="${1:?Usage: validate-installation.sh INSTALLATION_ROOT [--report FILE]}"
shift
if (( $# != 0 )) && ! [[ $# == 2 && $1 == --report && -n $2 ]]; then
  printf '%s\n' 'Usage: validate-installation.sh INSTALLATION_ROOT [--report FILE]' >&2
  exit 2
fi
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/tooling.py" validate-install --root "$root" "$@"
