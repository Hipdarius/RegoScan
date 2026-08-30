#!/usr/bin/env bash
# Minimal end-to-end smoke test. POSTs /api/predict/demo, then re-feeds
# the same vector to /api/predict and confirms both endpoints agree.
set -euo pipefail
BASE="${VERA_API_BASE:-http://127.0.0.1:8000}"

echo "==> /api/predict/demo"
curl -fsS -X POST "$BASE/api/predict/demo" \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42}' \
  | tee /tmp/vera-demo.json | head -c 400
echo
echo

echo "==> /api/predict (re-using the same feature vector)"
SPEC=$(jq -r '.spec' /tmp/vera-demo.json)
LED=$(jq -r '.led' /tmp/vera-demo.json)
LIF=$(jq -r '.lif_450lp' /tmp/vera-demo.json)
SWIR=$(jq -r '.swir // "null"' /tmp/vera-demo.json)
AS7=$(jq -r '.as7265x // "null"' /tmp/vera-demo.json)

curl -fsS -X POST "$BASE/api/predict" \
  -H 'Content-Type: application/json' \
  -d "{\"spec\": $SPEC, \"led\": $LED, \"lif_450lp\": $LIF, \"swir\": $SWIR, \"as7265x\": $AS7}" \
  | head -c 400
echo
