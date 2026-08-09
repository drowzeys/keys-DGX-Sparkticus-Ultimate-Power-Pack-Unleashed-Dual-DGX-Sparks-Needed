#!/usr/bin/env bash
# Bee FPV ~20s: flower field → forest → rain → dry
# Dual H3 instances, master-K0 multishot, MiniMax official prompt guide.
# Requires: dual-serve co-tenant OK; heretic TE + Sol/Sage/Spectrum/FBC stack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"
export H3_TURBO=0 H3_DUAL_TURBO=0
HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
OUT="${OUT_DIR:-$HOME/Videos/bee_fpv_rain_20s}"
mkdir -p "$OUT"
# Prefer scripts next to this package; fall back to ~/comfy
SPANS="${ROOT}/scripts/h3-spans.py"
[[ -f "$SPANS" ]] || SPANS="$HOME/comfy/h3-spans.py"
PLAN="${ROOT}/bee_fpv_rain_20s_plan.json"
cd "$(dirname "$SPANS")"
exec python3 "$SPANS" \
  --plan "$PLAN" \
  --nodes "${HEAD}:8188,${WORKER}:8188" \
  --kf-mode master-parallel \
  --upscale \
  --te heretic \
  --outdir "$OUT" \
  --workflow "${ROOT}/jc-noupscale-api.json" \
  --span-workflow "${ROOT}/jc-baseline-workflow-api.json"
