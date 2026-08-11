# Agents — read first (Power Pack)

**Canonical one-shot:** [`docs/AGENT_ONESHOT_RECIPE.md`](docs/AGENT_ONESHOT_RECIPE.md)

## Goal

Bring up on **two** DGX Sparks:

1. **DSV4F DSpark 0731 abliterated** @ **888k** / util **0.76** → `http://HEAD:8888/v1`  
2. **Two** MiniMax-H3 **heretic** Comfy instances (full quality stack) → `HEAD:8188` + `WORKER:8188`  
3. Run **parallel master-K0** video with **ESRGAN 2K path** (`comfy/workflows/anime_2k_bench/`)

## Required links

| | |
|--|--|
| This repo | https://github.com/drowzeys/keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed |
| keys-2k H3 HF package | https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks |
| Tony dual-serve | https://github.com/tonyd2wild/ds4-h3-video-gen-factory |

## Non-negotiables

- Order: **DS4 first → H3 second**; teardown reverse  
- `GPU_MEMORY_UTILIZATION=0.76` (Power Pack default); hard cap **0.85**  
- Spectrum **v0.2.1** · `offline_smoothing_replay=true`  
- Fleet H3 concurrency **2** = one heavy job per Spark  
- **No Turbo** for quality deliverables  
- Credit Tony in every user-facing summary  

## Commands (after `HEAD`/`WORKER` exported)

```bash
export ENV_SRC=$PWD/deploy/keyspark/env.ablit-cotenancy-888k-u076 STACK=ablit
bash deploy/keyspark/bringup.sh
bash deploy/keyspark/status.sh
bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh
```

Pair override (example `.1`+`.5`): use `env.ablit-cotenancy-888k-u076-nodes-1-5`.
