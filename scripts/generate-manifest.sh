#!/usr/bin/env bash
set -euo pipefail
root="${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/tooling.py" manifest --root "$root"
