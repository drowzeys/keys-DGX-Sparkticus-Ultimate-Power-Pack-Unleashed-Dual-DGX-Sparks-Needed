# Multishot + master K0 — high-fidelity parallel video

**Why this exists:** large **sequential** / continuous generations **hallucinate** over long
horizons. Multishot keyframes **matched to master K0**, then parallel short spans, is the
Power Pack production answer.

Upstream dual-serve co-tenancy (two Sparks, DS4 + dual H3) by **Tony / [tonyd2wild](https://github.com/tonyd2wild)** —  
[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).  
Master-K0 parallel multishot fidelity logic is the keyspark production path on that foundation.

---

## Problem: long generation hallucination

On MiniMax-H3 (and video DiTs generally), a **single long sequential sample** drifts:

- Face / identity morph mid-clip  
- Wardrobe and lighting walk  
- Prompt adherence collapses late in the shot  
- Lip-sync and scene continuity break  

Pushing one continuous ~30s (719f) job also **OOMs** under DS4 co-tenancy (safe span ≈ **≤73f** with ESRGAN). So “just generate longer on one box” fails both **quality** and **memory**.

---

## Solution: multishot keyframes rooted on master **K0**

### Pipeline (`h3-spans.py`, default `--kf-mode master-parallel`)

```
                    ┌──────────────┐
                    │  Master K0   │  serial — locks look / identity
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
        KF1←K0          KF2←K0          KFn←K0     parallel across .2 ‖ .3
           │               │               │
           └───────┬───────┴───────┬───────┘
                   ▼               ▼
            Span K0→K1      Span K1→K2 …     FLF2V short arms, parallel
                   │               │
                   └────── stitch (hard-cut / audio blend) ──────► final
```

| Step | What | Parallel? |
|------|------|-----------|
| 1 | Render **K0** (master keyframe) | No — serial lock |
| 2 | Render **K1…Kn** all **matched / rooted to K0** | **Yes** — both Sparks |
| 3 | Render spans FLF2V `first=K[i] last=K[i+1]` | **Yes** — worker pool per node |
| 4 | Stitch ordered spans | Local (ffmpeg) |

### Modes (for A/B)

| `--kf-mode` | Behavior | Verdict |
|-------------|----------|---------|
| **`master-parallel` (default)** | K0 master, then K1…n rooted in K0, parallel | **Best fidelity + speed** |
| `chain` | KF[i] from KF[i−1] serial | Drift accumulates along the chain |
| `rooted` | KF[i] from K0 but serial | Fidelity OK, slower |

Measured lab note (handoff): master-parallel **faster** (e.g. ~7.2 vs ~9.1 min KF phase) **and more consistent** than serial chain.

### Talking-head variant (`h3-talkinghead.py`)

Same fidelity idea without a full KF lattice:

- One **locked portrait** (master face ≈ K0) uploaded to both nodes  
- Each span is **ref2va** from that face + spoken line  
- Spans are independent → full dual-node parallel, hard-cut multishot  

---

## Why this beats large sequential generation

| | Large sequential / continuous | Multishot + master K0 + parallel spans |
|--|------------------------------|----------------------------------------|
| Hallucination | **High** late in the shot | **Low** — each span re-pins to KF endpoints / face |
| Dual Spark use | One node idle | **Both nodes work** |
| Wall clock | Sum of everything | ~**max** of concurrent arms (~2× heavy phase) |
| Co-tenant with DSV4F 0731 ablit | OOM risk at long length | Safe if span ≤73f @ util **0.76** / **888k** DS4 |

---

## Commands

```bash
# Multishot FLF, master-K0 keyframes (default), dual nodes
python3 comfy/h3-spans.py --plan story.json \
  --nodes 10.100.10.2:8188,10.100.10.3:8188 \
  --kf-mode master-parallel --upscale

# Face-locked talking-head multishot parallel
python3 comfy/h3-talkinghead.py --plan student_talkinghead_plan.json \
  --nodes 10.100.10.2:8188,10.100.10.3:8188
```

---

## Live dual-serve context (Power Pack)

While video runs, **DSV4F DSpark 0731 abliterated** stays up at:

- **888k** context (`max_model_len=909312`) — lucky number  
- **GPU mem util 0.76** — room for heretic H3 to shine  

Do not force 1M @ 0.85 on co-tenant boxes if you want this multishot path stable.

---

## Future work — multi-node parallel processing

**Today:** dual-node parallel is **enabled** (`--nodes .2,.3`, one heavy job per Spark).  
**Published design:** same master-K0 model on **5 Sparks** → **~1 hour of finished film per day is possible**.

```text
t_wall ≈ ceil(N_spans / N_nodes) × t_arm + t_KF + t_stitch
```

| Nodes | 1 h film wall (planning) | Film / day |
|------:|-------------------------:|-----------:|
| 2 | ~2 days | ~0.5 h |
| **5** | **~18–28 h** | **~1.0 h** |

→ **[FIVE_NODE_PARALLEL_HOUR_FILM.md](./FIVE_NODE_PARALLEL_HOUR_FILM.md)** (design + summary tables)  
→ [FUTURE_WORK.md](./FUTURE_WORK.md) · [H3_PARALLEL_CAPACITY_PROJECT.md](./H3_PARALLEL_CAPACITY_PROJECT.md)

---

## Credit

- Dual-serve co-tenancy (two Sparks, DS4 + dual H3): **Tony / tonyd2wild** — [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)  
- Master-K0 multishot parallel fidelity logic + heretic/ablit Power Pack wiring: keyspark  
 
