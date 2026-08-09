#!/usr/bin/env bash
# Install MiniMax-H3 Turbo (few-step LoRA) on both co-tenant H3 nodes.
#
# Weights (ComfyUI-fixed for pruned base):
#   https://huggingface.co/QrusherZA/H3_Turbo_ComfyUI
# Original Turbo training / nodes:
#   https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora
#   https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo
#
# Usage:
#   bash deploy/keyspark/setup_h3_turbo.sh
#   RESTART=1 bash deploy/keyspark/setup_h3_turbo.sh   # restart Comfy after install
set -euo pipefail

HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
H3_DIR="${H3_DIR:-/home/keyspark/h3-cotenancy}"
CACHE="${CACHE:-$HOME/.cache/h3-turbo}"
LORA_500="${H3_TURBO_LORA_REFINE:-minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors}"
LORA_850="${H3_TURBO_LORA_ROUGH:-minimax_h3_turbo_4step_ckpt850.safetensors}"
HF_REPO_500="QrusherZA/H3_Turbo_ComfyUI"
HF_REPO_850="larryvrh/MiniMax-H3-Turbo-Lora"
NODES_URL="https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git"
MC_URL="https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context.git"
RESTART="${RESTART:-1}"

say() { echo -e "\n=== $* ==="; }

say "0/5 download Turbo LoRAs (ckpt500 pruned + ckpt850 rough for dual-sampler)"
mkdir -p "$CACHE"
if [ ! -s "$CACHE/$LORA_500" ]; then
  hf download "$HF_REPO_500" "$LORA_500" --local-dir "$CACHE" || \
    curl -L --fail -o "$CACHE/$LORA_500" \
      "https://huggingface.co/${HF_REPO_500}/resolve/main/${LORA_500}?download=true"
fi
if [ ! -s "$CACHE/$LORA_850" ]; then
  hf download "$HF_REPO_850" "$LORA_850" --local-dir "$CACHE" || \
    curl -L --fail -o "$CACHE/$LORA_850" \
      "https://huggingface.co/${HF_REPO_850}/resolve/main/${LORA_850}?download=true"
fi
ls -lah "$CACHE/$LORA_500" "$CACHE/$LORA_850"

say "1/5 clone / update custom nodes (Turbo + Motion Context)"
NODES_SRC="${NODES_SRC:-/tmp/ComfyUI-MiniMax-H3-Turbo}"
MC_SRC="${MC_SRC:-/tmp/ComfyUI-H3-Motion-Context}"
if [ -d "$NODES_SRC/.git" ]; then git -C "$NODES_SRC" pull --ff-only || true
else git clone --depth 1 "$NODES_URL" "$NODES_SRC"; fi
if [ -d "$MC_SRC/.git" ]; then git -C "$MC_SRC" pull --ff-only || true
else git clone --depth 1 "$MC_URL" "$MC_SRC"; fi

say "2/5 install nodes + LoRAs on .2 and .3"
for ip in "$HEAD" "$WORKER"; do
  echo "-- $ip --"
  ssh "keyspark@$ip" "mkdir -p $H3_DIR/ComfyUI/custom_nodes $H3_DIR/ComfyUI/models/loras"
  rsync -a --delete "$NODES_SRC/" "keyspark@$ip:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo/"
  rsync -a --delete "$MC_SRC/" "keyspark@$ip:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-H3-Motion-Context/"
  scp -q "$CACHE/$LORA_500" "keyspark@$ip:$H3_DIR/ComfyUI/models/loras/$LORA_500"
  scp -q "$CACHE/$LORA_850" "keyspark@$ip:$H3_DIR/ComfyUI/models/loras/$LORA_850"
  ssh "keyspark@$ip" "test -f $H3_DIR/ComfyUI/models/loras/$LORA_500 && \
    test -f $H3_DIR/ComfyUI/models/loras/$LORA_850 && \
    test -f $H3_DIR/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo/__init__.py && \
    test -f $H3_DIR/ComfyUI/custom_nodes/ComfyUI-H3-Motion-Context/nodes.py && echo OK"
done

if [ "$RESTART" = "1" ]; then
  say "3/5 restart H3 Comfy on both nodes (loads Turbo + Motion Context)"
  for ip in "$HEAD" "$WORKER"; do
    ssh "keyspark@$ip" "bash -s" <<REMOTE
set -e
H3_DIR='$H3_DIR'
if [ -f "\$H3_DIR/logs/comfyui.pid" ]; then kill "\$(cat \$H3_DIR/logs/comfyui.pid)" 2>/dev/null || true; fi
fuser -k 8188/tcp 2>/dev/null || true
sleep 2
cd "\$H3_DIR"
nohup ./h3-comfy-launch.sh > "\$H3_DIR/logs/comfyui.log" 2>&1 &
echo \$! > "\$H3_DIR/logs/comfyui.pid"
echo restarted pid=\$(cat \$H3_DIR/logs/comfyui.pid)
REMOTE
  done
  echo "waiting for system_stats..."
  for ip in "$HEAD" "$WORKER"; do
    ok=0
    for _ in $(seq 1 36); do
      if curl -sf -m 3 "http://${ip}:8188/system_stats" >/dev/null 2>&1; then ok=1; break; fi
      sleep 5
    done
    echo "  $ip: $([ $ok = 1 ] && echo OK || echo DOWN)"
  done
else
  say "3/4 skip restart (RESTART=0) — restart Comfy manually to load nodes"
fi

say "4/5 verify Turbo + Motion Context nodes"
for ip in "$HEAD" "$WORKER"; do
  curl -sf "http://${ip}:8188/object_info" | python3 -c '
import sys,json
d=json.load(sys.stdin)
need=["MiniMaxH3TurboLoRA","MiniMaxH3TurboSampler","MiniMaxH3MotionContext","MiniMaxH3MotionContextTrim","MiniMaxH3MotionContextSaveLatent","MiniMaxH3MotionContextLoadLatent","SplitSigmas","LoadVideo","GetVideoComponents"]
print(sys.argv[1], {n:(n in d) for n in need})
' "$ip" || echo "$ip object_info failed (Comfy not ready?)"
  ssh "keyspark@$ip" "grep -E 'h3_motion_context: (interior|keyframe)' $H3_DIR/logs/comfyui.log | tail -3" 2>/dev/null || true
done

say "5/5 usage"
echo "Single turbo:     H3_TURBO=1 bash deploy/keyspark/run_quality_parallel.sh"
echo "Dual turbo (HQ):  H3_DUAL_TURBO=1 bash deploy/keyspark/run_quality_parallel.sh"
echo "  (@ANe5s #21: default ckpt850@1.0 x4 → ckpt500@0.7 x6 = 10 steps)"
echo "Seamless audio:   H3_MOTION_CONTEXT=1 H3_DUAL_TURBO=1 ...  # sequential arms + timeline"
echo "  audio_mode=timeline · context_latent Save/Load · context_length=22"
echo "Docs: docs/DUAL_TURBO_MOTION.md"
echo "Credits: larryvrh Turbo · QrusherZA pruned · @ANe5s dual-sampler · NikoDemon80 Motion Context"
