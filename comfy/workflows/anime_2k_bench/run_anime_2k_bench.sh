#!/usr/bin/env bash
# Anime 2K bench — dual-Spark master-K0 multishot + **async ESRGAN×2**
#
# Claude upgrade (2026-08-11): --upscale-async
#   Spans render at native 704×1280 (low memory under DS4 co-tenancy).
#   Finished spans are upscaled to ~1408×2560 on free nodes **in parallel**
#   with remaining span work. Stitch uses the x2 clips.
#
# Dual-serve foundation: tonyd2wild/ds4-h3-video-gen-factory
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"
export H3_TURBO=0 H3_DUAL_TURBO=0

HEAD="${HEAD:-10.100.10.1}"
WORKER="${WORKER:-10.100.10.5}"
OUT="${OUT_DIR:-$HOME/Videos/anime_2k_bench}"
PLAN="${PLAN:-$ROOT/anime_2k_plan.json}"
REALISM="${REALISM:-0}"
# UPSCALE_MODE: async (default, Claude upgrade) | inline | none
UPSCALE_MODE="${UPSCALE_MODE:-async}"
REUSE_KF="${REUSE_KF:-}"   # optional glob to reuse keyframes

mkdir -p "$OUT"

if [[ "$REALISM" == "1" ]]; then
  KF_WF="$ROOT/graphs/jc-noupscale-api-realism.json"
  SPAN_WF="$ROOT/graphs/jc-baseline-workflow-api-realism.json"
  echo "REALISM=1 → LoRA h3-realism-people-t2v-i2v-r2v"
else
  KF_WF="$ROOT/graphs/jc-noupscale-api.json"
  # async path uses noupscale for spans (upscale decoupled)
  SPAN_WF="$ROOT/graphs/jc-noupscale-api.json"
fi

SPANS="$ROOT/scripts/h3-spans.py"
[[ -f "$SPANS" ]] || SPANS="$HOME/keys-DGX-Sparkticus-Ultimate-Power-Pack-Unleashed/comfy/h3-spans.py"
[[ -f "$SPANS" ]] || SPANS="$HOME/comfy/h3-spans.py"

echo "=== anime 2K bench (upscale_mode=$UPSCALE_MODE) ==="
echo "  plan  : $PLAN"
echo "  nodes : ${HEAD}:8188 + ${WORKER}:8188"
echo "  out   : $OUT"
echo "  path  : native 704×1280 → ESRGAN×2 → ~1408×2560"
echo "  turbo : OFF"
echo

for ip in "$HEAD" "$WORKER"; do
  curl -sf -m 5 "http://${ip}:8188/system_stats" >/dev/null || {
    echo "ERROR: H3 Comfy not up at http://${ip}:8188" >&2
    exit 1
  }
done

ARGS=(
  --plan "$PLAN"
  --nodes "${HEAD}:8188,${WORKER}:8188"
  --kf-mode master-parallel
  --te heretic
  --outdir "$OUT"
  --workflow "$KF_WF"
)

case "$UPSCALE_MODE" in
  async)
    ARGS+=(--upscale-async --upscale-model RealESRGAN_x2plus.pth)
    # span graph without inline ESRGAN (async does x2 after each span)
    ARGS+=(--span-workflow "$SPAN_WF")
    ;;
  inline)
    ARGS+=(--upscale --span-workflow "${ROOT}/graphs/jc-baseline-workflow-api$([ "$REALISM" = 1 ] && echo -realism).json")
    if [[ "$REALISM" == "1" ]]; then
      ARGS+=(--span-workflow "$ROOT/graphs/jc-baseline-workflow-api-realism.json")
    else
      ARGS+=(--span-workflow "$ROOT/graphs/jc-baseline-workflow-api.json")
    fi
    ;;
  none)
    ARGS+=(--span-workflow "$SPAN_WF")
    ;;
  *)
    echo "UPSCALE_MODE must be async|inline|none" >&2; exit 1
    ;;
esac

if [[ -n "$REUSE_KF" ]]; then
  ARGS+=(--reuse-kf-glob "$REUSE_KF")
fi

cd "$(dirname "$SPANS")"
exec python3 "$SPANS" "${ARGS[@]}"
