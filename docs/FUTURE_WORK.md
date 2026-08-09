# Future work — multi-node parallel processing

**Status:** **Planned / enabled path** — design locked; full N-node farm **not yet measured**  
**Published design:** [FIVE_NODE_PARALLEL_HOUR_FILM.md](./FIVE_NODE_PARALLEL_HOUR_FILM.md) — **~1 h film / day on 5 Sparks is possible**  
**Primary vehicle:** [H3_PARALLEL_CAPACITY_PROJECT.md](./H3_PARALLEL_CAPACITY_PROJECT.md)  
**Last updated:** 2026-08-09  

---

## Headline (published)

| Nodes | 1 h film wall (planning) | Film per calendar day |
|------:|-------------------------:|----------------------:|
| 2 | ~2 days | ~0.5 h |
| **5** | **~18–28 h** | **~1.0 h** |

Summary tables A–G: **[FIVE_NODE_PARALLEL_HOUR_FILM.md](./FIVE_NODE_PARALLEL_HOUR_FILM.md)**

---

## What is already shipping (today)

| Capability | Nodes | Status |
|------------|------:|--------|
| Dual-serve DS4 + dual H3 co-tenancy | **2** | ✅ Live (Tony foundation + Power Pack) |
| Master-K0 multishot + short FLF/ref2va spans | **2** | ✅ Production default |
| Worker-per-node task pool (`--nodes a,b`) | **2** | ✅ Scripts accept a node list |
| Co-tenant span cap ≤73f (+ESRGAN) | **2** | ✅ Measured RAM law |
| Quality stack (heretic TE, Sage, Sol, Spectrum audio, FBC, ESRGAN) | **2** | ✅ See [H3_QUALITY_STACK.md](./H3_QUALITY_STACK.md) |

Dual-node parallel is **enabled and proven**. The gap is **scaling the same model past two Sparks** and **solo-H3 long arms** (~350f) when DS4 is not co-resident.

---

## Future work (multi-node parallel scale-out)

### Goal

Run the **same** quality multishot pipeline across **N Sparks** (target lab: **5**), so wall clock scales as:

```text
t_wall ≈ ceil(N_spans / N_nodes) × t_arm + t_KF + t_stitch
```

Quality does **not** change with more nodes — only how many arms finish per wave.

### Scope

| Item | Description | Priority |
|------|-------------|----------|
| **N-node fleet list** | Generalize `--nodes` / `H3_FLEET_CONCURRENCY` beyond `.2`+`.3` (3–5 Sparks) | P0 |
| **Solo-H3 long arms** | Pause DS4 → measure **362f / 20-step** (grid snap of ~350f) with full quality stack | P0 |
| **Phase A baseline** | Record `t_arm` (ESRGAN on/off) → fill capacity formula | P0 |
| **Phase B dual @ ~350f** | 4–8 spans multishot master-K0 on 2 free-UMA nodes | P1 |
| **Phase C five-node farm** | Smoke 10 spans → optional **1 hour film** (~247 × 350f-class arms) | P1 |
| **Orchestrator hardening** | Retry/requeue failed arms, per-node health, wave barriers | P2 |
| **Capacity tables** | Publish measured wall vs node count in [PERFORMANCE…](./PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md) | P2 |
| **Continuous hero path** | Document “pause DS4 → continuous → restore dual-serve” recipe | P2 |

### Explicit non-goals (for this future track)

- Turbo LoRA for **quality** deliverables (speed-only path stays separate)  
- Stealing co-tenant boxes past fleet util **0.85** or past the **0.76** ablit headroom profile  
- Claiming 5-node hour-film wall times before Phase A `t_arm` is measured  

### Planning numbers (until measured)

| Nodes | Waves for ~247 spans | Est. wall @ ~24 min/arm | Film / day |
|------:|---------------------:|------------------------:|-----------:|
| 1 | 247 | multi-day | ~0.2 h |
| 2 | 124 | ~2 days | ~0.5 h |
| **5** | **50** | **~18–28 h** | **~1.0 h** |

Rule of thumb: **~1 hour finished full-quality film per ~1 calendar day on 5× H3 is possible.**  
Full summary tables: [FIVE_NODE_PARALLEL_HOUR_FILM.md](./FIVE_NODE_PARALLEL_HOUR_FILM.md).

### Design principles (already decided)

1. **Parallel does not reduce quality** — identical graph/steps per arm.  
2. **Total length = stitch of arms**, not one giant sample.  
3. **Long continuous hallucination** → keep **master-K0 / face-lock multishot** for long form.  
4. **H3 length grid:** use **345** or **362**, not raw 350.  
5. **Co-tenant (DS4 up):** stay ≤**73f** (+ESRGAN). Long arms only when DS4 is down (or on a free Spark).  
6. **One heavy job per Spark** (`H3_FLEET_CONCURRENCY = N_nodes`).  

### Credit

Dual-serve co-tenancy foundation: **Tony / [@tonyd2wild](https://github.com/tonyd2wild)** —  
[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).  
N-node scale-out is keyspark future work **on top of** that foundation, not a replacement for it.

---

## How to pick this up

1. Read [H3_PARALLEL_CAPACITY_PROJECT.md](./H3_PARALLEL_CAPACITY_PROJECT.md) (test plan Phases A–D).  
2. Confirm co-tenant vs solo-H3 mode.  
3. Run Phase A (single 362f/20-step arm) → write `t_arm` into the results log.  
4. Scale node list only after dual multishot at long arms is clean.  
5. Restore dual-serve: `deploy/keyspark/env.ablit-cotenancy-888k-u076` (888k @ util **0.76**).

### Resume one-liner

> **Future work:** multi-node parallel processing is **enabled** on the dual path; **scale-out to 3–5 Sparks** + long solo arms (~362f/20) is the next capacity track. Measure `t_arm` first, then `ceil(N/nodes)×t_arm`. Co-tenant default remains ≤73f. Dual-serve credit: tonyd2wild.

---

## Related docs

| Doc | Role |
|-----|------|
| **[FIVE_NODE_PARALLEL_HOUR_FILM.md](./FIVE_NODE_PARALLEL_HOUR_FILM.md)** | **Published 5-node design + hour/day claim + tables A–G** |
| [H3_PARALLEL_CAPACITY_PROJECT.md](./H3_PARALLEL_CAPACITY_PROJECT.md) | Detailed phases, formulas, results log |
| [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md) | Fidelity model (why multishot, not one long gen) |
| [H3_QUALITY_STACK.md](./H3_QUALITY_STACK.md) | Quality path (no Turbo) |
| [PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md](./PERFORMANCE_STOCK_VS_ABLIT_HERETIC.md) | Today’s dual-node timing tables |
