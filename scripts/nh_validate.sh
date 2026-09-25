#!/usr/bin/env bash
# Neural-harness entry point for the CollaBuild checkout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT/harness_reports}"

echo "neural-harness: validating 'collabuild' from $ROOT"
nh validate collabuild --root "$ROOT" --out "$OUT"
echo "Reports written to $OUT"