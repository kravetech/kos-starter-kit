#!/usr/bin/env bash
set -euo pipefail

starter_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
engine="$starter_root/installer/install.py"

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "ERROR: Python 3 is required. Execute KOS-INSTALLER.md with Codex or Claude if unavailable." >&2
  exit 2
fi

exec python3 "$engine" "$@"
