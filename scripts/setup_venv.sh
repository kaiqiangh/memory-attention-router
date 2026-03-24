#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
printf '\nVirtual environment ready at %s/.venv\n' "$ROOT"
printf 'Activate with: source %s/.venv/bin/activate\n' "$ROOT"
