#!/usr/bin/env python3
"""Parallel dual-H3 ~10s Harry Potter → dragon — FLF multishot (Hermes architecture).

**Seamless parallel (concurrency=2)** — the correct keyspark/Hermes design:

  Phase 0  SEQUENTIAL quality keyframes K0, K1, K2 on .2
           (optional H3_I0_REF face re-anchor every key)
  Phase 1  PARALLEL dual FLF arms:
             .2  arm1: first=K0 last=K1  (human → dragon transform)
             .3  arm2: first=K1 last=K2  (dragon → Hogwarts flight)
           → previous segment LAST image == next segment FIRST image (shared key PNG)
  Phase 2  HARD-CUT stitch (NO xfade) — continuous by construction

Natural skin / anti-plastic look is ON by default (see multishot_flf.NATURAL_SKIN).

This replaces the older scout/FLF hybrid. Engine: multishot_flf.run_multishot.

Usage:
  PYTHONPATH=deploy/keyspark python3 keyframe_dual_flf.py
  H3_I0_REF=/path/to/face_or_clip.mp4 python3 keyframe_dual_flf.py
  H3_UPSCALE=0 python3 keyframe_dual_flf.py

Env: see multishot_flf.py (H3_HEAD/WORKER, STEPS, H3_KEY_MODE, OUT_DIR, …)

Based on tonyd2wild/ds4-h3-video-gen-factory + Hermes FLF multishot workflow.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from multishot_flf import MultishotConfig, run_multishot  # noqa: E402


LOOK = """integrated_multimodal_description: Photorealistic live-action cinema, 8K IMAX detail,
natural anamorphic lens, 24fps, 180° shutter motion blur. Cinematography like Alfonso Cuarón x
Roger Deakins. Strictly practical and motivated light — grey English daylight through tall Gothic
stone windows, warm candle and floating-candle spill, cool stone bounce, soft volumetric dust.
No cartoon, no anime, no CGI plastic skin, no game-engine look, no text, no subtitles, no watermark.

Identity lock: same teenage wizard whenever human — messy black hair, round wire spectacles,
lightning-bolt scar on forehead, black Hogwarts-style school robe, red-and-gold Gryffindor scarf,
white shirt, grey sweater. Highly detailed anatomy: correct facial proportions, visible pores,
individual hair strands, fabric weave, realistic glass reflection in the spectacles. Same
emerald-and-obsidian Western dragon scale pattern, horn shape, and body proportions whenever the
dragon appears — scales read as organic keratin plates, not plastic CGI."""

KEY_PROMPTS = [
    """KEYFRAME / living portrait (minimal motion, high quality). Subject only: the teenage wizard
boy alone in a grand Hogwarts-like great hall / common room — tall arched windows, misty Scottish
Highlands, floating candles, fireplace glow. Medium shot, center frame, locked camera with slight
handheld breath.

He looks at his hands in quiet fear and wonder as golden sparks crawl under his skin; robe fabric
lifts in an unseen wind; candles flicker. Spectacles on; scar visible; face fully readable with
REAL natural skin texture (pores, soft subsurface light — not airbrushed). NO dragon in frame yet.
NO second character.

overall_soundscape: crackling fireplace, wind against stone, soft fabric. No music. No dialogue.
non_diegetic_music: N/A""",
    """KEYFRAME / still-energy shot (minimal motion): a fully transformed mid-sized Western dragon
fills the same Hogwarts-like great hall, wings half-unfurled scraping beams, head turned toward a
tall open Gothic window with misty Scottish hills. Emerald-and-obsidian scales catch window light
with organic micro-detail and subsurface green (not plastic sheen); chest heaving, smoke from
nostrils, muscles coiled to leap. Same chamber architecture (candles, stone, window).

overall_soundscape: fireplace, deep reptilian inhale, wind. No music. No dialogue.
non_diegetic_music: N/A""",
    """KEYFRAME / living aerial still (minimal motion): the same emerald-and-obsidian dragon banks
in a hover over a Hogwarts-like castle — turrets, Great Hall roof, lake, misty Highlands. Hero
aerial angle, wings fully extended with correct membrane stretch, tail counterbalancing. Exact
same dragon identity (scale pattern, horns, proportions) as the mid hall keyframe.

overall_soundscape: wind, distant water, wing tension. No music. No dialogue.
non_diegetic_music: N/A""",
]

ARM_PROMPTS = [
    """ONE continuous take, no cuts.
FIRST FRAME is the human wizard key (match face, glasses, scarf, robe, hall lighting, skin texture exactly).
LAST FRAME is the fully transformed dragon at the open window key (identity, pose, lighting locked).

Storyboard:
[0.0s–1.5s] Medium shot: boy center frame, golden sparks under skin, robe lifts, candles flicker —
real pore-level skin, no plastic.
[1.5s–3.5s] Transformation: spine lengthens, shoulders broaden, overlapping iridescent
emerald-and-obsidian scales with anatomical weight; fingers fuse into wing digits; spectacles fall;
face elongates into noble snout, horns emerge, vertical pupils — visceral metamorphosis.
[3.5s–5.17s] Fully formed mid-sized Western dragon fills the chamber, wings half-unfurled, head
toward open window, coiled to leap. Camera holds.

overall_soundscape: crackling fireplace, fabric tearing, wet organic morphing, deep reptilian inhale.
No music. No dialogue.
non_diegetic_music: N/A""",
    """ONE continuous take, no cuts.
FIRST FRAME is the dragon at the open window (exact match to mid key).
LAST FRAME is the dragon hovering over the castle (exact match to end key).

Storyboard:
[0.0s–1.5s] Dragon coils and launches through the open arched window; stone dust and tapestry in
slipstream; camera pushes after him.
[1.5s–3.5s] Exterior: full wings, banks into wide hover over Hogwarts-like castle — turrets, lake,
mist; correct wing aerodynamics and body weight.
[3.5s–5.17s] Hero aerial hold: slow hover circle around the main keep, heavy downstroke, scale
detail sharp in diffuse daylight.

Physical consistency: same dragon identity as first frame, rigid castle geometry, gravity respected.
overall_soundscape: wind roar, heavy wing beats, distant lake water, deep dragon breath.
No music. No dialogue.
non_diegetic_music: N/A""",
]


def main():
    out = Path(os.environ.get("OUT_DIR", str(Path.home() / "Videos" / "hp_dragon_parallel")))
    work = Path(os.environ.get("WORK_DIR", "/tmp/hp_dragon_parallel"))
    ref = os.environ.get("H3_I0_REF", "").strip() or None
    # Prefer original sequential face if present and no ref set
    if not ref:
        cand = Path.home() / "Videos" / "hp_dragon_dual" / "harry_potter_dragon_hogwarts_10s.mp4"
        if cand.is_file():
            ref = str(cand)
            print(f"  auto H3_I0_REF={ref}", flush=True)

    cfg = MultishotConfig(
        key_prompts=KEY_PROMPTS,
        arm_prompts=ARM_PROMPTS,
        look=LOOK,
        natural_skin=True,
        out_dir=out,
        work_dir=work,
        final_name="harry_potter_dragon_parallel_10s.mp4",
        i0_ref=ref,
        key_mode=os.environ.get("H3_KEY_MODE", "auto"),
        hardcut=True,
    )
    final = run_multishot(cfg)
    # also write hardcut alias for older consumers
    hard = out / "harry_potter_dragon_parallel_10s_hardcut.mp4"
    if final.is_file() and not hard.exists():
        import shutil
        shutil.copy2(final, hard)
    print(f"  continuous/hardcut: {final}", flush=True)


if __name__ == "__main__":
    main()
