#!/usr/bin/env bash
# Anime 2K bench — dual-Spark master-K0 multishot + ESRGAN×2 (→ ~1408×2560)
#
# Quality path (default):
#   heretic TE · Sage · SolAttn/Triton · Spectrum v0.2.1 audio fix
#   (offline_smoothing_replay=true, audio_blend_weight=0) · FBC · ESRGAN×2
#   · master-parallel spans · optional Realism-People LoRA
#
# Dual-serve foundation: tonyd2wild/ds4-h3-video-gen-factory
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"
export H3_TURBO=0 H3_DUAL_TURBO=0

# Default to Power Pack live pair (.1+.5); override for classic .2+.3
HEAD="${HEAD:-10.100.10.1}"
WORKER="${WORKER:-10.100.10.5}"
OUT="${OUT_DIR:-$HOME/Videos/anime_2k_bench}"
PLAN="${PLAN:-$ROOT/anime_2k_plan.json}"
REALISM="${REALISM:-0}"   # 1 = load h3-realism-people LoRA on graphs

mkdir -p "$OUT"

if [[ "$REALISM" == "1" ]]; then
  KF_WF="$ROOT/graphs/jc-noupscale-api-realism.json"
  SPAN_WF="$ROOT/graphs/jc-baseline-workflow-api-realism.json"
  echo "REALISM=1 → LoRA h3-realism-people-t2v-i2v-r2v @ strength 1.0"
else
  KF_WF="$ROOT/graphs/jc-noupscale-api.json"
  SPAN_WF="$ROOT/graphs/jc-baseline-workflow-api.json"
fi

SPANS="$ROOT/scripts/h3-spans.py"
[[ -f "$SPANS" ]] || SPANS="$HOME/keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed/comfy/h3-spans.py"
[[ -f "$SPANS" ]] || SPANS="$HOME/comfy/h3-spans.py"

echo "=== anime 2K bench ==="
echo "  plan     : $PLAN"
echo "  nodes    : ${HEAD}:8188 + ${WORKER}:8188"
echo "  outdir   : $OUT"
echo "  upscale  : ESRGAN×2 on spans (native 704×1280 → ~1408×2560)"
echo "  kf-mode  : master-parallel"
echo "  turbo    : OFF (quality)"
echo

# Preflight Comfy
for ip in "$HEAD" "$WORKER"; do
  if ! curl -sf -m 5 "http://${ip}:8188/system_stats" >/dev/null; then
    echo "ERROR: H3 Comfy not up at http://${ip}:8188" >&2
    echo "Bring up Power Pack dual-serve first (DS4 then H3)." >&2
    exit 1
  fi
done

# Spectrum audio-fix default check (warn only)
for ip in "$HEAD" "$WORKER"; do
  curl -sf "http://${ip}:8188/object_info/SpectrumApplyMiniMaxH3" 2>/dev/null | python3 -c '
import sys,json
try:
  j=json.load(sys.stdin); k=next(iter(j))
  bag=j[k]["input"].get("required",{})|j[k]["input"].get("optional",{})
  f=bag.get("offline_smoothing_replay")
  d=f[1].get("default") if isinstance(f,list) and len(f)>1 and isinstance(f[1],dict) else None
  print(f"  spectrum@{sys.argv[1]} offline_smoothing_replay default={d}")
except Exception as e:
  print(f"  spectrum check skipped: {e}")
' "$ip" || true
done

cd "$(dirname "$SPANS")"
exec python3 "$SPANS" \
  --plan "$PLAN" \
  --nodes "${HEAD}:8188,${WORKER}:8188" \
  --kf-mode master-parallel \
  --upscale \
  --te heretic \
  --outdir "$OUT" \
  --workflow "$KF_WF" \
  --span-workflow "$SPAN_WF"
