#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT="$ROOT/agent"
export PATH="${HOME}/.local/bin:${PATH}"
cd "$AGENT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

uv sync --quiet
uv run python -m polyagent bootstrap
exec uv run python -m polyagent run "$@"
