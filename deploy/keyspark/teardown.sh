#!/usr/bin/env bash
# Tear down H3 first, then DS4 (reverse of bring-up).
set -euo pipefail

RECIPE="${RECIPE:-/home/keyspark/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731}"
HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
HEAD_SSH="${HEAD_SSH:-keyspark@$HEAD}"
WORKER_SSH="${WORKER_SSH:-keyspark@$WORKER}"
H3_DIR="${H3_DIR:-/home/keyspark/h3-cotenancy}"
PORT="${H3_PORT:-8188}"

echo "== stop H3 on both nodes =="
for host in "$HEAD_SSH" "$WORKER_SSH"; do
  ssh "$host" "pkill -f 'main.py --listen 0.0.0.0 --port ${PORT}' 2>/dev/null || true
    pkill -f 'h3-comfy-launch' 2>/dev/null || true
    rm -f $H3_DIR/logs/comfyui.pid 2>/dev/null || true" || true
  echo "  $host H3 stopped"
done

echo "== stop DS4 pair =="
ssh "$HEAD_SSH" "cd $RECIPE && ./stop-deepseek-v4-flash-dspark.sh" || true
echo "done"
