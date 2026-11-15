#!/usr/bin/env bash
# 30-second smoke test: run the unit-test suite, the linters, and the
# typecheck. Faster than `make test && make lint && make typecheck`
# because it parallelises the Python and web halves.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pytest tests/ -q --tb=line &
PID_TESTS=$!

uv run ruff check src/ apps/ scripts/ tests/ &
PID_LINT_PY=$!

(cd web && npx tsc --noEmit) &
PID_TSC=$!

(cd web && npm run lint --silent) &
PID_LINT_WEB=$!

wait $PID_TESTS && echo "  ✓ pytest"   || { echo "  ✗ pytest";   FAIL=1; }
wait $PID_LINT_PY && echo "  ✓ ruff"   || { echo "  ✗ ruff";     FAIL=1; }
wait $PID_TSC && echo "  ✓ tsc"        || { echo "  ✗ tsc";      FAIL=1; }
wait $PID_LINT_WEB && echo "  ✓ eslint" || { echo "  ✗ eslint"; FAIL=1; }

[ -z "${FAIL:-}" ] || exit 1
echo "  smoke ok"
