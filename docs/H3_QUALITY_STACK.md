# H3 quality stack — what we run (and what we don’t)

Production dual-Spark H3 is the **heretic + quality upgrade path**, not the few-step Turbo path.

Upstream dual-serve co-tenancy (DS4 + dual H3 on two Sparks): **Tony / [tonyd2wild](https://github.com/tonyd2wild)** —  
[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).

Live DS4 co-tenant: **DSV4F DSpark 0731 abliterated** @ **888k** (`max_model_len=909312`) · util **0.76**  
(so H3 has room to shine).

---

## Quality graph (in order)

```
UNET (fl2va / ref2va int8 convrot)
  → PathchSageAttentionKJ   (SageAttention 1.0.6, sage=auto)
  → SolAttnPatch            (NVIDIA Sol-engine / kijai Sol-Attn, SM121 Triton)
  → SpectrumApplyMiniMaxH3  (v0.2.1 — audio fix: offline_smoothing_replay=true)
  → H3FirstBlockCache       (FBC, start_step≥3 on dense)
  → sampler (res_multistep, dense 20 steps for quality)
  → VAE decode (+ batched VAE where present)
  → optional Motion Context (multishot audio/motion continuation)
  → RealESRGAN ×2
```

**TE (always heretic on this pack):**  
`H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors`

Templates: `h3-r2v-heretic-enhanced.json`, `jc-baseline-workflow-api.json`, `enhanced_graph.py`.

---

## Component notes

### 1. NVIDIA Sol-engine / Sol-Attn (Blackwell GB10)

| Piece | Path / node | Role |
|-------|-------------|------|
| **ComfyUI_sol-attn_Blackwell** | `custom_nodes/ComfyUI_sol-attn_Blackwell` | Sol-Attn model patch, H3-specific ports, **H3FirstBlockCache**, batched VAE |
| **ComfyUI-SolAttn_triton** | `custom_nodes/ComfyUI-SolAttn_triton` | Triton / Sol-Attn kernels for SM121 |
| Node | `SolAttnPatch` | e.g. tau=1.3, int8_qk, TMA, sink exact_kv_and_rows |

Related lineage: keys SM121 Sol-engine recipes (kijai SolAttn + Triton on single Spark), wired here for dual co-tenancy.

### 2. SageAttention (KJ node — not CLI flag)

| | |
|--|--|
| Package | `sageattention==1.0.6` (aarch64-friendly) |
| Node | `PathchSageAttentionKJ` with `sage_attention=auto` |
| **Never** | Comfy launch flag `--use-sage-attention` → **pure noise on H3** |

Sol-Attn `int8_qk` already covers a large INT8 path; Sage sits earlier in the chain for the quality stack.

### 3. Spectrum update + **audio fix**

| | |
|--|--|
| Package | `ComfyUI-Spectrum-MiniMax-H3` **v0.2.1** |
| Node | `SpectrumApplyMiniMaxH3` |
| **Audio fix** | `offline_smoothing_replay=**true**` (default on v0.2.1) |

That default is the validated path that kills degraded / stuttery speech on bad seeds while keeping video quality. Do **not** leave a pre-v0.2 bak under `custom_nodes/` (it shadows the node schema).

ref2va: Spectrum **`degree=1`** and **`warmup_steps≤1`** required.

### 4. Motion continuation

| | |
|--|--|
| Package | `ComfyUI-H3-Motion-Context` ([NikoDemon80](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)) |
| Role | Chain audio + motion across multishot arms (continuation), not a substitute for master-K0 identity pins |
| Use | Multishot / MC workflows when seamless audio bed matters; combine with short spans |

Motion Context continues the *timeline*; **master-K0 multishot** still owns identity fidelity (see [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md)).

### 5. Triton upgrades

| Piece | Role |
|-------|------|
| SolAttn **Triton** tree | SM121-safe kernels for Sol-Attn on GB10 |
| Sage 1.0.6 | Pure-Python/Triton wheel on aarch64 (full Sage 2.x CUDA needs local build if you want sageattn3) |
| Inductor / H3 VAE batch ports | In sol-attn Blackwell tree (`h3_vae_batch`, inductor fixes) |

### 6. Multishot / parallel (fidelity)

Not a custom_node, but required production logic:

- Multiple keyframes **matched to master K0**  
- Short FLF / ref2va spans in **parallel** on two Sparks  
- Avoids **long sequential hallucination**  

→ [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md)

---

## 🚫 Turbo LoRA — **not** for quality

We evaluated MiniMax-H3 **Turbo** LoRAs (few-step 4–8, dual-sampler “HQ” recipes, etc.).

| Path | Verdict |
|------|---------|
| **Dense 20-step + Spectrum audio fix + Sol/Sage/FBC + heretic TE + ESRGAN** | **Quality default** |
| **Turbo LoRA / few-step** | **Not used for quality deliverables** — speed-oriented; fidelity/lip/detail not competitive with dense |

Turbo nodes/weights may still exist on disk for experiments, but **Power Pack production and docs treat Turbo as non-quality**. Prefer:

```bash
# quality: dense steps, no H3_TURBO
H3_TURBO=0 H3_DUAL_TURBO=0 python3 comfy/h3-talkinghead.py --plan ...
# or h3-spans.py --upscale without turbo env
```

Do not enable `H3_TURBO=1` / `H3_DUAL_TURBO=1` for customer-facing or “gold” clips.

---

## Install map (custom_nodes on each Spark)

```text
~/h3-cotenancy/ComfyUI/custom_nodes/
  ComfyUI_sol-attn_Blackwell/     # Sol-engine + FBC + VAE batch
  ComfyUI-SolAttn_triton/         # Triton Sol-Attn
  ComfyUI-Spectrum-MiniMax-H3/    # v0.2.1 audio fix
  ComfyUI-KJNodes/                # PathchSageAttentionKJ
  ComfyUI-H3-Motion-Context/      # motion/audio continuation
  ComfyUI-H3-Multishot/           # multishot helpers
  ComfyUI-MiniMax-H3-Turbo/       # present optional — NOT quality default
  comfyui-videohelpersuite/
```

Bring-up helper: `deploy/keyspark/setup_h3_enhanced.sh` (rsync Sol/Spectrum/KJ/heretic TE; restart Comfy).

---

## Smoke checklist

```bash
for ip in 10.100.10.2 10.100.10.3; do
  curl -sf "http://$ip:8188/object_info" | python3 -c '
import sys,json
d=json.load(sys.stdin)
for n in ["PathchSageAttentionKJ","SolAttnPatch","SpectrumApplyMiniMaxH3",
          "H3FirstBlockCache","MiniMaxH3MotionContext","MiniMaxH3ImageToVideo"]:
  print(n, "OK" if n in d else "MISSING")
'
  curl -sf "http://$ip:8188/object_info/SpectrumApplyMiniMaxH3" | python3 -c '
import sys,json
j=json.load(sys.stdin); k=next(iter(j))
f=j[k]["input"].get("optional",{}).get("offline_smoothing_replay") or j[k]["input"].get("required",{}).get("offline_smoothing_replay")
print("offline_smoothing_replay", f)
'
done
```

Expect Spectrum default **`offline_smoothing_replay: true`**.

---

## Credit

| Piece | Who |
|-------|-----|
| Dual-serve DS4+dual H3 | **Tony / tonyd2wild** |
| Sol-engine / SolAttn / Triton / FBC wiring on GB10 | NVIDIA Sol-engine lineage + kijai/ports + keyspark wiring |
| Spectrum v0.2.1 audio fix | Spectrum MiniMax H3 authors |
| Motion Context | NikoDemon80 |
| SageAttention | SageAttention + KJNodes PathchSage |
| Heretic TE | sakamakismile (and related) |
| **Turbo LoRA** (not quality path) | larryvrh / QrusherZA / ANe5s — kept experimental only |
