# Five-node parallel design — **one hour of film per day is possible**

**Status:** **Published design** (planning math locked; farm not yet measured end-to-end)  
**Date:** 2026-08-09  
**Owner:** keyspark lab · Power Pack  
**Dual-serve foundation:** Tony / [@tonyd2wild](https://github.com/tonyd2wild) — [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)

---

## Headline

> With **5× DGX Spark** running full-quality MiniMax-H3 multishot in parallel  
> (**one heavy job per node**, master-K0 / face-lock arms, **no Turbo**),  
> producing about **one hour of finished film every calendar day is possible**.

That is not “one continuous 3600-second sample.” It is **parallel multishot**: many short high-fidelity arms, stitched. Quality stays per-arm; **more nodes only cut wall clock**.

| Claim | Detail |
|-------|--------|
| **Possible daily output (5 nodes)** | **~1 hour** finished full-quality film per **~1 calendar day** |
| Planning wall for 1 h film @ ~350f arms | **~18–28 hours** (≈ 50 waves × ~24 min/arm + KF/stitch/retry) |
| Quality | Same graph / 20 steps / heretic stack as dual proven runs |
| Parallel model | `t_wall ≈ ceil(N_spans / N_nodes) × t_arm + t_KF + t_stitch` |
| Measured today | Dual-node (2 Sparks) multishot proven; **5-node = design + next test** |

Measurement vehicle: [H3_PARALLEL_CAPACITY_PROJECT.md](./H3_PARALLEL_CAPACITY_PROJECT.md) · roadmap: [FUTURE_WORK.md](./FUTURE_WORK.md)

---

## 1. Design (how 5-node parallel works)

```text
                    ┌──────────── Master K0 ────────────┐
                    │  serial lock (look / identity)    │
                    └───────────────┬───────────────────┘
           KF1…KFn rooted in K0     │     (parallel across N Sparks)
                                    ▼
        ┌──────────┬──────────┬──────────┬──────────┬──────────┐
        │ Spark 1  │ Spark 2  │ Spark 3  │ Spark 4  │ Spark 5  │
        │ arm i    │ arm i+1  │ arm i+2  │ arm i+3  │ arm i+4  │
        │ FL2VA /  │ FL2VA /  │ FL2VA /  │ FL2VA /  │ FL2VA /  │
        │ ref2va   │ ref2va   │ ref2va   │ ref2va   │ ref2va   │
        └────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┘
             │          │          │          │          │
             └──────────┴──────────┴──────────┴──────────┘
                                    ▼
                         stitch ordered arms → film
```

### Design rules

| # | Rule |
|---|------|
| 1 | **Parallel does not reduce quality** — identical sampler, TE, Spectrum, steps per arm |
| 2 | **Film length = sum of arms**, not one giant DiT sample |
| 3 | **Master-K0 / face-lock** for long form (kills long-gen hallucination) |
| 4 | **One heavy job per Spark** (`H3_FLEET_CONCURRENCY = N_nodes`) |
| 5 | **H3 length grid:** ~350f planning → snap to **345** or **362** |
| 6 | **Co-tenant (DS4 up):** arm ≤ **73f** (+ESRGAN). Long arms only when DS4 is **down** or on free Sparks |
| 7 | **No Turbo** on quality deliverables |
| 8 | Orchestrator: generalize today’s `--nodes a,b` list to **N** endpoints |

### Two operating modes

| Mode | When | Arm length | Use |
|------|------|------------|-----|
| **A. Co-tenant dual** (today) | DS4 + H3 on same 2 boxes | **≤73f** (+ESRGAN) | Agents live while video runs; short multishot |
| **B. H3 film farm** (5-node design) | H3-only on film Sparks (DS4 paused or on a 6th box) | **~345–362f / 20 steps** | Hour-scale daily film capacity |

---

## 2. Formulas

```text
T_arm_s   = F / 24                         # finished seconds per arm
N_spans   = ceil(T_video_s / T_arm_s)      # how many arms for target length
W_waves   = ceil(N_spans / N_nodes)        # sequential waves of parallel work
t_wall    ≈ W_waves × t_arm + t_KF + t_stitch + t_retry
```

**Example — 1 hour film @ 350f arms**

```text
T_arm_s   = 350 / 24 ≈ 14.58 s
N_spans   = ceil(3600 / 14.58) ≈ 247
W_waves@5 = ceil(247 / 5) = 50
t_arm     ≈ 24 min   (planning placeholder until Phase A measures)
t_wall    ≈ 50 × 24 min = 20 h  (+ KF/stitch/retry → ~18–28 h band)
```

→ **One overnight-to-day cycle ≈ one hour of finished film on 5 Sparks.**

---

## 3. Summary tables

### Table A — **Headline capacity: finished film per calendar day** (planning)

Assumes full quality stack, multishot, `t_arm ≈ 24 min` @ ~350f / 20 steps, H3-only nodes, ~10% overhead for KF/stitch/retry.

| Nodes | Waves for **1 h** film (~247 spans) | Est. wall for 1 h film | **Finished film per ~24 h day** |
|------:|------------------------------------:|-----------------------:|--------------------------------:|
| 1 | 247 | ~4+ days | ~**0.2–0.25 h** |
| 2 | 124 | ~2 days | ~**0.4–0.5 h** |
| 3 | 83 | ~1.4–1.8 days | ~**0.6–0.7 h** |
| 4 | 62 | ~1.1–1.4 days | ~**0.8–0.9 h** |
| **5** | **50** | **~18–28 h** | **~1.0 h (design target)** |
| 8 | 31 | ~12–16 h | ~**1.5–2 h** |

**Bold row = published claim:** **5 nodes → ~1 hour of full-quality film per day is possible.**

---

### Table B — **1 hour film wall clock by node count** (planning, 350f-class arms)

| Nodes | Spans | Waves | @ 20 min/arm | @ 24 min/arm | @ 30 min/arm | Band (w/ overhead) |
|------:|------:|------:|-------------:|-------------:|-------------:|--------------------|
| 1 | 247 | 247 | 82 h | 99 h | 124 h | multi-day |
| 2 | 247 | 124 | 41 h | 50 h | 62 h | ~2 days |
| 3 | 247 | 83 | 28 h | 33 h | 42 h | ~1.5 days |
| 4 | 247 | 62 | 21 h | 25 h | 31 h | ~1–1.3 days |
| **5** | **247** | **50** | **17 h** | **20 h** | **25 h** | **~18–28 h** |

---

### Table C — **Arm length options** (what each arm buys)

| Frames (H3 grid) | Seconds @ 24 fps | Spans for **1 h** film | Notes |
|-----------------:|-----------------:|-----------------------:|-------|
| **56** | 2.3 s | ~1543 | Safer co-tenant with ESRGAN |
| **73** | 3.0 s | ~1184 | **Co-tenant max** w/ ESRGAN (proven dual) |
| 124 | 5.2 s | ~696 | Short FLF scouts / mid arms |
| **345** | 14.4 s | ~251 | Long solo arm (grid snap of ~350) |
| **362** | 15.1 s | ~239 | Preferred Phase A measure target |
| 481 | 20.0 s | ~180 | Stretch continuous-style arm |
| 719 | 30.0 s | ~120 | Continuous hero ref; co-tenant OOM |

Hour-film farm design centers on **345/362f** under **H3-only** free UMA.

---

### Table D — **Proven dual-node anchors** (measured — foundation of the math)

| Run | Length | Arms | Res | Wall | Mode |
|-----|--------|------|-----|------|------|
| JC Power Pack `0808_220007` | **30.4 s** | 10×73f | 1152×1536 | **23.3 min** | talkinghead dual co-tenant |
| Talkinghead gold `0808_203455` | **36.5 s** | 12×73f | 1152×1536 | **26.5 min** | talkinghead dual |
| Bee FPV `0808_231552` | **18.0 s** | 6×73f | 1728×960 | **22.0 min** | master-K0 spans dual |

Rough dual co-tenant `t_arm` class: **~2–4 min per 73f quality arm** (includes queue/contention).  
Long-arm `t_arm ≈ 24 min` for 350f is a **planning placeholder** until Phase A measures solo 362f/20.

---

### Table E — **Mode comparison**

| | Co-tenant dual (today) | 5-node film farm (design) |
|--|------------------------|---------------------------|
| Nodes | 2 | **5** |
| DS4 | Up (ablit 888k @ util **0.76**) | Paused / off film boxes |
| Arm | ≤73f + ESRGAN | ~362f / 20 steps + quality stack |
| Parallel | 2-way | **5-way** |
| Daily film capacity | tens of minutes class | **~1 hour / day** |
| Agents live? | Yes | Prefer DS4 on spare node if needed |
| Status | ✅ Proven | 📐 Design published · test later |

---

### Table F — **Quality stack (unchanged at any node count)**

| Layer | Setting |
|-------|---------|
| TE | Heretic H3 (`qwen3vl_32b_heretic…`) |
| Attention | Sage (`PathchSageAttentionKJ`) → Sol-engine / SolAttn + Triton |
| Audio / post | Spectrum **v0.2.1** `offline_smoothing_replay=true` → FBC → ESRGAN ×2 |
| Fidelity | Master-K0 multishot or face-lock ref2va |
| Turbo | **Off** for quality |
| Prompting | MiniMax official VIDEO_PROMPT_WRITING_GUIDE (`h3_prompt_guide.py`) |

---

### Table G — **Sensitivity: when is “1 h film / day” true?**

| If measured `t_arm` (362f/20 + ESRGAN) is… | 5-node wall for 1 h (~50 waves) | Daily hour-film? |
|-------------------------------------------:|--------------------------------:|:----------------:|
| 18 min | ~15–18 h | **Yes, comfortably** |
| **24 min** (planning baseline) | **~20–24 h** | **Yes (tight day)** |
| 30 min | ~25–30 h | Borderline / slightly over one day |
| 40 min | ~33–40 h | Need 6–8 nodes or shorter arms |

**Phase A exists to pin this row.** Until then the published claim uses the **24 min** planning baseline drawn from dual quality-arm experience scaled to longer free-UMA samples.

---

## 4. Architecture checklist (to make it real)

```text
[x] Dual-node parallel multishot proven
[x] Master-K0 + face-lock fidelity model documented
[x] Quality stack frozen (no Turbo)
[x] Capacity formulas + summary tables published (this doc)
[ ] Phase A: measure t_arm @ 362f/20 solo (DS4 down)
[ ] Generalize --nodes to 5 endpoints + fleet=5
[ ] Phase B: dual long-arm multishot
[ ] Phase C: 5-node smoke → optional overnight 1 h job
[ ] Phase D: restore dual-serve 888k@0.76 when done
```

---

## 5. Why not one continuous hour?

| Approach | Why it fails for hour-scale |
|----------|----------------------------|
| Single continuous DiT sample | Identity/wardrobe/lighting **hallucination**; co-tenant **OOM** (719f/362f already fail with DS4 up) |
| Serial one-box long gen | Days of wall; still drifts |
| **5-node multishot parallel** | Memory **per arm**; fidelity **pinned to K0**; wall **÷ nodes** |

---

## 6. Credit

- **Dual-serve co-tenancy on two Sparks:** Tony / [@tonyd2wild](https://github.com/tonyd2wild) — [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)  
- **5-node hour-film parallel design + Power Pack quality multishot:** keyspark  

---

## 7. Related

| Doc | Role |
|-----|------|
| [FUTURE_WORK.md](./FUTURE_WORK.md) | Roadmap entry |
| [H3_PARALLEL_CAPACITY_PROJECT.md](./H3_PARALLEL_CAPACITY_PROJECT.md) | Phases A–D test plan + results log |
| [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md) | Fidelity model |
| [H3_QUALITY_STACK.md](./H3_QUALITY_STACK.md) | Stack checklist |
| [PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md](./PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md) | Dual measured walls |

### One-liner

> **5-node parallel design published:** full-quality MiniMax-H3 multishot, one job per Spark → **~1 hour of finished film per calendar day is possible** (~50 waves × ~24 min arm ≈ 18–28 h wall for 1 h @ 350f-class arms). Dual path proven today; farm measurement next. Dual-serve credit: tonyd2wild.
