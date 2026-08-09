#!/usr/bin/env bash
set -euo pipefail
HEAD="${HEAD:-10.100.10.2}"
WORKER="${WORKER:-10.100.10.3}"
PORT_DS4="${VLLM_PORT:-8888}"
PORT_H3="${H3_PORT:-8188}"

echo "=== dual-boot status (.2/.3) DS4-0731 + MM-H3  concurrency=2 ==="
echo
echo "DS4  .2:${PORT_DS4}"
if curl -sf -m 3 "http://${HEAD}:${PORT_DS4}/v1/models" >/tmp/ds4_models_status.json 2>/dev/null; then
  python3 -c "import json; d=json.load(open('/tmp/ds4_models_status.json')); print('  OK models:', [m.get('id') for m in d.get('data',[])])" 2>/dev/null \
    || { head -c 400 /tmp/ds4_models_status.json; echo; }
else
  echo "  DOWN"
fi
echo "H3   .2:${PORT_H3}"
curl -sf -m 3 "http://${HEAD}:${PORT_H3}/system_stats" | python3 -c \
  "import sys,json; s=json.load(sys.stdin); print(f\"  OK ram_free={s['system']['ram_free']/1e9:.1f}G\")" 2>/dev/null \
  || echo "  DOWN"
echo "H3   .3:${PORT_H3}"
curl -sf -m 3 "http://${WORKER}:${PORT_H3}/system_stats" | python3 -c \
  "import sys,json; s=json.load(sys.stdin); print(f\"  OK ram_free={s['system']['ram_free']/1e9:.1f}G\")" 2>/dev/null \
  || echo "  DOWN"
echo
echo "H3 queues (fleet concurrency target = 2, one job/node):"
for ip in "$HEAD" "$WORKER"; do
  curl -sf -m 2 "http://${ip}:${PORT_H3}/queue" | python3 -c \
    "import sys,json; q=json.load(sys.stdin); print(f'  {\"$ip\"}: running={len(q.get(\"queue_running\",[]))} pending={len(q.get(\"queue_pending\",[]))}')" 2>/dev/null \
    || echo "  $ip: n/a"
done
echo
for ip in "$HEAD" "$WORKER"; do
  echo "--- $ip mem ---"
  ssh -o BatchMode=yes -o ConnectTimeout=5 "keyspark@$ip" \
    'free -h | head -2; docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | head -10; pgrep -af "main.py --listen" | head -3 || true' \
    2>/dev/null || echo "  (ssh failed)"
done
