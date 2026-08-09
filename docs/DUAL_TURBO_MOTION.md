# Dual Turbo sampling + Motion Context (high quality multishot)

## 1. Dual-sampler Turbo quality ([@ANe5s discussion #21](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/discussions/21))

Two-stage few-step sampling keeps Turbo speed while reducing artifacts:

| Stage | LoRA | Strength | Steps | Role |
|-------|------|----------|------:|------|
| **1 Rough** | `minimax_h3_turbo_4step_ckpt850.safetensors` (**non-EMA**) | **1.0** | default **4** (turbo-native; ANe5s often 5–7) | Layout, physics, motion (high-variance σ) |
| **2 Refine** | `minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors` | **0.7** | default **6** (ANe5s often 7–8) | Detail / de-blur (low-variance σ) |
| **Total** | | | **10** | `H3_TURBO_STEPS_ROUGH` + `H3_TURBO_STEPS_REFINE` |

**Do not** use EMA ckpt850 for stage 1 (ghosting). Strength refine **0.7** is a sharp threshold per ANe5s.
Ladder: speed `4+6=10` (default) → balanced `5+7=12` → quality `6+8=14`.

### Graph (per arm, on one H3)

```
UNET ─┬─ TurboLoRA ckpt850@1.0 → Sage→Sol→FBC → GuiderA → Sampler (high σ)
      └─ TurboLoRA ckpt500@0.7 → Sage→Sol→FBC → GuiderB → Sampler (low σ, latent from stage1)
BasicScheduler(total=rough+refine) → SplitSigmas(step=rough)
```

### Dual DGX Spark usage (one H3 instance per machine)

| Host | Instance | Role |
|------|----------|------|
| **10.100.10.2** (`H3_HEAD`) | 1× ComfyUI `:8188` | even keys / even arms (or all if MC) |
| **10.100.10.3** (`H3_WORKER`) | 1× ComfyUI `:8188` | odd keys / odd arms |

| Mode | What each box does |
|------|--------------------|
| **Parallel (default)** `H3_DUAL_TURBO=1` `H3_MOTION_CONTEXT=0` | Face keys + FLF arms in **waves of 2** across both Sparks → ~½ wall |
| **Motion-context** `H3_MOTION_CONTEXT=1` | Arms **sequential on HEAD** so audio latent continues; still dual-turbo per arm |

Each arm job still runs the **full** dual-stage graph (rough+refine) on its assigned box — not split stage1/stage2 across machines.

```bash
# dual-Spark parallel (recommended wall-clock)
H3_DUAL_TURBO=1 H3_MOTION_CONTEXT=0 bash deploy/keyspark/run_quality_parallel.sh

# seamless audio timeline (sacrifices arm parallelism)
H3_DUAL_TURBO=1 H3_MOTION_CONTEXT=1 bash deploy/keyspark/run_quality_parallel.sh
```

Cite **@ANe5s** if you publish results using this recipe.

---

## 2. Motion Context (audio continuity) — proper keyspark adaptation

**Repo:** [NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)

Pins previous clip’s last **22** frames + audio onto the next clip’s timeline so the model **continues the same waveform**, not a sound-alike.

### API graph wiring (implemented in `enhanced_graph.py`)

Upstream: [NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)

```
arm 1:    dual-turbo sample → SaveLatent(clip_index=1) → decode → SaveVideo
arm N>1:  scp prev arm → ComfyUI/input/mc_prev_arm{N-1}.mp4
          LoadVideo(file=basename) → GetVideoComponents → IMAGE + AUDIO
          MiniMaxH3ImageToVideo (first=K_i, last=K_{i+1})
          LoadLatent(folder=h3_context, clip_index=N-1) → context_latent  ★ seamless audio
          MotionContext(
            context_frames, context_audio, context_latent,
            audio_mode=timeline, encode_mode=video, anchor_mode=head,
            context_length=22, audio_context_length=22
          ) → Guider → dual-turbo sample
          SaveLatent(clip_index=N)
          decode → Trim(trim_frames, match_tail=true) → CreateVideo
```

| Setting | Value | Notes |
|---------|--------|--------|
| context_length | **22** | VAE grid; last 22 frames of prev |
| audio_context_length | **120** (~5s, nearly full arm) | pin almost entire prev soundtrack via `context_latent` |
| audio_mode | **timeline** | true waveform continue (not `ref` sound-alike) |
| natural_audio | **ON** (`H3_NATURAL_AUDIO=1`) | MC arms use denser dual-turbo **6+10** (not lean 4+6) |

**Natural audio policy (default):**
1. Pin ~full previous arm audio (120f) from Save/Load latent — not short 0.9s pin.
2. Arm1: dual-turbo as configured (fresh take).
3. Arms 2+: dual-turbo **6 rough + 10 refine** so Turbo invents less of the bed.
4. Nuclear option: `H3_MC_DENSE=1` → dense 16-step, no turbo on MC arms.

```bash
# natural soundtrack multishot
H3_MOTION_CONTEXT=1 H3_NATURAL_AUDIO=1 H3_AUDIO_CONTEXT_LENGTH=120 \
H3_DUAL_TURBO=1 H3_MC_STEPS_ROUGH=6 H3_MC_STEPS_REFINE=10 ...
# max audio fidelity (slower)
H3_MC_DENSE=1 H3_MC_STEPS=16 ...
```
| encode_mode | **video** | one VAE call for motion |
| anchor_mode | **head** | requires Trim |
| context_latent | **preferred** | Save/Load AV latent — skips lossy audio VAE re-encode |
| Spectrum | **ON** (v0.1.8 preliminary) | degree=1 + `bootstrap_first_forecast=true`; set `H3_SPECTRUM=0` only if issues |
| prev video | basename via `scp` → `ComfyUI/input/mc_prev_arm*.mp4` | native `LoadVideo` (not VHS) |
| latent slots | `output/h3_context/clip_0000N.safetensors` | Save/Load clip_index |

**Arms are sequential on HEAD** when MC is on (latents + prev video stay local). Dual-turbo still runs per arm; dual-box parallelism is for non-MC runs.

### Spectrum MiniMax H3 **v0.1.8** ([release](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3/releases/tag/v0.1.8))

Preliminary defaults (keyspark graph now uses these):

| Param | Value |
|-------|------:|
| degree | **1** |
| warmup_steps | **1** |
| tail_actual_steps | **1** |
| bootstrap_first_forecast | **true** |

Degree-4 aggressive preset must keep `bootstrap_first_forecast=false` (v0.1.8 rule).  
With MC we no longer force Spectrum off.

Install Spectrum: rsync tag `v0.1.8` into `custom_nodes/ComfyUI-Spectrum-MiniMax-H3` on both Sparks.  
Install Turbo+MC: `bash deploy/keyspark/setup_h3_turbo.sh`.

---

## 3. Credits

| Piece | Who |
|-------|-----|
| Dual-sampler Turbo recipe | **[@ANe5s](https://huggingface.co/ANe5s)** discussion #21 |
| Turbo LoRA training | [larryvrh/MiniMax-H3-Turbo-Lora](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora) |
| ComfyUI pruned Turbo weights | [QrusherZA/H3_Turbo_ComfyUI](https://huggingface.co/QrusherZA/H3_Turbo_ComfyUI) |
| Motion + audio chain | [NikoDemon80/ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) |
| Dual-H3 co-tenancy factory | [tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory) |
