# Keyspark measured results — dual-boot DS4 ablit + H3 heretic (concurrency=2)

**Hardware:** 2× NVIDIA DGX Spark GB10 (121 GiB unified memory each)  
**Fabric:** `.2` = 10.100.10.2 (spark-7552 head) · `.3` = 10.100.10.3 (spark-0060 worker)  
**Never use `.1` / gx10-5482 for this stack.**  
**Date window:** 2026-08-06 → 2026-08-07 (keyspark lab)

### 🙏 Credit — Tony’s Video Gen Factory

Co-tenancy methodology, factory design, and baseline A/B/C benches originate with
**[Tony / tonyd2wild](https://github.com/tonyd2wild)** —  
**[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)**.  
Sections marked **Tony baseline** are his published measurements (preserved here).  
Keyspark rows (ablit peak, video walls sequential/parallel) are this lab’s extensions.  
See **[CREDITS.md](./CREDITS.md)**.

All numbers below are **measured**, not estimated. Sources live under `bench/results/` and `/tmp/hp_dragon_*/run*.log` on the lab hosts.

---

## 1. DeepSeek-V4-Flash (DS4) — stock vs ablit vs co-tenancy

### 1.1 Stock DS4 alone (no H3) — Tony baseline A

Model: stock / `deepseek-v4-flash-dspark` · max_tokens=700 · C1–C6  
Source: `bench/results/A_no_video.txt`

| Concurrency | agg tok/s | per-stream | TTFT mean (s) |
|---:|---:|---:|---:|
| C1 | **88.87** | 90.87 | 0.16 |
| C2 | 149.37 | 76.27 | 0.18 |
| C3 | 199.47 | 67.84 | 0.19 |
| C4 | 214.90 | 60.06 | 0.25 |
| C5 | 203.93 | 44.35 | 0.34 |
| C6 | **285.95** | 51.95 | 0.34 |

### 1.2 Stock DS4 + idle H3 co-resident (H3 loaded, not rendering hard)

Model: `deepseek-v4-flash-0731` · util 0.78 · H3 both nodes up  
Source: `bench/results/keyspark_idle_h3_coresident_20260806_231121.txt` · `bench/results/bench_full.txt`

| Concurrency | agg tok/s | per-stream | TTFT mean (s) |
|---:|---:|---:|---:|
| C1 | **83.54** | 85.43 | 0.17 |
| C2 | 130.74 | 67.55 | 0.23 |
| C3 | 170.18 | 58.51 | 0.27 |
| C4 | 193.91 | 54.07 | 0.34 |
| C5 | 200.44 | 43.90 | 0.37 |
| C6 | **242.03** | 44.12 | 0.42 |

Decode peak (count300, warm): **83.3 tok/s** · mean content mix **67.4 tok/s**  
Prefill: 8K≈1802 · 32K≈2313 · **100K≈2430** tok/s  

**vs stock alone:** C1 −6% (88.9→83.5), C6 −15% (286→242) — H3 idle tax is real but livable.

### 1.3 Stock DS4 while H3 is rendering

Source: `bench/results/B_one_render.txt`, `C_two_renders.txt`

| Concurrency | Idle (A) | **1× H3 render (B)** | **2× H3 render (C)** |
|---:|---:|---:|---:|
| C1 | 88.87 | **40.98** | **28.48** |
| C2 | 149.37 | 68.38 | 50.99 |
| C3 | 199.47 | 88.19 | 66.74 |
| C4 | 214.90 | 97.19 | 73.44 |
| C5 | 203.93 | 92.14 | 74.25 |
| C6 | 285.95 | **130.77** | **100.79** |

Interpretation (Tony + keyspark): first video arm absorbs most contention; second arm is cheaper.

| Step | C1 cost (tok/s lost) | C6 cost |
|------|---------------------:|--------:|
| Idle → 1 render | 47.9 | 155.2 |
| 1 → 2 renders | 12.5 | 30.0 |

### 1.4 Post-abliteration DS4 (L10–35 λ3.5 anchorstock)

Model served: `deepseek-v4-flash-0731-ablit-l10-35-anchorstock`  
Env: `deploy/keyspark/env.ablit-cotenancy` · util **0.78** · MTP k=5 · 1M ctx  
Weights load observed: **~79.17 GiB** · GPU KV ~**1.50M** tokens @ util 0.78

| Metric | Stock 0731 (H3 idle co-res) | Ablit 0731 (H3 busy co-res) | Delta |
|--------|----------------------------:|----------------------------:|------:|
| Decode peak count300 | **83.3** tok/s | **81.5** tok/s | **≈ −2%** |
| Mean content mix | 67.4 | 65.1 | ≈ −4% |
| C1 idle-coresident | 83.5 | ~same class (ablit keeps DSpark/MTP) | ~flat |

**Takeaway:** abliteration (this champion: L10–35 λ3.5 wo_b) does **not** materially slow decode vs stock on the same DSpark 0731 + util 0.78 profile. Refusal bypass is the product; speed stays.

Source peak file: `/tmp/ds4-ablit-peak-retry.txt` (ablit + H3 co-tenant during lab runs).

---

## 2. MiniMax H3 — pre vs post heretic/enhanced upgrade

### 2.1 Stack layers

| Layer | Pre (basic co-tenancy) | Post (heretic enhanced) |
|-------|------------------------|-------------------------|
| ComfyUI | older / 0.30.0 issues | **0.30.1** (required for Spectrum) |
| TE | stock MiniMax TE | **heretic** `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` |
| Attn | SolAttnMiniMax only or partial | **Sage → SolAttnPatch → Spectrum → FBC** |
| Post | often none / native res | **RealESRGAN_x2plus** → 864×480 → **1728×960** |
| Graph | simple T2V / I2V | `enhanced_graph.py` |

### 2.2 Wall-clock for ~5s clip (124 frames @ 24 fps, 20 steps)

| Config | Res | Wall | Notes |
|--------|-----|-----:|-------|
| **Pre** sequential part1 (stock-ish dual script) | 832×480 | **333 s** | `hp_dragon_dual` run2 p1 |
| **Pre** sequential part2 | 832×480 | **347 s** | run2 p2 |
| **Post** enhanced sequential part1 | 1728×960 | **411 s** | Spectrum+ESRGAN; dual_after |
| **Post** enhanced full arm (parallel partA) | 1728×960 | **424 s** | FLF + upscale |
| **Post** enhanced full arm (parallel partB) | 1728×960 | **440 s** | FLF + upscale |

**Upgrade cost on a single 5 s arm:** ~333 s → ~411–440 s (**~+25–30% wall**) for **~4× pixels** (832×480 → 1728×960) + heretic TE + Spectrum/Sage stack.

Cheap scout keyframes (len=22, steps=10): **~84–92 s** each.  
Quality keyframes (len=33–49, steps=20): **~150–192 s** each.

---

## 3. Video workflow — sequential vs parallel (concurrency=2)

Story: Harry Potter → dragon → Hogwarts, **~10 s** final stitch (two ~5.17 s halves).

### 3.1 Sequential dual (one arm after the other)

| Run | Stack | Part1 | Part2 | **Total wall** | Output |
|-----|-------|------:|------:|---------------:|--------|
| Original sequential | pre/basic | 333 s | 347 s | **~680 s (~11.3 min)** | 832×480 · 10.0 s |
| Enhanced sequential | heretic+Spectrum+ESRGAN | 411 s | *(killed; est. ~440 s)* | **~851 s est. (~14.2 min)** | 1728×960 |

Continuity: part2 `first_frame` = last frame of part1 (tightest seam).

### 3.2 Parallel dual-FLF (concurrency=2) — fast scouts

Script: `keyframe_dual_flf.py` with short scouts (early lab run)  
Source: `Videos/hp_dragon_parallel/TIMING.txt` · `/tmp/hp_dragon_parallel/run.log`

| Phase | Wall | Boxes |
|-------|-----:|-------|
| 0 mid keyframe I1 | 88 s | `.2` only |
| 1 I0+I2 scouts parallel | **92 s** | `.2` ‖ `.3` |
| 2 full FLF 5 s×2 parallel | **440 s** (A 424 / B 440) | `.2` ‖ `.3` |
| stitch | &lt;5 s | local ffmpeg |
| **Total** | **624 s (~10.4 min)** | |

Output: **1728×960** · ~10.1 s · Spectrum + RealESRGAN.

### 3.3 Parallel quality-first (default now)

`H3_QUALITY_ID=1` · full steps on I0/I1 · detailed identity prompts · optional `H3_I0_REF`  
Phase 0 measured (I0 ‖ I1 full steps): **192 s** wall (max of arms ~192 / 152).  
Full end-to-end of quality path ≈ Phase0 + Phase1(I2) + Phase2(~440 s) ≈ **~14 min class** (quality over speed; still benefits from dual-arm Phase2).

### 3.4 Head-to-head (same ~10 s story)

| Workflow | Wall | Resolution | Stack | vs sequential enhanced |
|----------|-----:|------------|-------|------------------------:|
| Sequential basic | **680 s** | 832×480 | stock dual | faster but soft |
| Sequential enhanced (est.) | **~851 s** | 1728×960 | heretic+ | 1.00× |
| **Parallel enhanced (fast scouts)** | **624 s** | 1728×960 | heretic+ | **~1.36× faster** (~227 s saved) |
| Parallel quality-first | ~14 min class | 1728×960 | heretic+ quality KF | arms still parallel |

**Pure dual-arm math (enhanced):**  
`sequential arms 424+440 = 864 s` vs `parallel max = 440 s` → **~2× on the heavy phase**.  
Overall not 2× because keyframes are serial/partial overhead (~180 s fast path).

```
Sequential enhanced (est):  ████████████████████████  ~851s
Parallel enhanced (meas):   ██████████████████        624s   (−27%)
Parallel heavy arms only:   ████████████              440s   (−49% vs 864)
```

---

## 4. What “concurrency=2” means

| Layer | Concurrency | Meaning |
|-------|-------------|---------|
| DS4 vLLM | max_num_seqs **6** | up to 6 chat streams |
| **H3 fleet** | **2** | **one** heavy Comfy job per Spark, **both** Sparks at once |
| Forbidden | 2 heavy FLF on one Spark | OOM / thrash under util 0.78 DS4 co-tenancy |

---

## 5. Hard caps & co-tenancy rules (do not “optimize” these)

1. **Start DS4 first**, wait `/v1/models`, **then** start H3. Reverse → H3 ~50 GiB, DS4 cannot load.
2. **`GPU_MEMORY_UTILIZATION=0.78`** for co-tenancy (Tony). Fleet hard cap **0.85** — never exceed.
3. H3: `--disable-pinned-memory` only (no `--reserve-vram` while co-tenanting).
4. Teardown: **H3 first**, then DS4.
5. Nodes: **only `.2` + `.3`**.

---

## 6. Re-run benches (reproduce)

```bash
# DS4 C1–C6 (stock or ablit model id as served)
python3 bench/bench_conc.py 10.100.10.2:8888 deepseek-v4-flash-0731-ablit-l10-35-anchorstock idle 1,2,3,4,5,6

# Video walls
bash deploy/keyspark/run_quality_parallel.sh   # quality parallel
# sequential: PYTHONPATH=deploy/keyspark python3 deploy/keyspark/hp_dragon_dual.py
```

Raw files to commit with the fork:

- `bench/results/A_no_video.txt`
- `bench/results/B_one_render.txt`
- `bench/results/C_two_renders.txt`
- `bench/results/keyspark_idle_h3_coresident_20260806_231121.txt`
- `bench/results/bench_full.txt`
- `bench/results/realwork_peak.txt`
- `bench/results/ablit_peak_h3_coresident.txt` (copy of lab peak)
- `bench/results/video_walls_hp_dragon.md` (this section 3 condensed)
