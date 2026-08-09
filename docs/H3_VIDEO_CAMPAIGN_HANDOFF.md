# H3 Dual-Spark Video Campaign — HANDOFF

_Last updated: 2026-08-08, before a full-cluster reboot. Written on head node `spark-13b3`._

## TL;DR
We built a **face-locked, lip-synced, on-camera talking-head video pipeline** that runs on
**two DGX Sparks co-resident with a live DeepSeek-V4-Flash (DSV4F) serve**, with **inline ESRGAN
upscale to 1152×1536**, rendering spans in parallel across the two nodes. All optimizations live
on disk and survive reboot. One re-render is pending (to bake in the Spectrum audio fix).

## Cluster / topology
- **Head: `spark-13b3` = node1 = 10.100.10.4** (this machine). All scripts + finished videos live
  here under `~/comfy/` and `~/Videos/`. Runs a single-H3 ComfyUI when needed.
- **`spark-7552` = 10.100.10.2** and **`spark-0060` = 10.100.10.3**: the render pair. Each runs
  ComfyUI (`~/h3-cotenancy/ComfyUI`, port :8188) **co-resident with DSV4F** (vLLM TP=2, API on
  `.2:8888`; `.3:8888` is the TP worker and correctly shows DOWN).
- DSV4F config: 888k context, GPU mem util **0.76** (deliberately lowered from the universal 0.85
  to leave headroom for H3 — do NOT restore 0.85 on these nodes).

## Operating perimeter (HARD limits — learned from 2 OOM→reboot incidents)
- **Exactly 2 nodes co-resident with DSV4F. Never borrow a 3rd.**
- **Inline-upscale span length: 73 frames MAX** (measured RAM floor 5 GB). 56f is the robust
  default (6 GB floor). **90f OOMs → `panic_on_oom` reboots the node.** H3 length snaps to the
  17k+5 grid: valid = 5,22,39,56,73,90,... (so "50f"→56, "60/70f"→73).
- Memory is **per-span, not per-batch** (nodes render one span each at a time).
- Always run the **RAM guard** (`scratchpad/ram_guard.sh` pattern): interrupt ComfyUI at <4 GB
  free to protect DSV4F. OOM here = reboot, so be conservative.
- Each **scene ≥10 s**, built from multiple spans (4×73f = 12.2 s); location changes only between
  scenes.

## The winning architecture (validated)
**Face-lock via ref2va.** `MiniMaxH3ReferenceToVideo` + the `minimax_h3_ref2va` model: generate
ONE locked portrait, then every span is a ref2va generation from that same `ref_images.ref_image_0`
with prompt "Use <Picture 1> as the person (keep this exact face)". Identity holds across scenes;
lip-sync is native (no FLF2V mouth-pinning to fight). This fixed the identity drift that the
fl2va+keyframe approach (`h3-spans.py`) had across multi-scene narratives.

Wiring gotchas:
- `ref_images.ref_image_0` is a **flat dotted key** in API JSON (not nested).
- Remove the template's stock ref `LoadImage` nodes.
- ref2va path REQUIRES Spectrum node **`degree==1` AND `warmup_steps<=1`** (else
  "bootstrap_first_forecast requires ..." error).
- ref2va has **no first/last-frame input** → spans join by cuts (fine for talking-head).
- No keyframe-planning phase → ~26 min for a 36 s video (vs 45 min for the fl2va keyframe pipeline).

## Dual-node parallelism (preserved in the scripts, both stages)
The two-Spark parallelism is encoded in the head-node pipeline scripts (default
`--nodes 10.100.10.2:8188,10.100.10.3:8188`), so it's reusable for every future creation:
- **Keyframe generation — parallel:** `h3-spans.py --kf-mode master-parallel` (default). KF0
  (master) renders serially to lock the look; KF1..KFn then fan across both nodes concurrently,
  all rooted in KF0. A/B verdict: faster (7.2 vs 9.1 min) AND more consistent than the serial
  chain (chain accumulates identity drift).
- **Video/span generation — parallel:** every pipeline (`h3-talkinghead.py`, `h3-spans.py`,
  `h3-multishot.py`, `h3-parallel.py`) renders spans across both nodes via a worker-per-node
  task pool. Measured ~2× (e.g. 13 spans in 26 min vs ~170 min serial). `h3-talkinghead.py`
  has no keyframe phase — each ref2va span is independent, so all spans parallelize directly.
Memory is per-span/per-node, so parallelism doesn't compound peak memory (still obey 73f cap).

## Tooling (all in `~/comfy/`)
| File | Purpose |
|---|---|
| `h3-talkinghead.py` | ⭐ face-locked on-camera talking-head (ref2va), parallel across 2 nodes |
| `h3-spans.py` | keyframe-span pipeline: FLF2V(KF[i]→KF[i+1]) seamless cuts, master-parallel KFs, `--upscale` |
| `h3-multishot.py` | task-pool scheduler, cut/weld shots |
| `h3-weld.py` | hybrid motion-context weld + shared helpers (imported by the others) |
| `h3-parallel.py` | data-parallel independent clips |
| `measure_span_mem.py` | measures per-span RAM/GPU headroom (39/56/73f) |

Templates: `jc-noupscale-api.json` (fl2va, no ESRGAN), `jc-baseline-workflow-api.json`
(fl2va + ESRGAN inline), `h3-r2v-heretic-enhanced.json` (ref2va + ESRGAN inline — talking-head base).
Plans: `student_talkinghead_plan.json` (current), `student_story_56f_plan.json`, `hp_pigeon_plan.json`.
Locked face reference: `~/comfy/ref2va_test/face_ref.png`.

## Optimizations baked into BOTH .2/.3 ComfyUI stacks (persist on disk)
- `ComfyUI_sol-attn_Blackwell`: sm_121 patches, kijai SolAttnPatch (int8 + TMA, cos 0.99995),
  ported H3FirstBlockCache, batched VAE decode. (md5-identical across .2/.3.)
- `ComfyUI-Spectrum-MiniMax-H3` **upgraded to v0.2.1 on .2/.3/.4** → `offline_smoothing_replay=true`
  default = validated H3 audio-quality fix (kills degraded speech/stutter). Old versions backed up
  to `~/spectrum-backups/` (NOT inside custom_nodes — putting backups there makes ComfyUI load a
  duplicate node that shadows the new schema).
- ComfyUI 0.31.1 already includes the H3 audio-sampling commit (ModelSamplingAV).
- Models on disk: `minimax_h3_fl2va_pruned_int8_convrot` (I2V/FLF2V),
  `minimax_h3_ref2va_pruned_int8_convrot` (reference/face-lock), heretic Qwen3-VL TE, video+audio VAEs,
  RealESRGAN_x2plus.

## PENDING work — re-render talking-head WITH the audio fix
The last delivered talking-head (`~/Videos/talkinghead/0808_203455_talkinghead.mp4`) was rendered
BEFORE the Spectrum v0.2.1 audio upgrade, and had two issues since fixed in the plan/prompt
(burned-in subtitles → added NO-subtitle negatives; wardrobe drift → pinned outfit).
**Re-run after reboot** to get audio fix + subtitle fix + wardrobe lock in one video.

### Resume steps (after the reboot)
1. User restarts DSV4F stack: compose in `~/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731/`, 888k/0.76,
   DSV4F-first. Verify `curl .2:8888/health` = UP.
2. Launch ComfyUI on .2 AND .3 (co-tenancy order = DSV4F first, then H3):
   `ssh keyspark@10.100.10.2 'setsid bash ~/h3-cotenancy/h3-comfy-launch.sh </dev/null >~/h3-cotenancy/logs/comfyui.log 2>&1 &'`
   (same for .3). Startup takes 1–2 min; poll `:8188/system_stats`. Over-SSH detachment was flaky —
   if it dies, relaunch (a tmux/screen session is more reliable).
3. Verify audio fix: `curl .2:8188/object_info/SpectrumApplyMiniMaxH3` → `offline_smoothing_replay`
   default should be `true`.
4. Start RAM guard, then:
   `cd ~/comfy && python3 h3-talkinghead.py --plan student_talkinghead_plan.json --outdir ~/Videos/talkinghead`
5. Telegram delivery: `source ~/.hermes/.env` (TELEGRAM_BOT_TOKEN, TELEGRAM_HOME_CHANNEL, bot
   Keys_spark_bot), `curl -F chat_id=$TELEGRAM_HOME_CHANNEL -F video=@<final.mp4>
   https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendVideo` (≤50 MB).

## Known open issues / next optimizations
- H3 sometimes **burns the spoken line as on-screen subtitles** when the prompt quotes it. Mitigation
  added (strong NO-subtitle/caption negatives + rephrased delivery) — verify it worked on the re-run.
- **Wardrobe** isn't locked by ref2va (face only) — now pinned via prompt; verify.
- Keyframe planning in `h3-spans.py` is serial-ish; `master-parallel` mode (KF0 master then KF1..n
  parallel rooted in KF0) is the default and beat the serial chain on consistency AND speed.
- On-screen **text is always gibberish** (H3 limitation) — don't rely on legible UI/logos/text.

## Delivered videos (on `spark-13b3`)
- `~/Videos/student_story_v2/0808_191833_final.mp4` — 30 s narrated, 1152×1536 (sent to Telegram).
- `~/Videos/talkinghead/0808_203455_talkinghead.mp4` — 36.5 s face-locked talking-head, 1152×1536
  (sent to Telegram; pre-audio-fix — re-render pending).
- Earlier tests: `~/Videos/h3_spans/`, `~/Videos/h3_multishot/`, `~/Videos/hp_pigeon_parallel/`,
  `~/comfy/ref2va_test/talk_span.mp4` (the face-lock validation).

## Memory (Claude auto-memory, `~/.claude/projects/-home-keyspark/memory/`)
Key files: `project_h3_facelocked_talkinghead.md`, `feedback_h3_seamless_join_serial.md`,
`feedback_h3_dsv4f_cotenancy_oom.md`, `project_h3_video_campaign_resume.md`,
`minimax_h3_comfyui_gb10.md`, `node_claims_active.md`.
