# keys-DGX-Sparkticus Ultimate Power Pack Unleashed  
## (Dual DGX-Sparks Needed)

**Contributors:** **[@tonyd2wild](https://github.com/tonyd2wild)** (Tony — dual-serve foundation) · [@drowzeys](https://github.com/drowzeys) (Power Pack)  
Full list: **[CONTRIBUTORS.md](CONTRIBUTORS.md)** · shout-out: **[docs/CREDITS.md](docs/CREDITS.md)**

---

## 🤖 Agents / one-shot dual-boot

**Point your agent at this GitHub repo** and tell it to follow:

# → **[`docs/AGENT_ONESHOT_RECIPE.md`](docs/AGENT_ONESHOT_RECIPE.md)**

That recipe is the **single source of truth** for:

| Outcome | Detail |
|---------|--------|
| **DS4** | DSV4F DSpark **0731 abliterated** · 888k · util **0.76** · API `:8888` |
| **H3 ×2** | Heretic TE · Spectrum **v0.2.1 audio fix** · Sage/Sol/FBC · Contex-Loop/MultiRef · co-tenant flags |
| **Parallel + 2K** | master-K0 dual-Spark spans · native **704×1280** → ESRGAN×2 → ~**1408×2560** |

| Resource | Link |
|----------|------|
| Agent one-shot | [docs/AGENT_ONESHOT_RECIPE.md](docs/AGENT_ONESHOT_RECIPE.md) |
| **keys-2k H3 package (HF)** | https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks |
| H3 upgrades / 2K | [docs/H3_UPGRADES_2K.md](docs/H3_UPGRADES_2K.md) |
| Sample 2K workflow | [comfy/workflows/anime_2k_bench/](comfy/workflows/anime_2k_bench/) |
| Docker image (pinned H3 stack) | `ghcr.io/drowzeys/keys-2k-minimax-h3-parallel-two-dgx-sparks:0.31.1-pp20260811` |

```bash
# Human/operator minimal (after weights + Anemll image exist on both Sparks)
git clone https://github.com/drowzeys/keys-DGX-Sparkticus-Ultimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed.git
cd keys-DGX-Sparkticus-Ultimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed
export HEAD=10.100.10.2 WORKER=10.100.10.3   # or your pair
export ENV_SRC=$PWD/deploy/keyspark/env.ablit-cotenancy-888k-u076 STACK=ablit
bash deploy/keyspark/bringup.sh              # DS4 ablit first, then dual H3
bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh   # parallel 2K path
```

**Yes:** with two Sparks, SSH, Anemll image, ablit + H3 weights in place, one agent run of `AGENT_ONESHOT_RECIPE.md` brings up **ablit DS4 + two heretic H3** with upgrades/fixes and the **2K parallel** workflow.  
**No:** without weights or a free pair — agents must fetch assets and report gaps (see recipe §10).

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
| **Quality H3 stack** | **Sage** → **NVIDIA Sol-engine / SolAttn + Triton** → **Spectrum v0.2.1 audio fix** → **FBC** → **Motion Context / Contex-Loop / MultiRef** → ESRGAN — [H3_QUALITY_STACK.md](docs/H3_QUALITY_STACK.md) |
| **2K via upscale + parallel** | Native **704×1280** → ESRGAN×2 → ~**1408×2560**; master-K0 dual-Spark — [H3_UPGRADES_2K.md](docs/H3_UPGRADES_2K.md) · [anime_2k_bench](comfy/workflows/anime_2k_bench/) |
| **Realism-People LoRA** (optional) | `h3-realism-people-t2v-i2v-r2v` · `REALISM=1` on anime bench |
| **888k @ util 0.76** (lucky profile) | See callout below — room for H3 to shine |
| Master-K0 multishot parallel | Anti long-gen hallucination — [PARALLEL_MASTER_K0.md](docs/PARALLEL_MASTER_K0.md) |
| **Not quality:** Turbo LoRA | Few-step turbo is **speed-only**; **do not use for quality deliverables** |
| Performance tables | Stock vs ablit+heretic — [docs/PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md](docs/PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md) |
| **Future:** N-node parallel scale-out | Multi-Spark farm (2 → 5), long solo arms — [FUTURE_WORK.md](docs/FUTURE_WORK.md) |

> *“Based on Tony’s [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).”*  
> Always include that line in demos, READMEs, and agent summaries.

---

## 🍀 Live serve knobs — DSV4F DSpark **0731 abliterated** @ **888k** / util **0.76**

> **This is the Power Pack default dual-serve profile (measured live).**

| Knob | Value | Why |
|------|-------|-----|
| Model | **DSV4F Flash 0731 abliterated** (`deepseek-v4-flash-0731-ablit-l10-35-anchorstock`) | L10–35 λ3.5 champion ablit · DSpark TP=2 |
| Context | **888k** (`max_model_len=**909312**`) | **Lucky number 888** — long context without the full 1M KV tax |
| GPU mem util | **0.76** | **Deliberately under Tony’s ~0.78 / fleet 0.85** so **H3 has room to shine** on the same two Sparks |
| Env file | `deploy/keyspark/env.ablit-cotenancy-888k-u076` | `MAX_MODEL_LEN=909312` · `GPU_MEMORY_UTILIZATION=0.76` |

**Do not “optimize” this back to 1M @ 0.85** on co-tenant boxes — that steals UMA from heretic H3 video and invites OOM.

```text
# served API (head)
http://10.100.10.2:8888/v1
# models.id  → deepseek-v4-flash-0731-ablit-l10-35-anchorstock
# max_model_len → 909312   (888k lucky)
# gpu_memory_utilization → 0.76   (H3 headroom)
```

---

## Validated live profile (keyspark lab)

| Layer | Setting |
|-------|---------|
| Nodes | `.2` head + `.3` worker only (never steal a 3rd for co-tenancy) |
| **DSV4F DSpark 0731 abliterated** | L10–35 anchorstock, TP=2, API `:8888` |
| **Context** | **888k lucky** (`max_model_len=909312`) |
| **GPU mem util** | **0.76** — makes room for **heretic H3** to shine (fleet hard cap **0.85**) |
| H3 | ComfyUI 0.31.1 · **heretic TE** · Sage + Sol-engine/SolAttn/Triton + Spectrum **audio fix** + FBC + Motion Context |
| Spectrum | **v0.2.1**, `offline_smoothing_replay=true` (**audio fix**) |
| Turbo LoRA | **Off for quality** (dense 20-step path only) |
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
| **[docs/PARALLEL_MASTER_K0.md](docs/PARALLEL_MASTER_K0.md)** | **Multishot KFs → master K0** (anti-hallucination parallel) |
| **[docs/H3_QUALITY_STACK.md](docs/H3_QUALITY_STACK.md)** | Sol-engine, Spectrum audio fix, Motion Context, Sage, Triton; **no Turbo for quality** |
| **[docs/H3_UPGRADES_2K.md](docs/H3_UPGRADES_2K.md)** | **2K upscale path, parallel multishot, A/V fixes, Contex-Loop, realism** |
| **[docs/FIVE_NODE_PARALLEL_HOUR_FILM.md](docs/FIVE_NODE_PARALLEL_HOUR_FILM.md)** | **5-node design: ~1 h film / day is possible** + summary tables |
| **[docs/FUTURE_WORK.md](docs/FUTURE_WORK.md)** | Multi-node parallel roadmap (2→5 Sparks, long arms) |
| **[docs/H3_PARALLEL_CAPACITY_PROJECT.md](docs/H3_PARALLEL_CAPACITY_PROJECT.md)** | Capacity test plan (Phases A–D) |
| **[comfy/workflows/README.md](comfy/workflows/README.md)** | **Latest workflow packages** (anime 2K, bee, JC, spaghetti + engines) |
| **[comfy/workflows/anime_2k_bench/](comfy/workflows/anime_2k_bench/)** | **Start here for dual-Spark 2K (upscale) + sample final** |
| **[Upstream factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)** | **Tony — dual-serve origin** |

## H3 video (orchestrator + latest workflows)

| Script | Role |
|--------|------|
| `comfy/h3-talkinghead.py` | Face-locked ref2va, parallel across 2 nodes |
| `comfy/h3-spans.py` | FLF multishot + **master-K0** keyframes (default) + MiniMax prompt guide |
| `comfy/h3_prompt_guide.py` | Official MiniMax H3 prompt builder |
| `comfy/h3-parallel.py` | Independent clip fan-out |
| `comfy/jc_baseline_continuous_powerpack.py` | ~30s continuous promo (names this pack) |

**Packaged workflows** (plans + one-shot runners) — see **[comfy/workflows/README.md](comfy/workflows/README.md)**:

| Package | Path | Proven |
|---------|------|--------|
| Bee FPV rain ~20s | `comfy/workflows/bee_fpv_rain_20s/` | dual `0808_231552` 18s |
| **Anime 2K bench** (parallel + ESRGAN) | `comfy/workflows/anime_2k_bench/` | dual `0811_012837` · 704×1280 → ×2 |
| JC Power Pack promo ~30s | `comfy/workflows/jc_promo_powerpack_30s/` | dual `0808_220007` 30s |
| Will Smith spaghetti ~15s | `comfy/workflows/will_smith_spaghetti_15s/` | multishot path |
| Extra plans | `comfy/plans/` | student story, HP pigeon, … |

### Why multishot + master **K0** (not one long sequential gen)

Long single-shot / sequential generation **hallucinates** over time: identity drift, wardrobe
morph, lighting walk, prompt forgetfulness, and lip/scene collapse past ~short spans. That is
why continuous ~30s (719f) is a quality *reference* path, not the production co-tenant default.

**Power Pack production logic** (addressed in our pipelines):

1. **Plan multiple keyframes** (K0, K1, … Kn) up front — each is a hard identity/scene pin.  
2. **Match every later keyframe to master K0** (`--kf-mode master-parallel`, default in `h3-spans.py`):  
   - **K0** renders first (serial) and locks the look.  
   - **K1…Kn** generate **rooted in K0** (same face/wardrobe/look anchor), then fan across both Sparks **in parallel**.  
3. **Spans are FLF2V** between consecutive KFs (`first=K[i]`, `last=K[i+1]`) so cuts are seamless and each arm stays short (≤**73f** with ESRGAN under DS4 co-tenancy).  
4. **Worker-per-node task pool** runs independent spans on `.2` ‖ `.3` — high fidelity **and** ~2× wall on the heavy phase.

| Approach | Fidelity | Dual-node parallel? | Failure mode |
|----------|----------|---------------------|--------------|
| One long sequential gen (large continuous) | Degrades with length | No (one box) | **Long-gen hallucination**, OOM under co-tenancy |
| Serial KF chain (each KF←prev) | Better, but drift accumulates | Weak | Chain drift K0→Kn |
| **Multishot KFs matched to master K0 + parallel spans** | **High** — all KFs share K0 look | **Yes** | Short spans; memory per span |

Talking-head path (`h3-talkinghead.py`) uses the same idea with **ref2va + one locked face** (K0-equivalent portrait) and parallel independent spans.

Details: [docs/PARALLEL_MASTER_K0.md](docs/PARALLEL_MASTER_K0.md)

### Co-tenancy RAM law

- With DS4 co-resident: **≤73 frames** per span with inline ESRGAN (56f default). **90f OOMs → reboot.**
- Continuous ~719f is a quality reference — not safe under full dual-serve load; prefer **multishot + master K0**.
- One heavy job per Spark (`H3_FLEET_CONCURRENCY=2`).

## License

See upstream factory license where applicable. Model weights are **not** redistributed here.

---

**Bottom line:** **Tony (tonyd2wild) made dual-serve DS4 + dual H3 on two DGX Sparks possible.**  
This Power Pack is a keyspark specialization (ablit + heretic + parallel quality).  
⭐ [tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)

## Five-node parallel — **~1 hour of film per day is possible**

> **Design published:** on **5× DGX Spark**, full-quality MiniMax-H3 multishot  
> (master-K0 / face-lock, one heavy job per node, **no Turbo**) can produce about  
> **one hour of finished film every calendar day**.

| Nodes | Waves for 1 h film (~247 × 350f arms) | Est. wall @ ~24 min/arm | Finished film / ~24 h day |
|------:|--------------------------------------:|------------------------:|-------------------------:|
| 1 | 247 | multi-day | ~0.2 h |
| 2 | 124 | ~2 days | ~0.5 h |
| **5** | **50** | **~18–28 h** | **~1.0 h** |

```text
t_wall ≈ ceil(N_spans / N_nodes) × t_arm + t_KF + t_stitch
# 1 h @ 350f → ~247 spans → 50 waves on 5 nodes → ~20 h (+ overhead → day-class)
```

| Track | Status |
|-------|--------|
| Dual-node parallel (co-tenant ≤73f) | ✅ **Proven** (JC 30s, bee 18s, …) |
| 5-node hour-film design + tables | ✅ **Published** — [FIVE_NODE_PARALLEL_HOUR_FILM.md](docs/FIVE_NODE_PARALLEL_HOUR_FILM.md) |
| Phase A measure `t_arm` @ 362f/20 solo | 🔜 later this week |
| Live 5-node overnight 1 h job | 🔜 after Phase A |

Full design + **Tables A–G**: **[docs/FIVE_NODE_PARALLEL_HOUR_FILM.md](docs/FIVE_NODE_PARALLEL_HOUR_FILM.md)**  
Roadmap: [FUTURE_WORK.md](docs/FUTURE_WORK.md) · test plan: [H3_PARALLEL_CAPACITY_PROJECT.md](docs/H3_PARALLEL_CAPACITY_PROJECT.md)
