# H3 Music Video v2 — real-song audio refs + parallel 2K, one shot

**What it makes:** a full-length 2K (~2560×1408) music video for a REAL audio track,
with the original song as the final soundtrack and visuals generated to its rhythm —
rendered in parallel across a dual-Spark pair. First production run: a full 2:58 song,
35 spans, ~6 h wall on two GB10s under DS4 co-tenancy.

## Why v2

v1 spans (`h3-spans.py`) improvise the audio per span, so music shifts texture at every
cut. v2 (`h3-spans-v2.py`) fixes this for music videos:

1. **Per-span audio reference** — each span receives its exact time-slice of the song as
   a standalone `ref_audio` (`MiniMaxH3ReferenceToVideo`, prompted as `<Audio 1>`), so
   generated audio/visuals follow the real track in place.
2. **Keyframe-bounded cuts** — `MiniMaxH3CustomKeyframes` pins KF[i] at frame 1 and
   KF[i+1] at the last frame; spans stay parallel-safe and cuts are seamless.
3. **Original-track mux** — the stitch step lays the REAL song over the whole timeline
   (`*_final_song.mp4`); the generated-audio stitch is kept for reference (`*_final_gen.mp4`).
4. **Auto 2K** — async ESRGAN x2 is ON by default; native 1280×704 → ~2560×1408. Spans
   render clean and whichever node runs out of span work drains the upscale queue, so
   only the last span's upscale sits on the critical path.

## One-shot

```bash
# 0. Prereqs: Power Pack bringup healthy (DS4 + dual H3), heretic TE, both nodes.

# 1. REQUIRED pack patch (once per node) — decouples the Motion-Context-MultiRef
#    self-test so keyframe anchors enable on current cores (audio row packing changed
#    upstream; the pack's timeline-audio feature stays safely disabled):
cd <ComfyUI>/custom_nodes/ComfyUI-H3-Motion-Context-MultiRef
git apply <power-pack>/deploy/patches/multi-ref-decouple-audio-selftest.patch
# restart ComfyUI on every node after applying

# 2. Build + deploy the 0.7 realism merges (fl2va for keyframes, ref2va for spans):
python3 comfy/scripts/build_realism070_int8.py          # fl2va 0.7
python3 comfy/scripts/build_ref2va_realism070_int8.py   # ref2va 0.7
# copy both ~20G files to models/diffusion_models/ on every render node

# 3. Author the plan from the example:
#    comfy/plans/music_video_v2_example_plan.json
#    Rule: len(spans) == ceil(song_seconds / (span_len/24)); keyframes = spans+1.
#    Map sections to the song: run a loudness profile (ffmpeg ebur128) and place
#    builds/drops/outros honestly. The final span may overhang; the mux trims it.

# 4. Render:
python3 comfy/h3-spans-v2.py --plan my_song_plan.json \
  --nodes 10.100.10.1:8188,10.100.10.5:8188 --outdir ~/Videos/my_mv
```

## Mistakes this build already made for you

| Gotcha | The fix (already in the shipped scripts) |
|---|---|
| Autogrow audio-ref input rejected | API key is the dotted, 0-based path `ref_audios.ref_audio_0` — not `ref_audio_1` |
| CustomKeyframes "keyframe 1 has no image" | dynamic image inputs are `keyframe_image_1..N` |
| MultiRef self-test blocks everything | apply `deploy/patches/multi-ref-decouple-audio-selftest.patch`, restart Comfy |
| Gibberish/babble audio | `h3-weld.py` `submit()` auto-converts BasicGuider → CFGGuider 5.0 + ConditioningZeroOut ([H3_AUDIO_FIX_CFG5.md](./H3_AUDIO_FIX_CFG5.md)); `H3_CFG=1` restores guidance-free |
| Speech/onset roughness on a take | per-seed realization — re-roll the seed ([H3_AUDIO_FIX_CFG5.md](./H3_AUDIO_FIX_CFG5.md)) |
| ref2va + EasyCache | leave EasyCache OFF for R2V (launch script default) |

## Budgeting

Per 124-frame span at 1280×704 with CFG 5 under DS4 co-tenancy: ~12-16 min. A 3-minute
song (~35 spans) on a dual pair: keyframes ~1.5 h + spans ~4 h (2K upscale overlapped)
≈ **6 h total**. Halve the pixel count (864×480) for a ~2.5x faster draft pass; the
plan is resolution-agnostic.

## Credit

Dual-serve foundation by **Tony (tonyd2wild)** — the v2 music-video layer builds on the
Power Pack quality stack (Sol/Spectrum/FBC + heretic TE + CFG-5 audio fix).
