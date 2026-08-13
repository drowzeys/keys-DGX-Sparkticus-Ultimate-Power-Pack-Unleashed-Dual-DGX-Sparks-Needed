#!/usr/bin/env bash
# Ensure serve model dirs are visible inside docker HF_CACHE mounts.
# Symlinks that point outside the mount root are invisible to containers;
# use bind mounts instead.
#
# PITFALL (cost one dead serve, 2026-08-13): deleting a node-local model copy
# while the container still holds it open works fine — until the next restart,
# when vLLM finds an empty dir (or a bind whose source shows //deleted in
# findmnt) and dies with "Invalid repository ID or local directory". bind_model
# below self-heals that: it re-binds from the surviving copy (NFS or local) and
# replaces stale binds whose source is gone.
set -euo pipefail
HEAD="${HEAD:-spark-7552}"
WORKER="${WORKER:-spark-0060}"

bind_model() {
  local host="$1" src="$2" name="$3" probe="$4"
  ssh "$host" "bash -s" <<REMOTE
set -e
src='$src'
dst=/home/keyspark/.cache/huggingface/'$name'
mkdir -p /home/keyspark/.cache/huggingface
# a populated real dir needs no bind (node-local copy)
if [ -e "\$dst/$probe" ] && ! mountpoint -q "\$dst" 2>/dev/null; then
  echo "\$HOSTNAME: \$dst already populated (local copy)"
  exit 0
fi
# stale bind: mounted but the probe file is unreachable (source deleted)
if mountpoint -q "\$dst" 2>/dev/null; then
  if [ -e "\$dst/$probe" ]; then
    echo "\$HOSTNAME: already bind-mounted"
    exit 0
  fi
  echo "\$HOSTNAME: stale bind on \$dst (source gone) — remounting"
  sudo -n umount "\$dst" 2>/dev/null || sudo -n umount -l "\$dst"
fi
if [ -L "\$dst" ]; then rm -f "\$dst"; fi
if [ -d "\$dst" ] && [ -z "\$(ls -A "\$dst" 2>/dev/null)" ]; then rmdir "\$dst"; fi
mkdir -p "\$dst"
if [ ! -e "\$src/$probe" ]; then
  echo "\$HOSTNAME: missing model source \$src" >&2
  exit 1
fi
sudo -n mount --bind "\$src" "\$dst"
echo "\$HOSTNAME: bound \$src -> \$dst"
ls "\$dst/$probe" >/dev/null
REMOTE
}

bind_stock() {
  local host="$1" src="$2"
  ssh "$host" "bash -s" <<REMOTE
set -e
src='$src'
dst=/home/keyspark/.cache/huggingface/dsv4f-0731-stock
mkdir -p /home/keyspark/.cache/huggingface
if mountpoint -q "\$dst" 2>/dev/null; then
  echo "\$HOSTNAME: already bind-mounted"
  exit 0
fi
# replace symlink/empty dir
if [ -L "\$dst" ]; then rm -f "\$dst"; fi
if [ -d "\$dst" ] && [ -z "\$(ls -A "\$dst" 2>/dev/null)" ]; then rmdir "\$dst"; fi
mkdir -p "\$dst"
if [ ! -d "\$src" ]; then
  echo "\$HOSTNAME: missing stock source \$src" >&2
  exit 1
fi
sudo -n mount --bind "\$src" "\$dst"
echo "\$HOSTNAME: bound \$src -> \$dst"
ls "\$dst"/model-00001-of-00048.safetensors >/dev/null
REMOTE
}

bind_stock "$HEAD"   /home/keyspark/models-local/DeepSeek-V4-Flash-0731
bind_stock "$WORKER" /home/keyspark/models/DeepSeek-V4-Flash-0731

# Abliterated anchorstock (the 888k serve's model). On the lab head the local
# copy was reclaimed for disk space — ~/models is an NFS export from the
# orchestrator node, which is exactly the surviving copy we bind from. The
# worker keeps a real local copy, so bind_model no-ops there.
bind_model "$HEAD"   /home/keyspark/models/dsv4f-0731-ablit-l10-35-anchorstock \
  dsv4f-0731-ablit-l10-35-anchorstock config.json
bind_model "$WORKER" /home/keyspark/models/dsv4f-0731-ablit-l10-35-anchorstock \
  dsv4f-0731-ablit-l10-35-anchorstock config.json
