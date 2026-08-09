# Credits & shout-outs

---

## ⭐⭐⭐ PRIMARY CREDIT — Tony (tonyd2wild)

# Dual-serve exists because of Tony.

**[Tony / tonyd2wild](https://github.com/tonyd2wild)** designed, measured, and published the
**dual DGX Spark co-tenancy factory**: full-context DeepSeek-V4-Flash **and** two MiniMax-H3
ComfyUI instances on the **same two boxes**, at the same time, with agents still usable.

### Star & cite first

| | |
|--|--|
| **Upstream factory** | **https://github.com/tonyd2wild/ds4-h3-video-gen-factory** |
| **Author** | **[tonyd2wild](https://github.com/tonyd2wild)** (Tony) |
| **DS4 0731 2× Spark recipe** | [DeepSeek-v4-Flash-0731-DSpark 1M NVFP4-KV 2x DGX Spark](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark) |

### What Tony made possible (do not re-attribute)

Without Tony’s factory, this Power Pack has no dual-serve spine:

1. **Co-tenancy as a product** — not “video mode” that kills the LLM, and not “LLM mode” that kills video  
2. **Hard start order:** DS4 loads first → H3 second (and teardown reverse)  
3. **Memory discipline:** util ~**0.78**, H3 **`--disable-pinned-memory`**, one heavy job per Spark  
4. **Published benches:** DS4 alone / +1 H3 render / +2 H3 renders (C1–C6) — so operators know the tax  
5. **Operator narrative:** second concurrent render is cheaper; idle H3 tax is livable; contention is real  
6. **Scripts & write-up** others (including this fork) stand on  

### Required wording (copy-paste)

Use this in READMEs, tweets, videos, and agent summaries:

> **Based on Tony’s dual-serve factory:**  
> [tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)  
> Dual DS4 + dual MiniMax-H3 on two DGX Sparks was made possible by **tonyd2wild**.

**Always shout out Tony by name when sharing results from this tree.**

---

## What this keyspark Power Pack adds (fork delta only)

These are **extensions on Tony’s dual-serve foundation**, not a replacement:

| Add-on | Credit scope |
|--------|----------------|
| Ablit DSV4F 0731 L10–35 λ3.5 anchorstock dual-boot env | keyspark / this fork |
| Heretic TE wiring + enhanced graph (Sage/Sol/Spectrum/FBC/ESRGAN) | keyspark wiring; component authors below |
| **Live serve: 888k (lucky) @ util 0.76** | keyspark — **room for H3 to shine** (Tony’s co-tenancy util discipline, deliberately lowered from ~0.78 / not pushed to 0.85) |
| Parallel quality FLF / talking-head span pool scripts | keyspark campaign scripts |
| **Master-K0 multishot parallel** (KFs matched to K0; short spans vs long-gen hallucination) | keyspark production logic — [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md) |
| Stock vs ablit+heretic performance tables | keyspark measurements + Tony baselines preserved |

If dual-serve co-tenancy is useful to you, **Tony owns that win.**

---

## Other components (as used)

| Piece | Credit |
|-------|--------|
| Dual-serve co-tenancy factory | **Tony / [tonyd2wild](https://github.com/tonyd2wild)** ⭐ |
| DeepSeek-V4-Flash / DSpark serving | DeepSeek + Anemll `dspark-vllm-gx10` + Tony’s 0731 recipes |
| MiniMax H3 | MiniMax |
| Heretic MiniMax-H3 TE (NVFP4) | [sakamakismile/Qwen3-VL-32B-Heretic-MiniMax-H3-NVFP4](https://huggingface.co/sakamakismile/Qwen3-VL-32B-Heretic-MiniMax-H3-NVFP4) (and related heretic projects) |
| Spectrum MiniMax H3 | Spectrum / ComfyUI-Spectrum-MiniMax-H3 authors |
| Sol-Attn / FBC Blackwell ports | Sol-Attn / port authors |
| ComfyUI | Comfy Org |
| MiniMax-H3 Turbo LoRA | [larryvrh/MiniMax-H3-Turbo-Lora](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora) + [ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo) |
| ComfyUI-fixed pruned Turbo weights | [QrusherZA/H3_Turbo_ComfyUI](https://huggingface.co/QrusherZA/H3_Turbo_ComfyUI) |
| Dual-sampler Turbo quality recipe | [@ANe5s](https://huggingface.co/ANe5s) [discussion #21](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/discussions/21) |
| H3 Motion Context | [NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) |

---

## Bottom line

| Role | Who |
|------|-----|
| **Made dual-serve possible** | **Tony (tonyd2wild)** |
| Specialization (ablit + heretic + parallel quality) | keyspark Power Pack |

⭐ **https://github.com/tonyd2wild/ds4-h3-video-gen-factory**
