#!/usr/bin/env bash
# Render-farm mode: trade the DS4 serve for full-node H3 rendering (bf16 resident).
#
#   bash farm-mode.sh enter   # stop H3+DS4, relaunch H3 with the whole node
#   bash farm-mode.sh exit    # ORDERED restore: everything down, DS4 first, H3 after
#
# The exit ordering is load-bearing: DS4's vLLM worker profiles memory at startup
# and CRASHES (WorkerProc init failure) if the H3 co-tenant still holds models —
# even after a ComfyUI /free. Full teardown before bringup is the only reliable path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
ENV_SRC="${ENV_SRC:-$ROOT/env.ablit-cotenancy}"

case "${1:-}" in
  enter)
    HEAD="$HEAD" WORKER="$WORKER" bash "$ROOT/teardown.sh"
    FARM_MODE=1 HEAD="$HEAD" WORKER="$WORKER" bash "$ROOT/launch_h3_dual.sh"
    echo "FARM MODE ACTIVE: both nodes free for bf16-resident rendering."
    echo "Restore with: bash $0 exit"
    ;;
  exit)
    HEAD="$HEAD" WORKER="$WORKER" bash "$ROOT/teardown.sh"
    HEAD="$HEAD" WORKER="$WORKER" ENV_SRC="$ENV_SRC" STACK="${STACK:-ablit}" ENHANCE_H3=0 \
      bash "$ROOT/bringup.sh"
    ;;
  *)
    echo "usage: $0 enter|exit" >&2; exit 2 ;;
esac
