# Performance: Stock dual-serve vs Ablit DS4 + Heretic H3

**Repo:** [keys-DGX-Sparkticus Utimate Power Pack Unleashed (Dual DGX-Sparks Needed)](https://github.com/drowzeys/keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed)  
**Hardware:** 2× NVIDIA DGX Spark GB10 (121 GiB UMA) · fabric `.2` head + `.3` worker  
**Never** use `.1` / 5482 for this stack.

---

## ⭐ Dual-serve credit — Tony (tonyd2wild)

**The dual-serve co-tenancy methodology, util profile, start order, and A/B/C benches in this
document come from Tony.** He made running full DS4 + dual H3 on two DGX Sparks possible.

→ **[tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)**  
→ Full shout-out: **[CREDITS.md](./CREDITS.md)**

Keyspark rows (ablit peak, heretic video walls) are lab extensions **on top of** Tony’s factory.

---

**Headline:** Abliteration + heretic TE keep **nearly the same DS4 decode speed** as stock 0731 on the dual co-tenancy stack (≈ **−2%** peak). Video wall goes up mainly because we ship **higher resolution + Spectrum/ESRGAN quality**, not because heretic is slow—and **dual-node parallel** recovers most of that wall-clock.

Based on [tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory) co-tenancy benches, plus keyspark ablit/heretic extensions. Sources under `bench/results/` and lab `TIMING.txt` files.

---

## What “stock dual serve” vs “Power Pack” means

| Layer | **Stock dual-serve** | **Power Pack (ablit + heretic)** |
|-------|----------------------|----------------------------------|
| DS4 weights | Stock DSV4F **0731** | **Ablit L10–35 λ3.5** `…-ablit-l10-35-anchorstock` |
| DS4 serve | DSpark TP=2, util ~0.78, often 1M ctx | Same DSpark/MTP path; **Power Pack live = 888k (lucky) @ util 0.76** so **H3 has room to shine** |
| H3 TE | Stock MiniMax Qwen3-VL TE | **Heretic** `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` |
| H3 stack | Basic co-tenancy / partial Sol | **Sage → Sol-Attn → Spectrum v0.2.1 → FBC** + soft VRAM pin |
| Video out | Often native / ~832×480 | **RealESRGAN ×2** (e.g. 864×480 → **1728×960**) |
| Product | Full speed, refusals intact | **Refusal bypass + better video/audio**, minimal DS4 speed tax |

Live Power Pack serve (DSV4F DSpark **0731 abliterated** — when up):

```text
model id:                 deepseek-v4-flash-0731-ablit-l10-35-anchorstock
max_model_len:            909312          # 888k — lucky number
gpu_memory_utilization:   0.76            # under 0.78/0.85 → room for heretic H3 to shine
env:                      deploy/keyspark/env.ablit-cotenancy-888k-u076
```

---

## 1. DSV4F decode — stock vs ablit (minimal decrease)

### 1.1 Stock DS4 alone (no H3) — Tony baseline

max_tokens=700 · C1–C6 · source `bench/results/A_no_video.txt`

| Concurrency | agg tok/s | per-stream | TTFT mean (s) |
|---:|---:|---:|---:|
| C1 | **88.87** | 90.87 | 0.16 |
| C2 | 149.37 | 76.27 | 0.18 |
| C3 | 199.47 | 67.84 | 0.19 |
| C4 | 214.90 | 60.06 | 0.25 |
| C5 | 203.93 | 44.35 | 0.34 |
| C6 | **285.95** | 51.95 | 0.34 |

### 1.2 Stock DS4 + **idle** H3 co-resident (dual serve)

Model `deepseek-v4-flash-0731` · util 0.78 · H3 both nodes up, not heavy-rendering  
Source `bench/results/keyspark_idle_h3_coresident_20260806_231121.txt`

| Concurrency | agg tok/s | per-stream | TTFT mean (s) |
|---:|---:|---:|---:|
| C1 | **83.54** | 85.43 | 0.17 |
| C2 | 130.74 | 67.55 | 0.23 |
| C3 | 170.18 | 58.51 | 0.27 |
| C4 | 193.91 | 54.07 | 0.34 |
| C5 | 200.44 | 43.90 | 0.37 |
| C6 | **242.03** | 44.12 | 0.42 |

Warm decode peak (count300): **83.3 tok/s** · content mix mean **67.4 tok/s**

**Idle H3 tax vs stock alone:** C1 **−6%** (88.9 → 83.5), C6 **−15%** (286 → 242). Co-tenancy cost is real; still usable for agents/chat.

### 1.3 Ablit DS4 vs stock (same dual-serve class) — **≈ −2% decode**

| Metric | Stock 0731 (H3 idle co-res) | **Ablit L10–35** (H3 co-res lab) | Delta |
|--------|----------------------------:|---------------------------------:|------:|
| Decode peak count300 | **83.3** tok/s | **81.5** tok/s | **≈ −2%** |
| Mean content mix | 67.4 | 65.1 | ≈ −4% |
| C1 idle-coresident class | 83.5 | same class (DSpark + MTP retained) | ~flat |

**Takeaway:** champion ablit (L10–35 λ3.5 `wo_b`, MTP stock) does **not** materially slow DSpark 0731. You keep dual-serve speed; you gain refusal bypass.

Source: `/tmp/ds4-ablit-peak-retry.txt` · `bench/results/ablit_peak_h3_coresident.txt`

### 1.4 Stock DS4 while H3 is **rendering** (contention)

Tony baseline A / B / C · sources `A_no_video.txt`, `B_one_render.txt`, `C_two_renders.txt`

| Concurrency | Idle (A) | **1× H3 render (B)** | **2× H3 render (C)** |
|---:|---:|---:|---:|
| C1 | 88.87 | **40.98** | **28.48** |
| C2 | 149.37 | 68.38 | 50.99 |
| C3 | 199.47 | 88.19 | 66.74 |
| C4 | 214.90 | 97.19 | 73.44 |
| C5 | 203.93 | 92.14 | 74.25 |
| C6 | 285.95 | **130.77** | **100.79** |

First video arm takes most of the hit; second arm is cheaper. **Policy:** one heavy H3 job per Spark (`H3_FLEET_CONCURRENCY=2`).

```
C1 decode (illustrative):
  Stock alone:           ████████████████████  ~89 tok/s
  Stock + idle H3:       ███████████████████   ~84 tok/s   (−6%)
  Ablit + idle/busy H3:  ██████████████████    ~82 tok/s   (−2% vs stock idle)
  Stock + 1 H3 render:   █████████             ~41 tok/s   (contention, not ablit)
```

---

## 2. MiniMax H3 — stock-ish vs heretic enhanced

Heretic TE is **required** on the Power Pack path:

```text
H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors
```

Templates: `h3-r2v-heretic-enhanced.json`, `jc-baseline-workflow-api.json`, `jc-noupscale-api.json` all pin that CLIP.

| Layer | Stock / basic dual | **Heretic enhanced (Power Pack)** |
|-------|--------------------|-----------------------------------|
| TE | stock MiniMax TE | **heretic** NVFP4 |
| Attn / quality | partial Sol | Sage → **Sol-Attn** → **Spectrum 0.2.1** (`offline_smoothing_replay=true`) → **FBC** |
| Upscale | often none | **RealESRGAN ×2** |
| Soft VRAM | varies | `--reserve-vram 48 --vram-headroom 10` |

### Wall-clock (~5 s arm, 124f @ 24 fps, 20 steps)

| Config | Resolution | Wall | Notes |
|--------|------------|-----:|-------|
| Pre / stock-ish sequential | 832×480 | **333–347 s** | dual script, lower res |
| Post heretic sequential | **1728×960** | **411 s** | Spectrum + ESRGAN |
| Post heretic parallel arm A/B | **1728×960** | **424 / 440 s** | FLF + upscale |

**Honest framing:** heretic+enhanced is **~+25–30% wall per arm** vs stock-ish 5 s clip—but you get **~4× pixels** (832×480 → 1728×960) + Spectrum audio fix + Sol/FBC. That is quality spend, not ablit tax.

---

## 3. Dual-node parallel cuts **video creation** time

### 3.0 Fidelity reason we parallelize multishot (not one long gen)

Large **sequential / continuous** generations **hallucinate** over long horizons (identity drift,
prompt collapse). Production path is **multishot keyframes matched to master K0**, then short
FLF spans in parallel on both Sparks — higher fidelity **and** lower wall clock than one long
sample. Full write-up: **[PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md)**.

Heavy phase = two ~5 s arms. Sequential sums; parallel takes the **max**.

| Mode | Wall (same ~10 s story) | Res | Stack |
|------|------------------------:|-----|-------|
| Sequential basic | **~680 s (~11.3 min)** | 832×480 | stock-ish dual |
| Sequential enhanced (est.) | **~851 s (~14.2 min)** | 1728×960 | heretic+ |
| **Parallel enhanced (fast scouts)** | **624 s (~10.4 min)** | 1728×960 | heretic+ |
| Parallel quality-first | ~14 min class | 1728×960 | heretic+ quality KF |

**Pure dual-arm math (enhanced):**

| | Time |
|--|-----:|
| Sequential arms | 424 + 440 = **864 s** |
| Parallel arms | max(424, 440) = **440 s** |
| Speedup on heavy phase | **~2.0×** (−49%) |

Overall end-to-end is **~1.3–1.4×** faster than sequential enhanced (not full 2×) because keyframe/scout phases still add overhead—but you still beat stock sequential wall while shipping higher-res heretic output.

```
Sequential enhanced (est):  ████████████████████████  ~851s
Parallel enhanced (meas):   ██████████████████        624s   (−27% vs seq enhanced)
Parallel heavy arms only:   ████████████              440s   (−49% vs 864s sequential arms)
```

Talking-head / multi-span pipelines (`h3-talkinghead.py`, `h3-spans.py`):  
**~2×** on span pools (e.g. 13 spans ~26 min parallel vs ~170 min serial class)—memory stays per-span (≤73f with ESRGAN under DS4 co-tenancy).

---

## 4. One-page comparison card

| Question | Answer |
|----------|--------|
| Does ablit slow DS4 vs stock 0731 dual-serve? | **No material hit** — peak decode **≈ −2%** |
| Does idle H3 slow DS4? | Yes, modestly (**C1 −6%**, C6 −15%) — true for stock *and* ablit |
| Does active H3 render slow DS4? | Yes, a lot (C1 ~89 → ~41 with 1 render) — **schedule** chat vs video |
| Is heretic H3 “free”? | Not free wall-clock; pays for **4× pixels + audio/quality stack** |
| How do we still finish video faster? | **Two Sparks, one job each**, parallel arms/spans → **~2×** on the heavy phase |
| Live Power Pack profile | **DSV4F DSpark 0731 abliterated** · **888k (lucky)** · util **0.76** · heretic H3 (room for H3 to shine) |

---

## 5. Reproduce (agents)

```bash
# DS4 C1–C6 (use served model id)
python3 bench/bench_conc.py 10.100.10.2:8888 \
  deepseek-v4-flash-0731-ablit-l10-35-anchorstock idle 1,2,3,4,5,6

# Stock dual-serve comparison (when STACK=stock is up)
python3 bench/bench_conc.py 10.100.10.2:8888 deepseek-v4-flash-0731 idle 1,2,3,4,5,6

# Parallel quality video wall
bash deploy/keyspark/run_quality_parallel.sh
```

Bring-up envs:

- Stock co-tenancy: `deploy/keyspark/env.cotenancy` / `STACK=stock`
- Ablit co-tenancy: `deploy/keyspark/env.ablit-cotenancy` (1M @ 0.78) or `env.ablit-cotenancy-888k-u076` (**888k @ 0.76**)

---

## Credits

### ⭐ Tony made dual-serve possible

- **Co-tenancy methodology, util 0.78 profile, DS4-first order, idle/1×/2× H3 C1–C6 benches:**  
  **Tony / [tonyd2wild](https://github.com/tonyd2wild)** —  
  **[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)**  
  Star and cite that repo first. See **[CREDITS.md](./CREDITS.md)**.

### This fork

- Ablit champion L10–35 + heretic dual-boot + parallel quality path: keyspark Power Pack  
- Spectrum v0.2.1 audio path (`offline_smoothing_replay`) · Sol-Attn / FBC on GB10  

