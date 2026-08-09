# Credits & shout-outs

## Tony — original DS4 × H3 Video Gen Factory

**This project is a keyspark fork of Tony’s work. Full credit for the video factory
goes to [tonyd2wild](https://github.com/tonyd2wild).**

| | |
|--|--|
| **Upstream repo** | **[tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)** |
| **Author** | [Tony (tonyd2wild)](https://github.com/tonyd2wild) |

Tony’s factory is the foundation of everything here:

- Dual MiniMax H3 on two DGX Sparks **alongside** full 1M-context DeepSeek-V4-Flash  
- The **DS4-first, then H3** co-tenancy rule (and why reverse order fails)  
- `GPU_MEMORY_UTILIZATION=0.78` profile, `--disable-pinned-memory`, no fake “video mode”  
- Co-tenancy benches: DS4 alone / +1 H3 render / +2 H3 renders (C1–C6)  
- The long-form write-up, banner, and “second render is nearly free” analysis  
- The idea that agents keep answering while video runs  

If you use this fork, **star and credit the upstream**:

→ https://github.com/tonyd2wild/ds4-h3-video-gen-factory

### Related Tony recipes (DS4 base)

- [DeepSeek-v4-Flash-0731-DSpark 1M NVFP4-KV, 2x DGX Spark](https://github.com/tonyd2wild/DeepSeek-v4-Flash-0731-DSpark-1M-NVFP4-KV-2x-DGX-Spark) — DS4 deployment this stack sits on  

## What this keyspark fork adds (not a replacement)

Extensions **on top of** Tony’s factory, not instead of it:

- Abliterated DSV4F 0731 dual-boot env (`env.ablit-cotenancy`)  
- Heretic TE + enhanced H3 graph (Sage / Sol / Spectrum / FBC / RealESRGAN)  
- Quality-first parallel dual-FLF video path (`deploy/keyspark/`)  
- Agent one-shot recipe + published pre/post speed tables for this lab  

## Other components (as used)

| Piece | Credit |
|-------|--------|
| DeepSeek-V4-Flash / DSpark serving | DeepSeek + Anemll DSpark image / lab recipes Tony and others publish |
| MiniMax H3 | MiniMax |
| Heretic TE / Sol-Engine / Spectrum / SolAttn ports | respective authors; wired here for dual-Spark heretic stack |
| ComfyUI | Comfy Org |
| **MiniMax-H3 Turbo LoRA** (few-step 4–8) | **[larryvrh/MiniMax-H3-Turbo-Lora](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora)** + **[ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo)** |
| **ComfyUI-fixed pruned Turbo weights** | **[QrusherZA/H3_Turbo_ComfyUI](https://huggingface.co/QrusherZA/H3_Turbo_ComfyUI)** (prefix/adaln fix for pruned bases; QrusherZA asks not to take credit for the Turbo training itself) |
| **Dual-sampler Turbo quality recipe** | **[@ANe5s](https://huggingface.co/ANe5s)** — [discussion #21](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/discussions/21) (ckpt850@1.0 rough → ckpt500@0.7 refine) |
| **H3 Motion Context** (audio+motion chain) | **[NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)** |

---

**Bottom line:** Tony built the video factory and proved dual H3 + full DS4 co-tenancy.  
This fork is a keyspark dual-boot specialization (ablit + heretic + parallel quality path).  
**Always shout out Tony when you share results from this tree.**
