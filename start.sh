#!/usr/bin/env bash
# Uruchomienie: ./start.sh  (czyta ./input, zapisuje ./output)
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" main.py "$@"
