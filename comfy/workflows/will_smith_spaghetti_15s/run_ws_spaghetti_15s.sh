#!/usr/bin/env bash
# Will Smith spaghetti ~15s talking-head multishot (face-lock ref2va, dual H3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
COMFY="$(cd "$ROOT/../.." && pwd)"
export PYTHONPATH="${COMFY}${PYTHONPATH:+:$PYTHONPATH}"
export H3_TURBO=0 H3_DUAL_TURBO=0
HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
OUT="${OUT_DIR:-$HOME/Videos/will_smith_spaghetti_15s}"
PLAN="${ROOT}/ws_spaghetti_15s_plan.json"
mkdir -p "$OUT"
if [[ -n "${IDENTITY_PNG:-}" ]]; then
  python3 - <<PY
import json
from pathlib import Path
p = Path("$PLAN")
d = json.loads(p.read_text())
d["identity_portrait_png"] = "$IDENTITY_PNG"
p.write_text(json.dumps(d, indent=2) + "\n")
PY
fi
exec python3 "$COMFY/h3-talkinghead.py" \
  --plan "$PLAN" \
  --nodes "${HEAD}:8188,${WORKER}:8188" \
  --outdir "$OUT"
