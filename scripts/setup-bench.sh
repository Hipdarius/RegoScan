#!/usr/bin/env bash
# One-shot bench setup: install deps, regenerate synth dataset, train a
# smoke model, then print the two serve commands. Useful when a fresh
# clone needs to verify the full pipeline works in a single command.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> installing python deps (uv)"
uv sync --all-extras

echo "==> installing web deps (npm)"
(cd web && npm ci)

echo "==> generating synth_v1.csv (400 samples)"
make data-gen

echo "==> training smoke model (50 epochs, 5 folds)"
make train

echo
echo "==> done. Serve commands:"
echo "   make serve-api    # http://127.0.0.1:8000"
echo "   make serve-web    # http://localhost:3000"
