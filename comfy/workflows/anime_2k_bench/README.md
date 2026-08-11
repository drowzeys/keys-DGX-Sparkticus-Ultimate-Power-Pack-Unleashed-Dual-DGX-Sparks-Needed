# Workflow: Anime 2K bench (dual-Spark parallel + ESRGAN)

**Ship path for “2K” MiniMax-H3 on open weights:** render at a legal native size,
then **RealESRGAN ×2**. Open H3 does **not** do true native 2K in one pass
(cloud MiniMax API can; local int8 convrot stacks cannot).

| Stage | Resolution | Notes |
|-------|------------|--------|
| Native denoise | **704×1280** | Multiple of 32 (720×1280 fails) |
| Span graph | FL2VA short spans | master-K0 parallel on 2 Sparks |
| Delivery “2K” | **~1408×2560** | Inline **RealESRGAN_x2plus** on spans |
| Length class | ~5s (4 KF → 3 spans × 39f) | Bench plan; scale plan for longer |

Dual-serve co-tenancy foundation:
**[@tonyd2wild / ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)**.

---

## Quality stack (required on both Comfy installs)

| Layer | Setting |
|-------|---------|
| TE | **Heretic** `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` |
| Sage | `PathchSageAttentionKJ` (`auto`) — **never** CLI `--use-sage-attention` |
| Sol | `SolAttnPatch` + Triton SM121 |
| Spectrum | **v0.2.1** · `offline_smoothing_replay=true` · `audio_blend_weight=0` (**A/V fix**) |
| FBC | `H3FirstBlockCache` |
| Motion / chain | Motion Context + **Contex-Loop** + **MultiRef** (install + restart) |
| Upscale | RealESRGAN ×2 on **spans** |
| Realism (optional) | LoRA `h3-realism-people-t2v-i2v-r2v.safetensors` · trigger `r34l1sm` |
| Turbo | **OFF** for quality |

Details: [docs/H3_UPGRADES_2K.md](../../../docs/H3_UPGRADES_2K.md) · [docs/H3_QUALITY_STACK.md](../../../docs/H3_QUALITY_STACK.md)

---

## One-shot run

```bash
# Power Pack dual H3 up (example live pair .1 + .5)
export HEAD=10.100.10.1 WORKER=10.100.10.5
bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh
# default UPSCALE_MODE=async  →  h3-spans.py --upscale-async

# classic lab pair
HEAD=10.100.10.2 WORKER=10.100.10.3 bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh

# with Realism-People LoRA (file must be in Comfy models/loras/ on both nodes)
REALISM=1 bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh

# upscale modes
UPSCALE_MODE=async  bash …/run_anime_2k_bench.sh   # default — Claude upgrade
UPSCALE_MODE=inline bash …/run_anime_2k_bench.sh   # ESRGAN inside span graph
UPSCALE_MODE=none   bash …/run_anime_2k_bench.sh   # native only

# reuse prior keyframes (skip KF gen)
REUSE_KF=~/Videos/h3-benchmark/spans-anime2k/0811_012837_kf*.png \
  bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh
```

Outputs: `~/Videos/anime_2k_bench/{runid}_final.mp4` (+ span + `_x2` clips when async)

### Why `--upscale-async` (Claude upgrade)

| Mode | Memory under DS4 co-tenant | Wall |
|------|----------------------------|------|
| **async** (default) | Spans stay native; ESRGAN runs as free capacity appears | Upscale overlaps remaining spans; only last ×2 on critical path |
| inline `--upscale` | ESRGAN in same graph as denoise | Higher peak UMA |
| none | Native only | Fastest, not delivery 2K |

Standalone single-clip helper: `comfy/upscale2k.py` · graph `graphs/upscale-async-api.json`

---

## Proven samples (keyspark lab 2026-08-11)

### A) Native parallel (no async x2) — `0811_012837`

| Field | Value |
|-------|--------|
| Nodes | `.1` + `.5` co-tenant DS4 |
| Native | **704×1280** · master-parallel · 3 spans |
| Wall | **~18.8 min** |
| Sample | [sample/0811_012837_final_704x1280.mp4](./sample/0811_012837_final_704x1280.mp4) |

### B) **Async upscale 2K** — `0811_072314` (Claude upgrade)

| Field | Value |
|-------|--------|
| Mode | parallel spans + **async ESRGAN×2** |
| Delivery | **~1408×2560** (×2 on spans, then stitch) |
| Wall | **~12.2 min** (reused prior KFs; spans ~10.1 min with overlapped x2) |
| x2 time | ~64–72 s / span (overlapped) |
| Sample | [sample/0811_072314_final_1408x2560_async.mp4](./sample/0811_072314_final_1408x2560_async.mp4) |
| Log | [sample/0811_072314_async_run.log](./sample/0811_072314_async_run.log) |

---

## Files

| Path | Role |
|------|------|
| `anime_2k_plan.json` | Identity + 4 KF + 3 span motions / audio beds |
| `run_anime_2k_bench.sh` | Dual-node launcher |
| `graphs/jc-noupscale-api.json` | KF graph (native, Spectrum audio fix) |
| `graphs/jc-baseline-workflow-api.json` | Span graph + ESRGAN×2 + full stack |
| `graphs/*-realism.json` | Same + Realism-People LoRA |
| `graphs/h3-fullstack-realism-base.json` | Continuous short T2VA + LoRA (smoke / people) |
| `scripts/h3-spans.py` | Master-K0 parallel engine |
| `sample/` | Lab final + KF0 still + run log |

---

## Weights users must install (not redistributed)

| Asset | Typical path under ComfyUI |
|-------|----------------------------|
| FL2VA int8 convrot | `models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` |
| Heretic TE | `models/text_encoders/H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` |
| Video + audio VAE | `models/vae/minimax_h3_*` |
| RealESRGAN ×2 | `models/upscale_models/RealESRGAN_x2plus.pth` |
| Realism LoRA (optional) | `models/loras/h3-realism-people-t2v-i2v-r2v.safetensors` |

---

## Co-tenancy / RAM laws

- With DS4 co-resident: short spans (this plan uses **39f**); keep ≤**73f** with ESRGAN.
- One heavy job per Spark (`H3_FLEET_CONCURRENCY=2`).
- Do **not** one-shot continuous multi-hundred-frame gens under full dual-serve load.

## A/V glitch checklist

1. Spectrum **v0.2.1** loaded  
2. Graph has `offline_smoothing_replay=true`, `audio_blend_weight=0`  
3. For multishot seams: Motion Context / Contex-Loop after Comfy restart  
4. `H3_TURBO=0`
