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
- Default stack: ablit DS4 + heretic H3 (`STACK=ablit`)  
- Spectrum **v0.2.1** audio fix; **no Turbo** for quality  
- Do not invent “latest” custom_node clones — use Power Pack setup or HF keys-2k pins  

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
