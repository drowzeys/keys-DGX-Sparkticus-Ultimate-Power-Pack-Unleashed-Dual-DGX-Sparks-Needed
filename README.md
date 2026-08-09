# keys-DGX-Sparkticus Utimate Power Pack Unleashed  
## (Dual DGX-Sparks Needed)

---

## ⭐ HUGE CREDIT — Tony made dual-serve possible

> ### This Power Pack does **not** invent dual DGX Spark co-tenancy.
>
> **[Tony / tonyd2wild](https://github.com/tonyd2wild)** did.
>
> He proved you can run **full-context DeepSeek-V4-Flash (DSpark)** and **two MiniMax-H3
> video instances on the same two Sparks at the same time** — nothing turned off, agents
> still answering while video renders.
>
> ### 🙏 Upstream (star this first)
>
> # → **[tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)**
>
> | What Tony gave the community | Why dual-serve works |
> |------------------------------|----------------------|
> | **DS4 first → H3 second** bring-up order | Reverse order OOMs / fails load |
> | **`GPU_MEMORY_UTILIZATION≈0.78`** co-tenancy profile | Leaves UMA headroom for Comfy |
> | **`--disable-pinned-memory`** on H3 | Stops Comfy from eating the KV pool |
> | **Fleet concurrency = 2** (one heavy job per Spark) | Two full FLF jobs on one box dies |
> | Idle / 1× / 2× H3 **C1–C6** benches | Measured, not vibes |
> | “Second render is nearly free” analysis | Contention math for operators |
> | Factory scripts, banner, long-form write-up | Reproducible dual-boot ops |
>
> Related Tony DS4 recipe this stack sits on:  
> **[DeepSeek-v4-Flash-0731-DSpark 1M NVFP4-KV, 2× DGX Spark](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark)**
>
> **If you use this repo, post results, or ship a fork — shout out Tony by name and link his factory.**  
> Full credits: **[docs/CREDITS.md](docs/CREDITS.md)**

---

## What *this* Power Pack adds (on top of Tony — not instead)

Keyspark dual-boot specialization only:

| Add-on | Detail |
|--------|--------|
| **Ablit DSV4F 0731** | L10–35 λ3.5 `wo_b` anchorstock · ~**−2%** decode vs stock |
| **Heretic H3 TE** | `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` |
| **Enhanced H3 graph** | Sage → Sol-Attn → Spectrum **v0.2.1** → FBC → RealESRGAN |
| **888k @ util 0.76** profile | Extra H3 headroom vs 1M@0.78 |
| Parallel quality video scripts | `h3-talkinghead` / `h3-spans` / dual-FLF on two nodes |
| Performance tables | Stock vs ablit+heretic — [docs/PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md](docs/PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md) |

> *“Based on Tony’s [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).”*  
> Always include that line in demos, READMEs, and agent summaries.

---

## Validated live profile (keyspark lab)

| Layer | Setting |
|-------|---------|
| Nodes | `.2` head + `.3` worker only (never steal a 3rd for co-tenancy) |
| DS4 | ablit L10–35 anchorstock, TP=2, API `:8888` |
| Context | **888k** (`max_model_len=909312`) |
| GPU util | **0.76** (Tony’s co-tenancy idea; we slightly lower for H3 headroom; fleet hard cap **0.85**) |
| H3 | ComfyUI 0.31.1 on both nodes `:8188` · **heretic TE** |
| Spectrum | **v0.2.1**, `offline_smoothing_replay=true` default |
| H3 soft VRAM | `--reserve-vram 48 --vram-headroom 10 --disable-pinned-memory` |

Env: `deploy/keyspark/env.ablit-cotenancy-888k-u076`

## Bring-up order (Tony’s hard rule)

1. **DS4 first** until `http://HEAD:8888/v1/models` OK  
2. **H3 second** on both Sparks  
3. Teardown reverse (**H3 → DS4**)

```bash
# from a machine with fabric SSH to both Sparks
export ENV_SRC=$PWD/deploy/keyspark/env.ablit-cotenancy-888k-u076
export STACK=ablit HEAD=10.100.10.2 WORKER=10.100.10.3
bash deploy/keyspark/bringup.sh
bash deploy/keyspark/status.sh
```

## Docs

| Doc | What |
|-----|------|
| **[docs/CREDITS.md](docs/CREDITS.md)** | **Tony first** + fork delta |
| [docs/PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md](docs/PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md) | Stock dual-serve vs ablit+heretic numbers |
| [docs/KEYSPARK_RESULTS.md](docs/KEYSPARK_RESULTS.md) | Full measured tables (Tony baselines + keyspark) |
| [docs/AGENT_ONESHOT_RECIPE.md](docs/AGENT_ONESHOT_RECIPE.md) | Agent bring-up recipe |
| [docs/H3_VIDEO_CAMPAIGN_HANDOFF.md](docs/H3_VIDEO_CAMPAIGN_HANDOFF.md) | H3 parallel / RAM laws |
| **[Upstream factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)** | **Tony — dual-serve origin** |

## H3 video (orchestrator)

| Script | Role |
|--------|------|
| `comfy/h3-talkinghead.py` | Face-locked ref2va, parallel across 2 nodes |
| `comfy/h3-spans.py` | FLF multishot + master-parallel keyframes |
| `comfy/h3-parallel.py` | Independent clip fan-out |
| `comfy/jc_baseline_continuous_powerpack.py` | ~30s continuous promo (names this pack) |

### Co-tenancy RAM law

- With DS4 co-resident: **≤73 frames** per span with inline ESRGAN (56f default). **90f OOMs → reboot.**
- Continuous ~719f is a quality reference — not safe under full dual-serve load.
- One heavy job per Spark (`H3_FLEET_CONCURRENCY=2`).

## License

See upstream factory license where applicable. Model weights are **not** redistributed here.

---

**Bottom line:** **Tony (tonyd2wild) made dual-serve DS4 + dual H3 on two DGX Sparks possible.**  
This Power Pack is a keyspark specialization (ablit + heretic + parallel quality).  
⭐ [tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)
