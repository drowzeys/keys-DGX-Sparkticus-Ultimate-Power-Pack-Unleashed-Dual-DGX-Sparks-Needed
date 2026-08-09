# H3 parallel capacity project — multi-node scale-out

**Saved:** 2026-08-09  
**Status:** **FUTURE WORK — paused; test later this week** (do not run 5-node farm until scheduled)  
**Owner:** keyspark lab  
**Roadmap home:** [FUTURE_WORK.md](./FUTURE_WORK.md)  
**Published design:** [FIVE_NODE_PARALLEL_HOUR_FILM.md](./FIVE_NODE_PARALLEL_HOUR_FILM.md) — **~1 h film / day on 5 Sparks is possible** + summary tables

This document is the **measurement vehicle** for Power Pack future work: take dual-node
parallel (already shipping) and scale **N Sparks** + longer solo arms without dropping quality.

---

## 1. Goal

Measure and document **how long and how fast** high-quality MiniMax-H3 video can be produced with:

- **Multishot parallel** processing (**enabled today on 2 nodes**)  
- **Per arm ≈ 350 frames** (snap to H3 grid **345** or **362**), **20 steps**  
- Full **quality stack** (not Turbo)  
- Variable node counts: **2 Sparks (now)** → **5 Sparks (future work)**  

Secondary: confirm solo-H3 continuous ceilings when **DSV4F is down** (~100 GiB free UMA per box).

---

## 2. Context locked in this campaign

### Dual-serve (current default)

| Layer | Setting |
|-------|---------|
| Nodes | `.2` + `.3` only for DS4+H3 co-tenant |
| DSV4F | **0731 abliterated**, **888k** (`max_model_len=909312`), util **0.76** (room for H3) |
| H3 | Heretic TE + Sage + Sol-engine/SolAttn/Triton + Spectrum **v0.2.1 audio fix** + FBC + ESRGAN |
| Turbo | **Not for quality** |
| Co-tenant arm cap | **≤73f** (+ESRGAN); **56f** safer; **90f+** OOM risk |
| Parallel | **1 heavy job per Spark** (`H3_FLEET_CONCURRENCY=2` on two boxes) |

### Credit

- **Dual-serve co-tenancy:** Tony / [@tonyd2wild](https://github.com/tonyd2wild) — [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)  
- Power Pack repo: [keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed…](https://github.com/drowzeys/keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed)  
- Prompts: [MiniMax H3 VIDEO_PROMPT_WRITING_GUIDE](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md) via `~/comfy/h3_prompt_guide.py`

### Proven co-tenant multishot anchors

| Run | Length | Res | Wall | Path |
|-----|--------|-----|------|------|
| JC Power Pack `0808_220007` | **30.4 s** (10×73f) | 1152×1536 | **23.3 min** | talkinghead dual |
| Talkinghead gold `0808_203455` | **36.5 s** (12×73f) | 1152×1536 | **26.5 min** | talkinghead dual |
| Bee FPV `0808_231552` | **18.0 s** (6×73f) | 1728×960 | **22.0 min** | spans master-K0 dual |

### Failed under co-tenant (expected)

| Attempt | Result |
|---------|--------|
| Continuous **719f** + ESRGAN | RAM-guard interrupt |
| Continuous **362f** + no ESRGAN (Will Smith) | interrupt mid-sample |

**Lesson:** Keep DSV4F up → multishot only. True continuous hero → **pause DS4** (or use a free Spark).

---

## 3. Thought process (decisions)

1. **Parallel does not reduce quality** — same graph/steps per arm; wall ≈ `ceil(N/nodes) × t_arm`.  
2. **Total film length** = stitch of arms, not one long sample.  
3. **Long continuous hallucination** → prefer **master-K0 / face-lock multishot** for long form.  
4. **350f** is not on H3 grid → use **345** or **362** in tests.  
5. With DS4 down, **~350f / 20 steps** arms are expected **fine** on free UMA; measure once.  
6. **5-node farm** is the scale-out model for hour-scale content; **2-node** is current lab.

---

## 4. Formulas

```text
T_arm_s     = F / 24                          # e.g. 350/24 ≈ 14.58 s
N_spans     = ceil(T_video_s / T_arm_s)       # 1 h → ~247 spans @ 350f
W_waves     = ceil(N_spans / N_nodes)
t_wall      ≈ W_waves × t_arm + t_KF + t_stitch
```

### 1 hour @ 350f / 20 steps (planning numbers)

| Nodes | Waves for ~247 spans | Est. span wall @ 24 min/arm | Est. total wall |
|------:|---------------------:|----------------------------:|-----------------|
| 1 | 247 | ~99 h | ~4+ days |
| 2 | 124 | ~50 h | ~2 days |
| **5** | **50** | **~20 h** | **~18–28 h** (incl. KF/stitch/retry) |

**Rule of thumb (5× H3, full quality):** ~**1 hour of finished film per ~1 calendar day is possible**.

Full published design + Tables A–G (daily capacity, wall-by-nodes, arm grid, proven anchors, sensitivity):  
→ **[FIVE_NODE_PARALLEL_HOUR_FILM.md](./FIVE_NODE_PARALLEL_HOUR_FILM.md)**

---

## 5. Test plan (later this week)

### Phase A — Solo baseline (DS4 down, 1 node)

1. Stop DSV4F on `.2`+`.3`; drop_caches; leave H3 up.  
2. Measure **one arm**:
   - `F=362`, `steps=20`, ESRGAN **on**  
   - Same: ESRGAN **off**  
3. Record wall minutes → plug into formula as `t_arm`.  
4. Optional stretch: `F=481`, `719` continuous (single sample) for continuous ceiling.

### Phase B — Dual multishot @ ~350f (2 nodes, DS4 still down)

1. 4–8 spans of **362f** / 20 steps, master-K0 or face-lock.  
2. Confirm stitch quality and wall ≈ `ceil(N/2)×t_arm`.

### Phase C — Five-node scale (when 5 Sparks free)

1. All five H3-only, no DS4 (or DS4 only on a 6th box if needed).  
2. Smoke: 10 spans @ 362f / 20 steps → expect ~2 waves.  
3. Optional: schedule **1 h** job overnight (247 spans) only after Phase A `t_arm` is measured.  
4. Log: node list, F, steps, ESRGAN y/n, waves, wall, failures.

### Phase D — Restore dual-serve

```bash
export ENV_SRC=~/ds4-h3-video-gen-factory/deploy/keyspark/env.ablit-cotenancy-888k-u076
export STACK=ablit
bash ~/ds4-h3-video-gen-factory/deploy/keyspark/bringup.sh
# or SKIP_H3=1 if H3 already healthy
```

Target after restore: ablit **888k** / util **0.76** + heretic dual H3.

---

## 6. Saved artifacts (already on disk)

| Path | What |
|------|------|
| `~/comfy/workflows/bee_fpv_rain_20s/` | Bee FPV workflow package |
| `~/h3-cotenancy/workflows/bee_fpv_rain_20s/` on **.2** and **.3** | Same on H3 stacks |
| `~/comfy/h3_prompt_guide.py` | Official MiniMax prompt builder |
| `~/comfy/h3-spans.py` | Multishot engine (guide-aware) |
| `~/Videos/bee_fpv_rain_20s/0808_231552_final.mp4` | 18 s dual success |
| `~/Videos/jc_promo_powerpack_30s/0808_220007_talkinghead.mp4` | 30 s dual success |
| Power Pack GitHub | docs: H3_QUALITY_STACK, PARALLEL_MASTER_K0, PERFORMANCE, CONTRIBUTORS (tonyd2wild) |

---

## 7. Resume checklist (copy when restarting)

```text
[ ] Read this file
[ ] Confirm whether test is co-tenant (DS4 up) or solo H3 (DS4 down)
[ ] If solo: stop DS4, drop_caches, verify free ~100G on each node
[ ] Phase A: single 362f/20-step arm → record t_arm
[ ] Phase B: dual multishot 4–8 × 362f
[ ] Phase C: only if 5 nodes free — smoke then optional 1h job
[ ] Phase D: restore 888k@0.76 ablit dual-serve
[ ] Append results table to section 8 below
```

---

## 8. Results log (fill in later)

| Date | Nodes | F | Steps | ESRGAN | Spans | Final length | Wall | Notes |
|------|------:|--:|------:|:------:|------:|-------------:|-----:|-------|
| | | | | | | | | |

---

## 9. One-liner for next agent

> **Future work (multi-node parallel):** dual-node path is enabled; scale-out is paused. Free DS4 → measure 362f/20-step arm time → scale multishot length as `N×(F/24)` with wall `ceil(N/nodes)×t_arm`. Co-tenant default stays ≤73f. Five Sparks ≈ one day wall per hour of full-quality film. Dual-serve credit: tonyd2wild. Roadmap: docs/FUTURE_WORK.md.
