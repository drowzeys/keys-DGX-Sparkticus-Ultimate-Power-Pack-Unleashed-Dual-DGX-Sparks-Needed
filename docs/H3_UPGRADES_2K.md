# H3 upgrades — 2K via upscale, parallel multishot, A/V fixes, realism

**Status:** shipped in Power Pack (2026-08-11)  
**Sample workflow:** [comfy/workflows/anime_2k_bench/](../comfy/workflows/anime_2k_bench/)  
**Hugging Face package (pinned stack + scripts):** https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks  
**Docker (pinned Comfy+nodes):** `ghcr.io/drowzeys/keys-2k-minimax-h3-parallel-two-dgx-sparks:0.31.1-pp20260811`  
**Agent one-shot (DS4+H3+2K):** [AGENT_ONESHOT_RECIPE.md](./AGENT_ONESHOT_RECIPE.md)  
**Dual-serve foundation:** [tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory) (Tony)

This note is the operator + agent map for the post–Power-Pack H3 quality
upgrades: how to get **delivery 2K**, **dual-Spark parallelism**, **audio/video
glitch mitigations**, **motion/context loop** packs, and **realism LoRA** without
breaking DS4 co-tenancy.

---

## 1. 2K reality on open MiniMax-H3

| Approach | Works locally? | Notes |
|----------|:--------------:|-------|
| Cloud MiniMax “native 2K” API | N/A (hosted) | Closed weights / credits |
| Open int8 convrot denoise at 2K | ❌ | OOM / illegal dims / hard caps |
| **704×1280 denoise → ESRGAN ×2 → ~1408×2560** | ✅ | **Power Pack path** |
| 720×1280 | ❌ | Not multiple of 32 — kills jobs |

**Rule:** native width/height must be multiples of **32**. Prefer **704×1280**
portrait for the anime 2K bench; landscape benches often use **864×480** then ×2.

```text
Native (legal)     ESRGAN×2        Delivery label
704 × 1280    →    1408 × 2560     “2K” portrait
864 × 480     →    1728 × 960      “2K-class” landscape
```

---

## 2. Parallel multishot (master-K0)

Long single-shot gens **hallucinate**. Production path:

1. Plan **keyframes K0…Kn** (identity pins)  
2. Render **K0** first (master)  
3. Render **K1…Kn** **in parallel** on both Sparks, each rooted on **K0**  
4. Render **FL2VA spans** `first=K[i] last=K[i+1]` **in parallel** (one heavy job / node)  
5. Hard-cut stitch (prev last == next first)

Engine: `comfy/h3-spans.py --kf-mode master-parallel --upscale`  
Doc: [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md)

**Lab timing (anime 2K bench `0811_012837`, `.1`+`.5` co-tenant DS4):**

| Phase | Wall |
|-------|------|
| Identity + 4 KF | ~96–168 s each |
| 3 parallel spans | **~8.9 min** (serial would be ~13+ min) |
| **Total** | **~18.8 min** for ~4.8 s @ 704×1280 |

---

## 3. Audio / video glitch fixes

### 3.1 Spectrum v0.2.1 (in-graph, loaded)

| Knob | Quality default | Why |
|------|-----------------|-----|
| `offline_smoothing_replay` | **`true`** | Offline replay isolates video spectral blend from joint A/V trajectory — **restores clean speech** on the seed that stuttered in single-pass |
| `audio_blend_weight` | **`0`** | No spectral mix of audio rows |
| `blend_weight` | `0.5` | Video spectral share |
| `degree` / `warmup_steps` | `1` / `1` | Performance default; raise for fragile ref2va |

Pinned in all `jc-*-api.json` graphs and `anime_2k_bench` package.

Smoke:

```bash
curl -sf http://HEAD:8188/object_info/SpectrumApplyMiniMaxH3 | python3 -c '
import sys,json
j=json.load(sys.stdin); k=next(iter(j))
bag=j[k]["input"].get("required",{})|j[k]["input"].get("optional",{})
f=bag["offline_smoothing_replay"]
print(f[1].get("default") if isinstance(f[1],dict) else f)
'
# expect True
```

### 3.2 Motion / tympanic bed continuity (multishot seams)

| Pack | Role | Upstream |
|------|------|----------|
| `ComfyUI-H3-Motion-Context` | Pin tail picture+audio into next clip | [NikoDemon80](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) |
| `ComfyUI-H3-Motion-Context-MultiRef` | MultiRef + **custom keyframes** (lazy patches) | [seitanism fork](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef) |
| `ComfyUI-MiniMaxH3-Contex-Loop` **v0.3.8** | Scene loop, checkpoint, review, assemble | [ethanfel](https://github.com/ethanfel/ComfyUI-MiniMaxH3-Contex-Loop) |
| `ComfyUI-NKD-Preview-Tools` **v3.3.0** | Timeline / popup / scrub viewer | [Nekodificador](https://github.com/Nekodificador/ComfyUI-NKD-Preview-Tools) |

**Install then restart Comfy** (custom nodes load only at process start).  
`deploy/keyspark/setup_h3_enhanced.sh` rsyncs these packs when present under
`~/comfy/ComfyUI/custom_nodes/`.

### 3.3 What is *not* an A/V fix

- Turbo / few-step LoRA (speed only — leave **off**)  
- Hard-cut multishot **without** any motion/context pin (seams can pop)  
- Spectrum single-pass research mode (`offline_smoothing_replay=false`)

---

## 4. Realism-People LoRA

| | |
|--|--|
| File | `h3-realism-people-t2v-i2v-r2v.safetensors` |
| Comfy path | `models/loras/` on **each** Spark |
| Trigger | `r34l1sm` (in prompt when desired) |
| Graph | `LoraLoaderModelOnly` → Sage → Sol → Spectrum → FBC |
| Package toggle | `REALISM=1 bash …/run_anime_2k_bench.sh` |

**Caution:** LoRA is bf16-trained; DiTs are **int8+convrot**. Expect imperfect
apply — A/B with `REALISM=0`. Not a substitute for heretic TE.

Weights are **not** redistributed in this git repo.

---

## 5. Full quality graph order

```text
UNET (fl2va / ref2va int8 convrot)
  → [optional] LoraLoaderModelOnly   # realism people
  → PathchSageAttentionKJ            # Sage auto
  → SolAttnPatch                     # Sol-engine / Triton
  → SpectrumApplyMiniMaxH3           # v0.2.1 audio fix knobs
  → H3FirstBlockCache
  → dense sampler ~20 steps (res_multistep)   # NOT Turbo
  → VAE video + audio decode
  → [optional] Motion Context / Contex-Loop chain
  → RealESRGAN ×2                    # delivery 2K
  → CreateVideo / SaveVideo
```

---

## 6. Benchmark notes (lab)

### 6.1 Speed — 5s continuous 864×480×124f, 20 steps

| Lane | Time | s/step |
|------|------|--------|
| `.1` GB10 **co-tenant DS4** | **297 s** | ~13 |
| Solo cool-chip baseline | 202.5 s | 8.09 |
| Mac M3 Ultra h3.c dense bf16 | ~1,115 s | 52.4 |

Clips under operator `~/Videos/h3-benchmark/` (`mac_*`, `node1.5_*`).

### 6.2 Anime multishot 2K bench

See [anime_2k_bench sample](../comfy/workflows/anime_2k_bench/sample/) — run
`0811_012837`, dual `.1`+`.5`, master-parallel, **18.8 min** wall.

---

## 7. Co-tenancy (do not regress)

| Knob | Value |
|------|-------|
| DS4 first, H3 second | hard order |
| `GPU_MEMORY_UTILIZATION` | **0.76** (888k lucky) on Power Pack default |
| Fleet hard util cap | **0.85** |
| H3 | `--disable-pinned-memory --reserve-vram 48 --vram-headroom 10` |
| Span length with ESRGAN | ≤**73f** under DS4 co-tenancy |
| Fleet H3 concurrency | **2** = one heavy job per Spark |

Env: `deploy/keyspark/env.ablit-cotenancy-888k-u076`  
Alt pair: `env.ablit-cotenancy-888k-u076-nodes-1-5` (`.1` head + `.5` worker)

---

## 8. Install checklist (each Spark)

```bash
# from a machine with SSH to HEAD/WORKER and ~/comfy/ComfyUI as source of truth
bash deploy/keyspark/setup_h3_enhanced.sh

# confirm nodes
for ip in $HEAD $WORKER; do
  curl -sf http://$ip:8188/object_info | python3 -c '
import sys,json
d=json.load(sys.stdin)
for n in ["PathchSageAttentionKJ","SolAttnPatch","SpectrumApplyMiniMaxH3",
          "H3FirstBlockCache","MiniMaxH3MotionContext","ImageUpscaleWithModel",
          "LoraLoaderModelOnly"]:
  print(n, "OK" if n in d else "MISSING")
'
done
```

After adding Contex-Loop / MultiRef / NKD, **restart Comfy** so `object_info`
lists the new classes.

---

## 9. Quick start for users

```bash
git clone https://github.com/drowzeys/keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed.git
cd keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed

# 1) dual-serve bring-up (Tony order: DS4 → H3)
export ENV_SRC=$PWD/deploy/keyspark/env.ablit-cotenancy-888k-u076
export STACK=ablit HEAD=10.100.10.2 WORKER=10.100.10.3   # or .1/.5 profile
bash deploy/keyspark/bringup.sh

# 2) 2K parallel anime bench
export HEAD WORKER
bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh

# optional realism
REALISM=1 bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh
```

---

## Credits (upgrade surface)

| Piece | Credit |
|-------|--------|
| Dual-serve co-tenancy | **Tony / tonyd2wild** |
| Spectrum audio fix v0.2.1 | xmarre / Spectrum MiniMax H3 |
| Motion Context | NikoDemon80 |
| Motion Context MultiRef | seitanism fork |
| Contex Loop | ethanfel (+ Niko lineage) |
| NKD Preview Tools | Nekodificador |
| Sol-engine / SolAttn | NVIDIA + community Triton ports |
| Sage | SageAttention + KJNodes |
| Heretic TE | sakamakismile et al. |
| 2K bench packaging | keyspark Power Pack |
