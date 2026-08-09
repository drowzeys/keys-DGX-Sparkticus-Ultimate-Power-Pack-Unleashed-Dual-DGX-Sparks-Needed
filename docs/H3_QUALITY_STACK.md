# H3 quality stack — full optimization checklist

Everything below is **in** the Power Pack dual-Spark heretic H3 path (production).  
**Turbo LoRA is not** (speed experiments only).

**Dual-serve co-tenancy** (DS4 + dual H3 on two Sparks): **Tony / [@tonyd2wild](https://github.com/tonyd2wild)** —  
[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory) · listed in [CONTRIBUTORS.md](../CONTRIBUTORS.md).

**Live DS4 co-tenant:** DSV4F DSpark **0731 abliterated** @ **888k** (`max_model_len=909312`) · util **0.76**  
(room for H3 to shine).

---

## Checklist (must all be present)

| # | Optimization | Status | Where |
|---|--------------|:------:|-------|
| 1 | **NVIDIA Sol-engine** / agent-native kernel path on GB10 | ✅ | `ComfyUI_sol-attn_Blackwell` + Sol stack (see NVIDIA [Sol Engine / H3 on-device](https://nvlabs.github.io/Sana/Sol-Engine/H3-OnDevice/)) |
| 2 | **SolAttn** (`SolAttnPatch`) | ✅ | int8_qk, TMA, tau≈1.3, sink exact — `ComfyUI_sol-attn_Blackwell` |
| 3 | **Triton upgrades** (SM121 SolAttn kernels) | ✅ | `ComfyUI-SolAttn_triton` + Blackwell sol_attn tree |
| 4 | **Sage node** (`PathchSageAttentionKJ`) | ✅ | `sageattention==1.0.6`, `sage_attention=auto` via KJNodes — **never** `--use-sage-attention` CLI |
| 5 | **Spectrum update** | ✅ | `ComfyUI-Spectrum-MiniMax-H3` **v0.2.1** |
| 6 | **Audio fix** | ✅ | Spectrum `offline_smoothing_replay=**true**` (v0.2.1 default + forced in templates/graphs) |
| 7 | **Motion continuation** | ✅ | `ComfyUI-H3-Motion-Context` (NikoDemon80) — optional on multishot audio bed |
| 8 | **H3FirstBlockCache (FBC)** | ✅ | In sol-attn Blackwell package |
| 9 | **Heretic TE** | ✅ | `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` |
| 10 | **Master-K0 multishot parallel** | ✅ dual / 🔜 N-node | Short spans vs long-gen hallucination — [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md); scale-out [FUTURE_WORK.md](./FUTURE_WORK.md) |
| 11 | **RealESRGAN ×2** | ✅ | Inline upscale on quality graphs |
| ❌ | **Turbo LoRA / few-step** | **Not quality** | May be installed; **do not use** for deliverables |

Live Comfy `object_info` on both Sparks should show:  
`PathchSageAttentionKJ`, `SolAttnPatch`, `SpectrumApplyMiniMaxH3`, `H3FirstBlockCache`,  
`MiniMaxH3MotionContext` (+ Trim/Save/Load latent), `MiniMaxH3ImageToVideo` / `ReferenceToVideo`.

---

## Quality graph (order)

```
UNET (fl2va / ref2va int8 convrot)
  → PathchSageAttentionKJ     # Sage node
  → SolAttnPatch              # NVIDIA Sol-engine / SolAttn + Triton
  → SpectrumApplyMiniMaxH3    # v0.2.1 + offline_smoothing_replay=true (AUDIO FIX)
  → H3FirstBlockCache         # FBC / cross-step cache family
  → dense sampler (res_multistep, ~20 steps)   # NOT Turbo
  → VAE decode (+ batched VAE when present)
  → [optional] Motion Context continuation
  → RealESRGAN ×2
```

**TE:** heretic only — `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors`

---

## Component detail

### NVIDIA Sol-engine + SolAttn + Triton

| Piece | Role |
|-------|------|
| Sol-engine (NVIDIA) | Full-stack kernel optimization / Sol-Attn / caching recipe for MiniMax-H3 on Spark-class GPUs |
| `SolAttnPatch` | Model-side Sol attention (int8 QK, TMA, sink conditioning) |
| `ComfyUI-SolAttn_triton` | Triton kernels for SM121 GB10 |
| Batched VAE / inductor ports | In Blackwell sol-attn tree |

Lineage also documented in keys single-Spark Sol-engine Comfy recipe repos; dual-boot wires the same nodes under Tony’s co-tenancy.

### Sage node

| | |
|--|--|
| Node | `PathchSageAttentionKJ` |
| Package | `sageattention==1.0.6` |
| Mode | `auto` |
| Forbidden | `main.py --use-sage-attention` → **noise** on H3 |

### Spectrum update + audio fix

| | |
|--|--|
| Version | **v0.2.1** |
| Node | `SpectrumApplyMiniMaxH3` |
| **Audio fix** | `offline_smoothing_replay=true` |
| ref2va | `degree=1`, `warmup_steps≤1`, `bootstrap_first_forecast=true` |

Pinned in:

- `~/comfy/h3-r2v-heretic-enhanced.json`
- `~/comfy/jc-baseline-workflow-api.json` / `jc-noupscale-api.json`
- `deploy/keyspark/enhanced_graph.py` → `_spectrum_inputs()`

Do not leave `ComfyUI-Spectrum-MiniMax-H3.bak*` under `custom_nodes/` (schema shadow).

### Motion continuation

| | |
|--|--|
| Package | [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) |
| Nodes | `MiniMaxH3MotionContext`, Trim, SaveLatent, LoadLatent |
| Use | Multishot audio/motion bed continuity |
| With | Short spans + master-K0 (or locked face); not a replacement for identity pins |

### Multishot fidelity (not a custom_node)

Long sequential gens **hallucinate**. Production: **multiple keyframes matched to master K0**, short FLF/ref2va spans in **parallel** on two Sparks.

→ [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md)

---

## 🚫 Turbo LoRA — not for quality

| Path | Use |
|------|-----|
| Dense 20-step + full stack above | **Quality default** |
| Turbo LoRA / dual-sampler few-step | **Speed experiments only** — rejected for quality deliverables |

```bash
export H3_TURBO=0 H3_DUAL_TURBO=0
```

---

## Install map (each Spark)

```text
~/h3-cotenancy/ComfyUI/custom_nodes/
  ComfyUI_sol-attn_Blackwell/      # Sol-engine ports + FBC + VAE batch
  ComfyUI-SolAttn_triton/          # Triton SolAttn
  ComfyUI-Spectrum-MiniMax-H3/     # v0.2.1 audio fix
  ComfyUI-KJNodes/                 # Sage PathchSageAttentionKJ
  ComfyUI-H3-Motion-Context/       # motion continuation
  ComfyUI-H3-Multishot/
  ComfyUI-MiniMax-H3-Turbo/        # optional — NOT quality default
  comfyui-videohelpersuite/
```

Setup: `bash deploy/keyspark/setup_h3_enhanced.sh`

---

## Smoke

```bash
for ip in 10.100.10.2 10.100.10.3; do
  curl -sf "http://$ip:8188/object_info" | python3 -c '
import sys,json
d=json.load(sys.stdin)
for n in ["PathchSageAttentionKJ","SolAttnPatch","SpectrumApplyMiniMaxH3",
          "H3FirstBlockCache","MiniMaxH3MotionContext","MiniMaxH3ReferenceToVideo"]:
  print(n, "OK" if n in d else "MISSING")
'
  curl -sf "http://$ip:8188/object_info/SpectrumApplyMiniMaxH3" | python3 -c '
import sys,json
j=json.load(sys.stdin); k=next(iter(j))
for bag in (j[k]["input"].get("required",{}), j[k]["input"].get("optional",{})):
  if "offline_smoothing_replay" in bag:
    f=bag["offline_smoothing_replay"]
    d=f[1].get("default") if isinstance(f,list) and len(f)>1 and isinstance(f[1],dict) else f
    print("offline_smoothing_replay default=", d)
'
done
```

Expect **offline_smoothing_replay default = True**.

---

## Credits

| Piece | Credit |
|-------|--------|
| Dual-serve | **Tony / tonyd2wild** (contributor) |
| NVIDIA Sol-engine | NVIDIA Sol Engine / H3 on-device work |
| SolAttn + Triton | kijai / Triton ports + Blackwell packaging |
| Spectrum audio fix | Spectrum MiniMax H3 v0.2.1 authors |
| Sage | SageAttention + KJNodes |
| Motion Context | NikoDemon80 |
| Heretic TE | sakamakismile et al. |
| Turbo (not quality) | larryvrh / QrusherZA / ANe5s — experimental only |
