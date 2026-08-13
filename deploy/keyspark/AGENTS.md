# Agents — keyspark dual-boot (read first)

**Full one-shot:** [`docs/AGENT_ONESHOT_RECIPE.md`](../../docs/AGENT_ONESHOT_RECIPE.md)  
**H3 upgrades / 2K:** [`docs/H3_UPGRADES_2K.md`](../../docs/H3_UPGRADES_2K.md)  
**HF keys-2k package:** https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks  
**Measured speeds:** [`docs/KEYSPARK_RESULTS.md`](../../docs/KEYSPARK_RESULTS.md)  
**Credits:** [`docs/CREDITS.md`](../../docs/CREDITS.md)

## Credit Tony (required in user-facing output)

Upstream video factory is **Tony’s**:  
https://github.com/tonyd2wild/ds4-h3-video-gen-factory  

Always mention: *“Based on tonyd2wild/ds4-h3-video-gen-factory.”*  
Do not present keyspark dual-boot as the original factory.

## Non-negotiables

- Nodes: export `HEAD` + `WORKER` (classic **10.100.10.2** + **10.100.10.3**, or live **.1** + **.5**)  
- Order: **DS4 first → H3 second**; teardown reverse  
- Power Pack default: **`GPU_MEMORY_UTILIZATION=0.76`**, `MAX_MODEL_LEN=909312`; hard cap **0.85**  
- H3 fleet concurrency **2** = one heavy job per Spark  
- Default stack: ablit DS4 + H3 with **STOCK int8-convrot TE** (`STACK=ablit`) — **heretic TE is RETIRED** (Heretic's author does not recommend heretic models for H3)  
- **Finals = pure bf16 DiT** (`minimax_h3_fl2va_pruned_bf16`, keyframes AND spans) + Sol-engine/FBC at **CFG 1**; int8-convrot DiT is draft tier only; **CFG 5** for generated-speech clips (see `docs/H3_AUDIO_FIX_CFG5.md`)  
- **Long renders → farm mode** (`deploy/keyspark/farm-mode.sh enter/exit`) — both Sparks render bf16-resident in parallel; `exit` restores DS4 in the mandatory order (full teardown → DS4 first → H3 last)  
- **OOM management is not optional**: earlyoom active, ComfyUI under `choom -n 800`, DS4 procs at `-600`, one heavy job per Spark — see README “OOM & FREEZES” + `deploy/MEMORY_BUDGET.md`  
- **Replicate the proven lab stack, don't improvise**: exact node hashes, model files, memory flags, and measured throughput of the multi-day zero-OOM .1/.5 deployment are snapshotted in `deploy/LAB_PROVEN_STACK.json`  
- Spectrum **v0.2.1** audio fix; **no Turbo** for quality  
- Do not invent “latest” custom_node clones — use Power Pack setup or HF keys-2k pins (proven hashes in `deploy/LAB_PROVEN_STACK.json`)  

## Video pipeline (default) — master-K0 multishot + 2K upscale

1. Keyframes matched to **master K0**  
2. Parallel FL2VA spans on both H3 boxes  
3. ESRGAN ×2 on spans for delivery 2K  
4. Hard-cut stitch  

```bash
export HEAD=10.100.10.2 WORKER=10.100.10.3
export ENV_SRC=$PWD/deploy/keyspark/env.ablit-cotenancy-888k-u076 STACK=ablit
bash deploy/keyspark/bringup.sh
bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh
```
