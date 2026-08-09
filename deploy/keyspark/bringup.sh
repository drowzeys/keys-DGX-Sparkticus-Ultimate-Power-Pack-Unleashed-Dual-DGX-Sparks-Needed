#!/usr/bin/env bash
# Bring up dual-boot: DS4-0731 DSpark TP=2 + MiniMax H3 (heretic) on .2/.3.
# Tony co-tenancy order: DS4 first (full load), then H3.
#
# Stacks:
#   STACK=ablit  (default)  env.ablit-cotenancy  — abliterated DSV4F + heretic H3
#   STACK=stock             env.cotenancy        — stock 0731
# Override: ENV_SRC=/path/to/env
#
# After healthy:
#   bash $ROOT/run_quality_parallel.sh   # quality dual-H3 10s (concurrency=2)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
FACTORY="$(cd "$ROOT/../.." && pwd)"
RECIPE="${RECIPE:-/home/keyspark/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731}"
STACK="${STACK:-ablit}"
case "$STACK" in
  ablit|abliterated|heretic)
    ENV_SRC="${ENV_SRC:-$ROOT/env.ablit-cotenancy}"
    SERVED_HINT="deepseek-v4-flash-0731-ablit-l10-35-anchorstock"
    ;;
  stock|base)
    ENV_SRC="${ENV_SRC:-$ROOT/env.cotenancy}"
    SERVED_HINT="deepseek-v4-flash-0731"
    ;;
  *)
    echo "Unknown STACK=$STACK (use ablit|stock)" >&2
    exit 1
    ;;
esac
HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
HEAD_SSH="${HEAD_SSH:-keyspark@$HEAD}"
WORKER_SSH="${WORKER_SSH:-keyspark@$WORKER}"
SKIP_H3="${SKIP_H3:-0}"
SKIP_DS4="${SKIP_DS4:-0}"
WAIT_DS4_SEC="${WAIT_DS4_SEC:-600}"
ENHANCE_H3="${ENHANCE_H3:-1}"   # ensure heretic TE + Spectrum nodes before launch

say() { echo -e "\n=== $* ==="; }

say "0/5 install cotenancy env (STACK=$STACK → $(basename "$ENV_SRC"))"
for host in "$HEAD_SSH" "$WORKER_SSH"; do
  scp -q "$ENV_SRC" "$host:$RECIPE/.env.dspark"
  # keep a named copy
  scp -q "$ENV_SRC" "$host:$RECIPE/.env.dspark.cotenancy"
done
# local copy if this host has the tree
if [ -d "$RECIPE" ]; then
  cp -f "$ENV_SRC" "$RECIPE/.env.dspark"
  cp -f "$ENV_SRC" "$RECIPE/.env.dspark.cotenancy"
fi

say "1/5 preflight image + stock weights (bind-mount for docker visibility)"
bash "$ROOT/prep_stock_bindmounts.sh"
ssh "$HEAD_SSH" "docker image inspect ghcr.io/anemll/dspark-vllm-gx10:0.1.1 >/dev/null"
if ! ssh "$WORKER_SSH" "docker image inspect ghcr.io/anemll/dspark-vllm-gx10:0.1.1 >/dev/null 2>&1"; then
  say "transfer anemll image head → worker over fabric (one-time)"
  ssh "$HEAD_SSH" "docker save ghcr.io/anemll/dspark-vllm-gx10:0.1.1" \
    | ssh "$WORKER_SSH" "docker load"
fi
ssh "$HEAD_SSH" 'test -f /home/keyspark/.cache/huggingface/dsv4f-0731-stock/model-00001-of-00048.safetensors'
ssh "$WORKER_SSH" 'test -f /home/keyspark/.cache/huggingface/dsv4f-0731-stock/model-00001-of-00048.safetensors'

say "2/5 drop page caches (unified memory)"
for host in "$HEAD_SSH" "$WORKER_SSH"; do
  ssh "$host" 'sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null' || \
    echo "WARN: drop_caches failed on $host (need passwordless sudo)"
done

if [ "$SKIP_DS4" != "1" ]; then
  say "3/5 launch DS4 pair from head (worker-first inside start script)"
  # stop any prior stack first
  ssh "$HEAD_SSH" "cd $RECIPE && ./stop-deepseek-v4-flash-dspark.sh 2>/dev/null || true" || true
  ssh "$HEAD_SSH" "cd $RECIPE && nohup env ENV_FILE=$RECIPE/.env.dspark ./start-deepseek-v4-flash-dspark.sh > /tmp/ds4-cotenancy-start.log 2>&1 & echo \$! > /tmp/ds4-cotenancy-start.pid"
  echo "start pid: $(ssh "$HEAD_SSH" 'cat /tmp/ds4-cotenancy-start.pid')"
  echo "waiting for API on ${HEAD}:8888 (up to ${WAIT_DS4_SEC}s)..."
  deadline=$((SECONDS + WAIT_DS4_SEC))
  ok=0
  while (( SECONDS < deadline )); do
    if curl -sf -m 3 "http://${HEAD}:8888/v1/models" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 10
  done
  if [ "$ok" != "1" ]; then
    echo "ERROR: DS4 did not become healthy in time" >&2
    ssh "$HEAD_SSH" 'tail -80 /tmp/ds4-cotenancy-start.log; docker ps -a | head -20' || true
    exit 1
  fi
  curl -sS "http://${HEAD}:8888/v1/models" | head -c 500; echo
  say "DS4 is serving"
else
  say "3/5 SKIP_DS4=1 — assuming already up"
fi

if [ "$SKIP_H3" != "1" ]; then
  if [ "$ENHANCE_H3" = "1" ] && [ -x "$ROOT/setup_h3_enhanced.sh" ]; then
    say "4a/5 ensure heretic TE + enhanced H3 nodes (Sage/Sol/Spectrum)"
    # setup restarts Comfy; launch_h3_dual also restarts — OK
    bash "$ROOT/setup_h3_enhanced.sh" || echo "WARN: setup_h3_enhanced had issues (continuing)"
  else
    say "4/5 launch MiniMax H3 Comfy on each node (after DS4)"
    bash "$ROOT/launch_h3_dual.sh"
  fi
else
  say "4/5 SKIP_H3=1"
fi

say "5/5 status"
bash "$ROOT/status.sh"
echo
echo "Endpoints (STACK=$STACK):"
echo "  DS4 OpenAI API : http://${HEAD}:8888/v1   (expect ${SERVED_HINT})"
echo "  H3 Comfy .2    : http://${HEAD}:8188      (heretic TE, concurrency arm A)"
echo "  H3 Comfy .3    : http://${WORKER}:8188    (heretic TE, concurrency arm B)"
echo "  H3 fleet concurrency = 2 (one heavy job per node)"
echo
echo "Quality dual-H3 10s video:"
echo "  bash $ROOT/run_quality_parallel.sh"
echo "  H3_I0_REF=/path/to/face.png bash $ROOT/run_quality_parallel.sh"
echo
echo "Teardown: bash $ROOT/teardown.sh"
