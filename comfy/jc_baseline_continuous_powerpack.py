#!/usr/bin/env python3
"""Single-Spark continuous JC baseline (no multishot).

One generation, dense steps + full upgrades — compare wall time to dual-Spark
multishot. Default: ~30s (719f @ 24fps, 17k+5 grid) × 20 steps.

Usage:
  H3_HOST=127.0.0.1:8188 H3_I0_REF=~/Videos/jc_promo_30s/I0_ref.jpg \\
    python3 jc_baseline_continuous.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enhanced_graph import build_enhanced
from multishot_flf import upload_image, http_json, wait_done, find_video, download

# 5 + 17*42 = 719 ≈ 29.96s @ 24fps (H3 length grid)
LENGTH = int(os.environ.get("H3_LEN", "719"))
STEPS = int(os.environ.get("H3_STEPS", "20"))
W = int(os.environ.get("H3_W", "576"))
H = int(os.environ.get("H3_H", "768"))
HOST = os.environ.get("H3_HOST", "127.0.0.1:8188")
OUT = Path(os.environ.get("OUT_DIR", str(Path.home() / "Videos" / "jc_baseline_continuous_single")))
WORK = Path(os.environ.get("WORK_DIR", "/tmp/jc_baseline_continuous"))

PROMPT = f"""integrated_multimodal_description: Photorealistic live-action cinema, 35mm film grain,
natural anamorphic lens, 24fps, 180° shutter. Closed department store aisle at night, soft
fluorescent light, red-and-white logo bokeh. No cartoon, no text, no subtitles, no watermark.

Identity: young Jennifer Connelly — luminous GREEN eyes, dark chestnut wavy hair, fair skin with
real pores, white ribbed tank top. Portrait {W}x{H}. Slow languid motion.

ONE continuous shot (~30s). She holds camera with green eyes, turns for a look-back smile, then
faces camera and speaks clearly with natural lip-sync (soft American voice, natural not synthetic):
"I want you to get keys DGX Sparkticus Utimate Power Pack Unleashed — dual DGX Sparks needed —
running both DeepSeek Version Four Flash and MiniMax H3 abliterated with all the speed upgrades,
multi-shot, seamless transition, turbo dual sampling — because that is what I want.
And… is this what you want in return?"
Then she blows a kiss to camera and holds a warm smile.

overall_soundscape: continuous quiet store hum, her clear natural speech, soft kiss, breath.
No music score. non_diegetic_music: N/A"""


def main():
    ref = os.environ.get("H3_I0_REF", "").strip()
    if not ref:
        cand = Path.home() / "Videos" / "jc_promo_30s" / "I0_ref.jpg"
        if cand.is_file():
            ref = str(cand)
    if not ref:
        print("ERROR: H3_I0_REF required", file=sys.stderr)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    http_json(f"http://{HOST}/system_stats", timeout=10)
    print(
        f"BASELINE continuous single-Spark  host={HOST}  {W}x{H}  len={LENGTH} "
        f"(~{LENGTH/24:.1f}s) steps={STEPS} dense  upgrades=Sage→Sol→Spectrum→FBC  x2",
        flush=True,
    )

    # upload face as first_frame identity
    import subprocess
    face = WORK / "face_ref.png"
    subprocess.check_call(
        ["ffmpeg", "-y", "-i", ref, "-frames:v", "1", "-q:v", "2", str(face)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    first = upload_image(HOST, face, "jc_baseline_face.png")

    # KJ "auto" = sageattention 1.0.6. Never default sageattn3 (CUDA offload bug).
    sage = os.environ.get("H3_SAGE", "auto")
    g = build_enhanced(
        PROMPT,
        seed=int(os.environ.get("SEED", "42042")),
        width=W,
        height=H,
        length=LENGTH,
        steps=STEPS,
        prefix="video/jc_baseline_continuous",
        first_frame=first,
        last_frame=None,
        sage=sage,
        spectrum=True,
        turbo=False,
        dual_turbo=False,
        motion_context=False,
        upscale="RealESRGAN_x2plus.pth",
        fbc_start_step=3,
    )
    # force dense res_multistep already when not turbo
    t0 = time.time()
    body = json.dumps({"prompt": g, "client_id": "jc_baseline_cont"}).encode()
    req = urllib.request.Request(
        f"http://{HOST}/prompt", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        pid = json.loads(r.read().decode())["prompt_id"]
    print(f"queued {pid}  steps={STEPS} length={LENGTH}", flush=True)

    # wait
    while True:
        hist = http_json(f"http://{HOST}/history/{pid}", timeout=30)
        if pid in hist:
            entry = hist[pid]
            st = entry.get("status", {})
            if st.get("completed") or entry.get("outputs"):
                break
            if st.get("status_str") == "error":
                raise RuntimeError(entry)
        print(f"  … {time.time()-t0:.0f}s", flush=True)
        time.sleep(20)

    # download video
    entry = http_json(f"http://{HOST}/history/{pid}", timeout=30)[pid]
    outs = entry.get("outputs", {})
    vid_info = None
    for node_out in outs.values():
        for v in node_out.get("videos") or node_out.get("gifs") or []:
            vid_info = v
            break
        if vid_info:
            break
    if not vid_info:
        # try images/files
        for node_out in outs.values():
            for v in node_out.get("images") or []:
                if str(v.get("filename", "")).endswith((".mp4", ".webm")):
                    vid_info = v
                    break
    if not vid_info:
        raise RuntimeError(f"no video in outputs: {list(outs.keys())}")

    fn = vid_info["filename"]
    sub = vid_info.get("subfolder", "")
    typ = vid_info.get("type", "output")
    dest = OUT / "jc_baseline_continuous_30s_20step.mp4"
    url = f"http://{HOST}/view?filename={fn}&subfolder={sub}&type={typ}"
    urllib.request.urlretrieve(url, dest)
    wall = time.time() - t0
    (OUT / "TIMING.txt").write_text(
        f"mode=SINGLE_CONTINUOUS_BASELINE\n"
        f"host={HOST}\n"
        f"length_frames={LENGTH}\n"
        f"duration_s_approx={LENGTH/24:.2f}\n"
        f"steps={STEPS}\n"
        f"turbo=0 dual_turbo=0\n"
        f"upgrades=Sage+SolAttn+Spectrum+FBC+ESRGAN_x2+heretic_TE\n"
        f"total_wall_s={wall:.1f}\n"
        f"note=continuous JC promo naming keys-DGX-Sparkticus Utimate Power Pack Unleashed\n"
    )
    print(f"DONE wall={wall:.0f}s → {dest}", flush=True)
    print(f"TIMING {OUT / 'TIMING.txt'}", flush=True)


if __name__ == "__main__":
    main()
