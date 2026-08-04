#!/usr/bin/env bash
set -euo pipefail
root="${1:?Usage: validate-installation.sh INSTALLATION_ROOT}"
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/tooling.py" validate-install --root "$root"
