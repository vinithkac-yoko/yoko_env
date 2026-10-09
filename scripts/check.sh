#!/usr/bin/env bash
# Everything CI runs, in one command. Stops at the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run lint-imports
uv run pytest -q --cov
uv run pytest packages/engine --cov=packages/engine/src --cov-fail-under=90 -q
(cd studio && npm run typecheck && npm test && npm run build)
echo "all checks passed"
