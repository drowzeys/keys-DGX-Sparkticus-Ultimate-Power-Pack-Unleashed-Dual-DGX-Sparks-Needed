# Keyspark fleet bring-up — DS4-0731 DSpark + MiniMax H3 dual

## 🙏 Shout-out — Tony’s original Video Gen Factory

This keyspark deploy tree **maps and extends**  
**[tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)**  
by **[Tony (tonyd2wild)](https://github.com/tonyd2wild)**.

Tony owns the core idea: two MiniMax H3 instances co-tenant with full-context
DeepSeek-V4-Flash on two DGX Sparks — DS4-first start order, util 0.78,
`--disable-pinned-memory`, and the idle / 1× / 2× H3 co-residency benches.

**Please star and credit the upstream factory** when you use these scripts.  
Full credits: [docs/CREDITS.md](../../docs/CREDITS.md).

Maps Tony’s factory onto this lab pair:

| Role | Host | Fabric | Mgmt |
|------|------|--------|------|
| DS4 head + H3 #1 | spark-7552 | **10.100.10.2** (`.2`) | 192.168.0.101 |
| DS4 worker + H3 #2 | spark-0060 | **10.100.10.3** (`.3`) | 192.168.0.100 |

Never use `.1` / gx10-5482 for this stack.

## Dual-boot profile (default)

| Layer | What | Where |
|-------|------|--------|
| **DS4 ablit** | `deepseek-v4-flash-0731-ablit-l10-35-anchorstock` TP=2 util **0.78** | `.2:8888` head + `.3` worker |
| **H3 heretic** | ComfyUI 0.30.1 + heretic TE + Sage/Sol/Spectrum/FBC | `.2:8188` + `.3:8188` |
| **H3 concurrency** | **2** = one heavy job per node, both nodes at once | fleet, not 2 jobs/GPU |

```
                    ┌─────────────────────────────────────┐
  Hermes / apps ──► │  DS4 ablit OpenAI  .2:8888/v1       │  prompts / chat
                    └─────────────────────────────────────┘
  video client  ──► │  H3 .2:8188  ║  H3 .3:8188          │  concurrency=2
                    │  arm A       ║  arm B               │
                    └─────────────────────────────────────┘
```

Quality video path — **FLF multishot** (Hermes architecture, default):

Engine: `multishot_flf.py` · runner: `keyframe_dual_flf.py` / `run_quality_parallel.sh`

1. **Phase 0** sequential quality **keyframes** K0…KN on `.2` (optional `H3_I0_REF` face lock; natural skin ON)
2. **Phase 1** parallel motion arms (concurrency=2): arm_i **first=K_i last=K_{i+1}** on `.2` ‖ `.3`
   — previous segment’s last image **is** the next segment’s first image (shared PNG)
3. **Phase 2** **hard-cut** concat (no xfade) → continuous by construction

Longer stories: `connelly_flf_20s.py` / `connelly_flf_30s.py` (same engine pattern, more arms).

## Critical co-tenancy rules (from Tony)

1. **Start DS4 first.** Wait until `/v1/models` answers and logs show ~1.47M KV tokens.
2. **Then start H3** on each node. Reverse order → H3 takes ~50 GiB and DS4 cannot load.
3. **`GPU_MEMORY_UTILIZATION=0.78`** — do not lower for video; that collapses the KV pool. Cap is **0.85** fleet-wide (hard).
4. H3: **`--disable-pinned-memory`** (no `--reserve-vram` while co-tenanting).
5. To restart DS4: stop H3 first (`teardown.sh` does this order).
6. **Never** two full FLF jobs on one Spark; concurrency=2 means **two boxes**.

## Quick start

```bash
ROOT=~/ds4-h3-video-gen-factory/deploy/keyspark

# full dual-boot: ablit DS4 + heretic H3 (default STACK=ablit)
bash $ROOT/bringup.sh

# stock 0731 instead of ablit
STACK=stock bash $ROOT/bringup.sh

# DS4 only / H3 only
SKIP_H3=1 bash $ROOT/bringup.sh
SKIP_DS4=1 bash $ROOT/bringup.sh

# status / stop
bash $ROOT/status.sh
bash $ROOT/teardown.sh

# quality-first dual-H3 ~10s video (needs stack up)
bash $ROOT/run_quality_parallel.sh
H3_I0_REF=~/Videos/hp_dragon_dual/harry_potter_dragon_hogwarts_10s.mp4 \
  bash $ROOT/run_quality_parallel.sh
```

## Endpoints

| Service | URL |
|---------|-----|
| DS4 OpenAI API | `http://10.100.10.2:8888/v1` |
| served model (ablit) | `deepseek-v4-flash-0731-ablit-l10-35-anchorstock` |
| served model (stock) | `deepseek-v4-flash-0731` |
| H3 ComfyUI `.2` | `http://10.100.10.2:8188` |
| H3 ComfyUI `.3` | `http://10.100.10.3:8188` |

## Config files

| File | Role |
|------|------|
| `env.ablit-cotenancy` | **Default dual-boot** — ablit weights util 0.78 |
| `env.cotenancy` | Stock 0731 co-tenancy |
| `profile.ablit-heretic-dual.env` | Env for video jobs (quality + concurrency=2) |
| `keyframe_dual_flf.py` | Quality-first parallel dual-FLF pipeline |
| `run_quality_parallel.sh` | One-shot runner + preflight |
| `setup_h3_enhanced.sh` | Heretic TE + Spectrum/Sol/Sage on both nodes |
| `hp_dragon_dual.py` | Sequential dual (best seam; ~2× wall) |

- DS4 recipe tree: `~/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731` (Anemll `ghcr.io/anemll/dspark-vllm-gx10:0.1.1`)
- Ablit weights: `~/.cache/huggingface/dsv4f-0731-ablit-l10-35-anchorstock`
- H3 tree: `~/h3-cotenancy` on each node (ComfyUI v0.30.1 + heretic TE)

## Bench (Tony)

```bash
# DS4 concurrency (text)
python3 ~/ds4-h3-video-gen-factory/bench/bench_conc.py \
  10.100.10.2:8888 deepseek-v4-flash-0731-ablit-l10-35-anchorstock idle 1,2,3,4,5,6

# H3 fleet = 2 concurrent video arms (see run_quality_parallel.sh)
```
