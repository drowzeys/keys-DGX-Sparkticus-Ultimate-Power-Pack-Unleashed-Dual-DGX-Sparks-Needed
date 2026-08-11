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

# classic lab pair
HEAD=10.100.10.2 WORKER=10.100.10.3 bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh

# with Realism-People LoRA (file must be in Comfy models/loras/ on both nodes)
REALISM=1 HEAD=10.100.10.1 WORKER=10.100.10.5 \
  bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh
```

Outputs: `~/Videos/anime_2k_bench/{runid}_final.mp4` (+ KF pngs / span mp4s)

---

## Proven sample (keyspark lab 2026-08-11)

| Field | Value |
|-------|--------|
| Run id | `0811_012837` |
| Nodes | `.1` + `.5` (co-tenant DS4 ablit 888k @ util 0.76) |
| Native | **704×1280** · 4 KF master-parallel · 3 spans |
| Wall | **~18.8 min** (KF plan + parallel spans **8.9 min** vs ~13+ serial) |
| Span times | ~264–296 s each |
| Sample final | [sample/0811_012837_final_704x1280.mp4](./sample/0811_012837_final_704x1280.mp4) |
| Log | [sample/0811_012837_run.log](./sample/0811_012837_run.log) |

> This sample was recorded **native 704×1280**. Re-run with this package’s
> `--upscale` graphs to land **~1408×2560** delivery 2K (ESRGAN on spans).

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
