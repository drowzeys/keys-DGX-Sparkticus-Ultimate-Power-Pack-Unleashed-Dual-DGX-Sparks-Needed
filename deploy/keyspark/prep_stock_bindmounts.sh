#!/usr/bin/env bash
# Ensure stock 0731 is visible inside docker HF_CACHE mounts.
# Symlinks that point outside the mount root are invisible to containers;
# use bind mounts instead.
set -euo pipefail
HEAD="${HEAD:-spark-7552}"
WORKER="${WORKER:-spark-0060}"

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
