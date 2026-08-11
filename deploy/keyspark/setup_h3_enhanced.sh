#!/usr/bin/env bash
# Bring .2/.3 h3-cotenancy to parity with single-Spark heretic enhanced stack:
#   Heretic TE + SageAttn + SolAttnPatch + Spectrum + FBC + RealESRGAN x2
# Does NOT start/stop DS4. Restarts ComfyUI on each node.
set -euo pipefail

HEAD="${HEAD:-spark-7552}"
WORKER="${WORKER:-spark-0060}"
H3_DIR="${H3_DIR:-/home/keyspark/h3-cotenancy}"
SRC_COMFY="${SRC_COMFY:-/home/keyspark/comfy/ComfyUI}"
HERETIC_TE="${HERETIC_TE:-$SRC_COMFY/models/text_encoders/H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors}"

say() { echo -e "\n=== $* ==="; }

setup_node() {
  local host="$1"
  say "setup $host"
  ssh "$host" "bash -s" <<REMOTE
set -euo pipefail
H3_DIR='$H3_DIR'
SRC_READY=1
export PATH=/usr/local/cuda-13.0/bin:\${PATH:-}
export CUDA_HOME=/usr/local/cuda-13.0
export LD_LIBRARY_PATH=/usr/local/cuda-13.0/lib64:/lib/aarch64-linux-gnu:\${LD_LIBRARY_PATH:-}

cd "\$H3_DIR/ComfyUI"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
PY=.venv/bin/python
PIP=.venv/bin/pip
\$PIP install -q -U pip wheel setuptools
# core + enhanced deps
\$PIP install -q -r requirements.txt 2>/dev/null || true
\$PIP install -q 'sageattention==1.0.6' pillow color-matcher matplotlib \
  opencv-python-headless 2>&1 | tail -5
\$PY -c "import sageattention, cv2; print('sage+cv2 OK', sageattention.__file__)"

mkdir -p models/text_encoders/H3 models/upscale_models models/diffusion_models models/vae
REMOTE

  # sync custom nodes (authoritative from head comfy)
  rsync -a --delete --exclude '__pycache__' --exclude '.git' \
    "$SRC_COMFY/custom_nodes/ComfyUI_sol-attn_Blackwell/" \
    "$host:$H3_DIR/ComfyUI/custom_nodes/ComfyUI_sol-attn_Blackwell/"
  rsync -a --delete --exclude '__pycache__' --exclude '.git' \
    "$SRC_COMFY/custom_nodes/ComfyUI-SolAttn_triton/" \
    "$host:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-SolAttn_triton/"
  rsync -a --delete --exclude '__pycache__' --exclude '.git' \
    "$SRC_COMFY/custom_nodes/ComfyUI-Spectrum-MiniMax-H3/" \
    "$host:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-Spectrum-MiniMax-H3/"
  rsync -a --delete --exclude '__pycache__' --exclude '.git' \
    "$SRC_COMFY/custom_nodes/ComfyUI-H3-Multishot/" \
    "$host:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-H3-Multishot/"
  rsync -a --delete --exclude '__pycache__' --exclude '.git' \
    "$SRC_COMFY/custom_nodes/ComfyUI-KJNodes/" \
    "$host:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-KJNodes/"
  # Motion Context (seamless audio) — prefer setup_h3_turbo.sh; sync if present
  if [[ -d /tmp/ComfyUI-H3-Motion-Context ]]; then
    rsync -a --delete --exclude '__pycache__' \
      /tmp/ComfyUI-H3-Motion-Context/ \
      "$host:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-H3-Motion-Context/"
  elif [[ -d "$SRC_COMFY/custom_nodes/ComfyUI-H3-Motion-Context" ]]; then
    rsync -a --delete --exclude '__pycache__' --exclude '.git' \
      "$SRC_COMFY/custom_nodes/ComfyUI-H3-Motion-Context/" \
      "$host:$H3_DIR/ComfyUI/custom_nodes/ComfyUI-H3-Motion-Context/"
  fi

  # 2026-08 H3 upgrades: Contex-Loop (scene A/V chain), MultiRef+custom KF, NKD preview
  for pack in \
    ComfyUI-MiniMaxH3-Contex-Loop \
    ComfyUI-H3-Motion-Context-MultiRef \
    ComfyUI-NKD-Preview-Tools
  do
    if [[ -d "$SRC_COMFY/custom_nodes/$pack" ]]; then
      rsync -a --delete --exclude '__pycache__' --exclude '.git' \
        "$SRC_COMFY/custom_nodes/$pack/" \
        "$host:$H3_DIR/ComfyUI/custom_nodes/$pack/"
      echo "  synced $pack -> $host"
    fi
  done

  # Realism-People LoRA (optional quality; bf16 LoRA on int8 DiT — A/B)
  if [[ -f "$SRC_COMFY/models/loras/h3-realism-people-t2v-i2v-r2v.safetensors" ]]; then
    ssh "$host" "mkdir -p $H3_DIR/ComfyUI/models/loras"
    rsync -a --info=stats2 \
      "$SRC_COMFY/models/loras/h3-realism-people-t2v-i2v-r2v.safetensors" \
      "$host:$H3_DIR/ComfyUI/models/loras/" || true
  fi

  # heretic TE
  ssh "$host" "mkdir -p $H3_DIR/ComfyUI/models/text_encoders/H3"
  rsync -a --info=stats2 "$HERETIC_TE" \
    "$host:$H3_DIR/ComfyUI/models/text_encoders/H3/"
  # default name → heretic
  ssh "$host" "cd $H3_DIR/ComfyUI/models/text_encoders
    if [ -f qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors ] && [ ! -L qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors ]; then
      mv -n qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors qwen3vl_32b_minimax_h3_nvfp4_awq.STOCK.safetensors || true
    fi
    ln -sfn H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
  "

  # RealESRGAN upscalers
  rsync -a --info=stats2 \
    "$SRC_COMFY/models/upscale_models/RealESRGAN_x2plus.pth" \
    "$SRC_COMFY/models/upscale_models/RealESRGAN_x2.pth" \
    "$SRC_COMFY/models/upscale_models/RealESRGAN_x4plus.pth" \
    "$host:$H3_DIR/ComfyUI/models/upscale_models/" 2>/dev/null || \
  rsync -a "$SRC_COMFY/models/upscale_models/"*.pth \
    "$host:$H3_DIR/ComfyUI/models/upscale_models/"

  # DiT + VAE already there; ensure both fl2va and ref2va
  rsync -a --info=stats2 \
    "$SRC_COMFY/models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" \
    "$SRC_COMFY/models/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" \
    "$host:$H3_DIR/ComfyUI/models/diffusion_models/" 2>/dev/null || true

  # launcher: co-tenancy flags + CUDA
  ssh "$host" "cat > $H3_DIR/h3-comfy-launch.sh <<'LAUNCH'
#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/cuda-13.0/bin:\${PATH:-}
export CUDA_HOME=/usr/local/cuda-13.0
export LD_LIBRARY_PATH=/usr/local/cuda-13.0/lib64:/lib/aarch64-linux-gnu:\${LD_LIBRARY_PATH:-}
export TRITON_CACHE_DIR=\${HOME}/.triton/cache
mkdir -p \"\$TRITON_CACHE_DIR\"
cd /home/keyspark/h3-cotenancy/ComfyUI
# Co-tenant with DS4: disable pinned memory. Never --use-sage-attention (noise).
# Sage is applied in-graph via PathchSageAttentionKJ.
exec .venv/bin/python main.py --listen 0.0.0.0 --port 8188 --disable-pinned-memory \"\$@\"
LAUNCH
chmod +x $H3_DIR/h3-comfy-launch.sh
"

  # restart comfy
  ssh "$host" "if [ -f $H3_DIR/logs/comfyui.pid ]; then kill \$(cat $H3_DIR/logs/comfyui.pid) 2>/dev/null || true; fi
    fuser -k 8188/tcp 2>/dev/null || true
    sleep 2
    cd $H3_DIR && nohup ./h3-comfy-launch.sh > $H3_DIR/logs/comfyui.log 2>&1 &
    echo \$! > $H3_DIR/logs/comfyui.pid
    echo restarted pid=\$(cat $H3_DIR/logs/comfyui.pid)
  "
}

setup_node "$HEAD"
# fabric mirror remaining bulk from .2 → .3 is faster for second host's TE/upscale if already done on first;
# still run full setup_node for deps on worker
setup_node "$WORKER"

say "wait healthy"
for i in $(seq 1 36); do
  a=$(curl -sf -m 2 http://10.100.10.2:8188/system_stats >/dev/null && echo OK || echo DOWN)
  b=$(curl -sf -m 2 http://10.100.10.3:8188/system_stats >/dev/null && echo OK || echo DOWN)
  echo "  H3.2=$a H3.3=$b"
  [ "$a" = OK ] && [ "$b" = OK ] && break
  sleep 5
done

say "verify optimization nodes"
for ip in 10.100.10.2 10.100.10.3; do
  echo "-- $ip --"
  curl -sf "http://$ip:8188/object_info" | python3 -c '
import sys,json
d=json.load(sys.stdin)
need=["PathchSageAttentionKJ","SolAttnPatch","SpectrumApplyMiniMaxH3","H3FirstBlockCache","UpscaleModelLoader","ImageUpscaleWithModel","MiniMaxH3MotionContext","MiniMaxH3MotionContextTrim","MiniMaxH3MotionContextSaveLatent","MiniMaxH3MotionContextLoadLatent","LoadVideo","GetVideoComponents"]
for n in need:
  print(f"  {n}: {'OK' if n in d else 'MISSING'}")
'
  ssh "keyspark@$ip" "grep -E 'Sol-Attn nodes|IMPORT FAILED|Spectrum|sage' $H3_DIR/logs/comfyui.log | tail -12" 2>/dev/null || true
done

say "done — use enhanced_render.py for heretic+fast+upscale jobs"
