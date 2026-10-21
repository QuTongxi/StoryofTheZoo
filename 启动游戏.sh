#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ -x .venv/bin/python ]]; then
    exec .venv/bin/python game.py --gui "$@"
fi
if command -v uv >/dev/null 2>&1; then
    exec uv run python game.py --gui "$@"
fi
python3 -m venv .venv
.venv/bin/python -m pip install 'pygame-ce==2.5.8'
exec .venv/bin/python game.py --gui "$@"
