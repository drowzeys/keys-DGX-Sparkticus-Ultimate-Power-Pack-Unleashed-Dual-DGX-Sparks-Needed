#!/usr/bin/env bash
# One MiniMax H3 ComfyUI instance per node (.2 and .3), co-tenant with DS4.
# Native process. Start AFTER DS4 is serving.
#
# Memory (same on HEAD + WORKER — set once, applies to both Sparks):
#   H3_RESERVE_VRAM   GB Comfy should leave free for DS4/OS (default 40)
#   H3_VRAM_HEADROOM  GB DynamicVRAM tries to keep free (default 8)
# Soft limits (not vLLM gpu_memory_utilization). Tune:
#   H3_RESERVE_VRAM=48 H3_VRAM_HEADROOM=10 bash launch_h3_dual.sh
set -euo pipefail

H3_DIR="${H3_DIR:-/home/keyspark/h3-cotenancy}"
PORT="${H3_PORT:-8188}"
HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
HEAD_SSH="${HEAD_SSH:-keyspark@$HEAD}"
WORKER_SSH="${WORKER_SSH:-keyspark@$WORKER}"
DS4_HEALTH="${DS4_HEALTH:-http://${HEAD}:8888/v1/models}"

# After .2 UMA OOMs on 361f@12 + ESRGAN + DS4@0.78: default more headroom.
H3_RESERVE_VRAM="${H3_RESERVE_VRAM:-48}"
H3_VRAM_HEADROOM="${H3_VRAM_HEADROOM:-10}"

if [ "${FARM_MODE:-0}" = "1" ]; then
  echo "FARM MODE: DS4 intentionally down — H3 gets the whole node (bf16-resident renders)."
  # Full-precision models resident: no need to reserve for a co-tenant.
  H3_RESERVE_VRAM="${H3_RESERVE_VRAM_FARM:-8}"
  H3_VRAM_HEADROOM="${H3_VRAM_HEADROOM_FARM:-10}"
elif ! curl -sf -m 5 "$DS4_HEALTH" >/dev/null 2>&1; then
  echo "WARNING: DS4 not healthy at $DS4_HEALTH — start DS4 FIRST (or FARM_MODE=1 for render-farm use)."
  [ "${SKIP_CHECK:-0}" = "1" ] || exit 1
fi

echo "H3 memory: --reserve-vram ${H3_RESERVE_VRAM} --vram-headroom ${H3_VRAM_HEADROOM} (both .2 and .3)"
echo "  override: H3_RESERVE_VRAM=N H3_VRAM_HEADROOM=M $0"

# Shared launcher body (identical on every Spark)
LAUNCHER_BODY=$(cat <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/cuda-13.0/bin:\${PATH:-}
export CUDA_HOME=\${CUDA_HOME:-/usr/local/cuda-13.0}
cd /home/keyspark/h3-cotenancy/ComfyUI
# Co-tenant with DS4 @ ~0.78 util: soft VRAM budget so H3 offloads before
# eating the whole UMA pool (same defaults on HEAD and WORKER).
# choom +800: under memory pressure the kernel/earlyoom kills this render
# process first, never the co-tenant DS4 serve.
exec choom -n 800 -- .venv/bin/python main.py \\
  --listen 0.0.0.0 --port 8188 \\
  --disable-pinned-memory \\
  --reserve-vram ${H3_RESERVE_VRAM} \\
  --vram-headroom ${H3_VRAM_HEADROOM} \\
  "\$@"
EOF
)

launch_one() {
  local ssh_t="$1" label="$2"
  echo "-- launch H3 on $label ($ssh_t) --"
  ssh "$ssh_t" "mkdir -p '$H3_DIR/logs'"
  # shellcheck disable=SC2029
  ssh "$ssh_t" "cat > '$H3_DIR/h3-comfy-launch.sh'" <<<"$LAUNCHER_BODY"
  ssh "$ssh_t" "chmod +x '$H3_DIR/h3-comfy-launch.sh' && grep -E 'reserve-vram|vram-headroom|disable-pinned' '$H3_DIR/h3-comfy-launch.sh'"
  ssh "$ssh_t" "bash -s" <<REMOTE
set -e
H3_DIR='$H3_DIR'
PORT='$PORT'
if [ -f "\$H3_DIR/logs/comfyui.pid" ]; then
  kill "\$(cat \$H3_DIR/logs/comfyui.pid)" 2>/dev/null || true
fi
fuser -k \${PORT}/tcp 2>/dev/null || true
sleep 1
cd "\$H3_DIR"
nohup ./h3-comfy-launch.sh > "\$H3_DIR/logs/comfyui.log" 2>&1 &
echo \$! > "\$H3_DIR/logs/comfyui.pid"
echo "  pid=\$(cat \$H3_DIR/logs/comfyui.pid)"
REMOTE
}

launch_one "$HEAD_SSH"   ".2"
launch_one "$WORKER_SSH" ".3"

echo "waiting for Comfy system_stats..."
for ip in "$HEAD" "$WORKER"; do
  ok=0
  for _ in $(seq 1 36); do
    if curl -sf -m 3 "http://${ip}:${PORT}/system_stats" >/dev/null 2>&1; then
      ok=1; break
    fi
    sleep 5
  done
  if [ "$ok" = "1" ]; then
    echo "  H3 ok http://${ip}:${PORT}"
  else
    echo "  H3 NOT ready http://${ip}:${PORT}"
    ssh "keyspark@$ip" "tail -40 $H3_DIR/logs/comfyui.log" || true
  fi
done
# --- GB10 vLLM spin-wait fix (see GB10_SPIN_WAIT_PATCH.md) --------------------
# If this script runs a stock vLLM image, the served container will busy-spin CPU
# cores at max clock while waiting on shm_broadcast (busy_loop_s=1s default),
# heating the shared GB10 SoC. Prefer an image built with the patch baked in.
# https://nacyot.github.io/artifacts/vllm-spin-wait-gb10/
