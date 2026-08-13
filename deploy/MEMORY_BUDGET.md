# Memory budget: DSV4F-0731 + dual H3 co-tenancy without OOM

The Power Pack's pinned profile (`GPU_MEMORY_UTILIZATION=0.76`, H3 `--reserve-vram 48
--vram-headroom 10 --disable-pinned-memory`) is tuned for **headless GB10 nodes with a
5–8 GB system reserve**. If your head node runs a desktop session, browsers, or other
services, the same numbers WILL OOM — the co-tenants are budgeted to within a few GB of
the 121 GB unified pool. Budget explicitly:

## The accounting (per 121 GB GB10 node)

```
121 GB total
  - SYSTEM reserve         (5–8 headless, 10–15 light desktop, 15–20 full desktop)
  - vLLM (DSV4F)           = 121 x GPU_MEMORY_UTILIZATION   (weights + KV + graphs)
  = what remains for H3    (model streams via partial loading; ~20–30 GB workable,
                            less means slower renders, ~<10 GB means OOM kills)
```

## Recommended profiles

| Head profile | System reserve | `GPU_MEMORY_UTILIZATION` | `MAX_MODEL_LEN` | H3 flags |
|---|---|---|---|---|
| Headless (lab default) | 5–8 GB | **0.76** | 909312 (888k) | `--reserve-vram 48 --vram-headroom 10` |
| Light desktop / few services | 10–15 GB | **0.72** | ~700k | same |
| Full desktop (GUI, browser) | 15–20 GB | **0.66–0.68** | ~500k | `--reserve-vram 52 --vram-headroom 12` |

Rules of thumb:
- Every extra GB of system reserve comes out of vLLM's share first: drop
  `GPU_MEMORY_UTILIZATION` by ~0.01 per GB beyond the headless baseline.
- Never exceed **0.85** util (fleet hard cap); never start H3 before DS4 is healthy.
- If DS4 fails its KV budget at your context length, reduce `MAX_MODEL_LEN` before
  raising util.
- One heavy H3 job per Spark under co-tenancy, always.

## Topology: orchestrate from a THIRD machine (the biggest free win)

Run the drivers (`h3-spans-v2.py`, `h3-scenes-driver.py`), audio slicing, ffmpeg
stitching/previews, and contact-sheet work on a box that is NOT a render node — a head
node, a workstation, anything. The scripts talk to the render pair purely over the
ComfyUI HTTP API, so orchestration adds **zero** memory cost where it hurts. This is how
the reference lab runs (drivers on a third Spark; the render pair carries only
DS4 + H3): with that split plus the pinned profile, OOM events drop to the occasional
transient spike that the victim-priority system absorbs. If you MUST orchestrate on a
render node, count its ffmpeg encodes (1–4 GB peaks) into the system reserve row above.

## OOM protection (install once per render node — strongly recommended)

Even a correct budget gets transient spikes. Make the RENDER the designated victim so
the LLM serve never dies:

```bash
sudo apt-get install -y earlyoom && sudo systemctl enable --now earlyoom
# ComfyUI as preferred OOM victim (the Power Pack launcher already does this via choom):
#   launch_h3_dual.sh starts ComfyUI under `choom -n 800`
# Optionally protect the DS4 container explicitly:
for pid in $(docker top $(docker ps -q --filter name=vllm-dspark) -eo pid | tail -n +2); do
  echo -600 | sudo tee /proc/$pid/oom_score_adj >/dev/null
done
```

With earlyoom + victim priorities, an over-budget spike kills one span render (which
`h3-spans-v2.py` retries automatically and `h3-scenes-driver.py` survives) instead of
panicking the node or killing DSV4F. Expect the occasional kill under long renders —
that is the system working as designed. A self-healing relaunch loop for ComfyUI is
cheap insurance on long runs:

```bash
while true; do
  curl -sf -m 4 http://NODE:8188/system_stats >/dev/null || \
    ssh NODE 'cd ~/h3-cotenancy && (nohup ./h3-comfy-launch.sh > logs/comfyui.log 2>&1 &)'
  sleep 120
done
```

## Measured: the co-tenancy tax (same scene, same settings, 2026-08-12)

158-frame span at 864x480, CFG 5, int8 TE, identical prompts:

| Renderer | Per-span |
|---|---|
| GB10 solo (no DS4 co-tenant, everything resident) | **~5.2 min** |
| GB10 under DS4 co-tenancy (partial-loading, reserve-vram 48) | ~8.8 min (+70%) |
| Mac Studio M3 Ultra, native h3.c (serial, guidance-free) | ~16.6 min |

Render-farm mode: for long productions, PAUSE the DS4 serve during the render window
(`deploy/keyspark/teardown.sh` / bringup are two commands) — a freed pair renders at
solo speed x2 nodes, roughly 3x the co-tenant throughput. Resume DS4 after.
