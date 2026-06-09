#!/bin/bash
# Run SatX from the git tree without pip install.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

missing=()
command -v hackrf_transfer >/dev/null 2>&1 || missing+=(hackrf)
command -v rtl_sdr >/dev/null 2>&1 || missing+=(rtl-sdr)
command -v rtl_433 >/dev/null 2>&1 || missing+=(rtl_433)
command -v satdump >/dev/null 2>&1 || missing+=(satdump)
if ((${#missing[@]})); then
  echo "Optional tools missing: ${missing[*]}" >&2
  echo "Install with: make deps   (or: brew install ${missing[*]})" >&2
fi

if [[ ! -d .venv ]]; then
  echo "Run 'make dev-install' first." >&2
  exit 1
fi

source .venv/bin/activate
exec python3 -m satx "$@"
