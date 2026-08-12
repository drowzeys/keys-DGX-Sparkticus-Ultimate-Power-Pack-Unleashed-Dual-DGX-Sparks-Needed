#!/usr/bin/env python3
"""H3 spans v2: MUSIC-VIDEO renderer — real-song audio reference + keyframe spans + auto 2K.

v1 (h3-spans.py) renders FLF2V spans whose audio is improvised per span, so the
music bed shifts texture at every cut. v2 fixes that for music videos:

  1. The plan carries a real SONG file. Each span gets its exact time-slice of
     the song as a standalone audio reference (MiniMaxH3ReferenceToVideo
     ref_audio_1, prompted as <Audio 1>), so generated audio/visuals follow the
     real track's rhythm and energy in place.
  2. Spans are still keyframe-bounded: MiniMaxH3CustomKeyframes pins KF[i] at
     frame 1 and KF[i+1] at the last frame (seamless hard cuts, parallel-safe).
  3. The final stitch muxes the ORIGINAL song over the whole timeline
     (*_final_song.mp4) — perfect audio continuity by construction. The
     generated-audio stitch is kept alongside (*_final_gen.mp4).
  4. ESRGAN x2 async upscale is ON by default (--no-upscale to disable):
     render native 1280x704, deliver ~2560x1408.

Plan schema additions over v1:
  "song": "/path/to/track.wav"      # required; span count must satisfy
                                    # len(spans) == ceil(duration / (span_len/24))
  "unet": "minimax_h3_ref2va_realism070_int8_convrot_localmerge.safetensors"
  "kf_unet": "minimax_h3_fl2va_realism_int8_convrot_localmerge.safetensors"

Usage:
  ./h3-spans-v2.py --plan song_plan.json [--nodes ...] [--outdir ...] [--no-upscale]
"""
import argparse, json, math, subprocess, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
import importlib.util

_HERE = Path(__file__).resolve().parent
_SEARCH = [_HERE, _HERE / "scripts", Path.home() / "comfy"]
for _p in _SEARCH:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _find(name: str) -> Path:
    for base in _SEARCH:
        cand = base / name
        if cand.is_file():
            return cand
    raise FileNotFoundError(f"{name} not found in {[str(s) for s in _SEARCH]}")


_spec = importlib.util.spec_from_file_location("h3weld", str(_find("h3-weld.py")))
W = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(W)


def probe_duration(path):
    return float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip())


def kf_prompt(plan, kf):
    import h3_prompt_guide as PG
    # kf_style: keyframes are scene-establishing stills — texture-macro bait
    # ("film grain", "visible pores") in the style can collapse them into
    # abstract close-ups, so plans may supply a de-baited wide-framing style
    # for keyframes while spans keep the full texture language.
    return PG.kf_t2va_or_i2va(
        style=plan.get("kf_style", plan["style"]), lighting=plan["lighting"], tone=plan["tone"],
        kf_prompt=kf["prompt"],
        audio_bed=plan.get("audio_bed", "Music video ambience."),
        has_first_frame=False)


def span_prompt(plan, span, length_frames):
    """ref2va span prompt: motion + the song slice as <Audio 1>."""
    secs = length_frames / 24.0
    parts = [
        plan["style"],
        f"Lighting: {plan['lighting']}",
        f"Tone: {plan['tone']}",
        f"A continuous {secs:.1f} second single shot. Camera and subject: {span['motion']}",
        "Audio: the soundtrack is exactly the music of <Audio 1>, continuing seamlessly "
        "at the same tempo, key and mix; all on-screen motion, dancing and cuts land on "
        "its beat. No other music, no speech."
        + (f" {span['audio']}" if span.get("audio") else ""),
        span.get("identity_note", ""),
    ]
    return "\n".join(p for p in parts if p)


def ref_span_clip(template, args, prompt, length, seed, prefix,
                  first_name, last_name, audio_name, unet_name):
    """ref2va span graph: song-slice audio ref + first/last custom keyframes."""
    wf = json.loads(json.dumps(template))
    cid = W.cid
    i2v, noise, save, clip, unet = (cid(wf, "MiniMaxH3ImageToVideo"), cid(wf, "RandomNoise"),
                                    cid(wf, "SaveVideo"), cid(wf, "CLIPLoader"), cid(wf, "UNETLoader"))
    vvae = avae = None
    for k, v in wf.items():
        if v.get("class_type") == "VAELoader":
            if "audio" in v["inputs"]["vae_name"]:
                avae = k
            else:
                vvae = k
    guider = cid(wf, "BasicGuider")
    sampler = cid(wf, "SamplerCustomAdvanced")

    wf[noise]["inputs"]["noise_seed"] = seed
    wf[save]["inputs"]["filename_prefix"] = f"video/{prefix}"
    wf[unet]["inputs"]["unet_name"] = unet_name
    if W.TE_FILES[args.te]:
        wf[clip]["inputs"]["clip_name"] = W.TE_FILES[args.te]

    # drop the I2V node and any frames wired into it; replace with ref2va + custom keyframes
    for key in ("first_frame", "last_frame"):
        ref = wf[i2v]["inputs"].get(key)
        if isinstance(ref, list):
            wf.pop(ref[0], None)
    wf.pop(i2v, None)

    wf["v2_aud"] = {"class_type": "LoadAudio", "inputs": {"audio": audio_name}}
    wf["v2_r2v"] = {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
        "clip": [clip, 0], "vae": [vvae, 0], "audio_vae": [avae, 0],
        "prompt": prompt, "width": args.width, "height": args.height, "length": length,
        "ref_image_size": "match", "ref_audios.ref_audio_0": ["v2_aud", 0]}}
    wf["v2_kf_first"] = {"class_type": "LoadImage", "inputs": {"image": first_name}}
    wf["v2_kf_last"] = {"class_type": "LoadImage", "inputs": {"image": last_name}}
    wf["v2_ckf"] = {"class_type": "MiniMaxH3CustomKeyframes", "inputs": {
        "conditioning": ["v2_r2v", 0], "vae": [vvae, 0], "latent": ["v2_r2v", 1],
        "keyframe_state": json.dumps({"count": 2, "positions": [1, length]}),
        "indexing": "1-based", "crop": "disabled",
        "keyframe_image_1": ["v2_kf_first", 0], "keyframe_image_2": ["v2_kf_last", 0]}}
    wf[guider]["inputs"]["conditioning"] = ["v2_ckf", 0]
    wf[sampler]["inputs"]["latent_image"] = ["v2_r2v", 1]
    # anything else that consumed the I2V node's outputs must now read r2v
    for k, v in wf.items():
        for ik, iv in list(v.get("inputs", {}).items()):
            if isinstance(iv, list) and iv and iv[0] == i2v:
                v["inputs"][ik] = ["v2_r2v", iv[1]]
    return wf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--workflow", default=str(_find("jc-noupscale-api.json")))
    ap.add_argument("--no-upscale", action="store_true", help="skip the default async ESRGAN x2")
    ap.add_argument("--upscale-model", default="RealESRGAN_x2plus.pth")
    ap.add_argument("--te", choices=list(W.TE_FILES), default="keep")
    ap.add_argument("--kf-mode", choices=["master-parallel", "chain", "rooted", "independent"],
                    default="independent",
                    help="independent (default): every keyframe is a pure text-to-video still from its own "
                         "prompt — REQUIRED for multi-location story plans, where anchoring on a master "
                         "frame makes scene-jumping keyframes wander into macro/wrong-scene shots. Keep "
                         "cast consistency by embedding the full character description in every keyframe "
                         "prompt. master-parallel/chain/rooted anchor keyframes as in v1 (fine for "
                         "single-world plans).")
    ap.add_argument("--nodes", default="10.100.10.1:8188,10.100.10.5:8188")
    ap.add_argument("--outdir", default=str(Path.home() / "Videos" / "h3_spans_v2"))
    ap.add_argument("--blend-frames", type=int, default=3)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--reuse-kf-glob")
    a = ap.parse_args()

    plan = json.loads(Path(a.plan).expanduser().read_text())
    song = Path(plan["song"]).expanduser()
    if not song.is_file():
        sys.exit(f"song not found: {song}")
    dur = probe_duration(song)
    fps = 24.0
    span_len = plan.get("span_len", 124)
    span_sec = span_len / fps
    need = math.ceil(dur / span_sec)
    kfs, spans = plan["keyframes"], plan["spans"]
    if len(spans) != need:
        sys.exit(f"song is {dur:.1f}s -> need exactly {need} spans of {span_sec:.2f}s; plan has {len(spans)}")
    if len(spans) != len(kfs) - 1:
        sys.exit(f"need len(spans)==len(keyframes)-1; got {len(spans)} spans, {len(kfs)} keyframes")

    template = json.loads(Path(a.workflow).expanduser().read_text())
    nodes = [n.strip() for n in a.nodes.split(",")][:2]
    args = SimpleNamespace(te=a.te, width=plan.get("width", 1280), height=plan.get("height", 704))
    OUT = Path(a.outdir).expanduser(); OUT.mkdir(parents=True, exist_ok=True)
    runid = time.strftime("%m%d_%H%M%S")
    seed = plan.get("seed", 1000)
    kf_frames = plan.get("kf_frames", 9)
    span_unet = plan.get("unet", "minimax_h3_ref2va_realism070_int8_convrot_localmerge.safetensors")
    kf_unet = plan.get("kf_unet")
    upscale = not a.no_upscale
    print(f"run {runid}: song {song.name} {dur:.1f}s -> {len(spans)} spans @{args.width}x{args.height}"
          f"{' + async x2' if upscale else ''}, nodes {'+'.join(nodes)}", flush=True)
    t_start = time.time()

    # keyframe stills come from the plan template graph (I2V path);
    # optionally pin its UNET so keyframes match the span checkpoint's look
    if kf_unet:
        template = json.loads(json.dumps(template))
        template[W.cid(template, "UNETLoader")]["inputs"]["unet_name"] = kf_unet

    # ---- Phase 0: slice the song per span and upload to every node ----
    audio_names = []
    for i in range(len(spans)):
        t0 = i * span_sec
        slice_path = OUT / f"{runid}_a{i}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.4f}",
                        "-t", f"{span_sec:.4f}", "-i", str(song),
                        "-ac", "2", "-ar", "32000", str(slice_path)], check=True)
        name = f"spans_{runid}_a{i}.wav"
        for n in nodes:
            W.upload_image(n, slice_path, name)
        audio_names.append(name)
    print(f"[audio] {len(audio_names)} song slices uploaded", flush=True)

    # ---- Phase 1: keyframes (same skeleton logic as v1) ----
    node0 = nodes[0]
    identity_name = None
    if plan.get("identity_image"):
        identity_name = f"spans_{runid}_id.png"
        for n in nodes:
            W.upload_image(n, Path(plan["identity_image"]).expanduser(), identity_name)
    elif plan.get("identity_prompt"):
        print("[plan] identity ref...", flush=True)
        png = W.micro(node0, template, args, f"{plan['style']}\n{plan['identity_prompt']}\n"
                      f"Facing camera, {plan['lighting']}.", seed, f"{runid}_id", tag="identity")
        identity_name = f"spans_{runid}_id.png"
        for n in nodes:
            W.upload_image(n, png, identity_name)

    def gen_keyframe(node, i, first):
        pid = W.submit(node, W.base_clip(template, args, kf_prompt(plan, kfs[i]), kf_frames,
                                         seed + i, f"{runid}_kf{i}", first=first))
        clip = OUT / f"{runid}_kf{i}.mp4"
        W.wait_and_fetch(node, pid, clip, timeout=2400, tag=f"kf{i}")
        png = OUT / f"{runid}_kf{i}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.12", "-i", str(clip),
                        "-frames:v", "1", str(png)], check=True)
        name = f"spans_{runid}_kf{i}.png"
        for n in nodes:
            W.upload_image(n, png, name)
        return name

    kf_names = [None] * len(kfs)
    if a.reuse_kf_glob:
        import glob, re

        def kf_index(p):
            m = re.search(r"kf(\d+)\.png$", p)
            return int(m.group(1)) if m else 10**9

        # numeric sort: lexicographic ordering scrambles kf10 before kf2 for
        # unpadded names, silently mismapping every keyframe past index 9
        pngs = sorted(glob.glob(str(Path(a.reuse_kf_glob).expanduser())), key=kf_index)
        if len(pngs) != len(kfs):
            sys.exit(f"--reuse-kf-glob matched {len(pngs)} but plan has {len(kfs)} keyframes")
        for i, p in enumerate(pngs):
            name = f"spans_{runid}_kf{i}.png"
            for n in nodes:
                W.upload_image(n, Path(p), name)
            kf_names[i] = name
        print(f"[plan] reusing {len(pngs)} keyframes", flush=True)
    elif a.kf_mode == "independent":
        print(f"[plan] generating {len(kfs)} independent keyframes in parallel...", flush=True)
        kerrs, kidx, klock = [], {"n": 0}, threading.Lock()

        def kf_worker_ind(node):
            while True:
                with klock:
                    if kerrs or kidx["n"] >= len(kfs):
                        return
                    i = kidx["n"]; kidx["n"] += 1
                try:
                    nm = gen_keyframe(node, i, None)
                    with klock:
                        kf_names[i] = nm
                    print(f"  kf{i} planned", flush=True)
                except Exception as e:
                    with klock:
                        kerrs.append(f"kf{i}: {e}")
                    return

        kts = [threading.Thread(target=kf_worker_ind, args=(n,)) for n in nodes]
        [t.start() for t in kts]; [t.join() for t in kts]
        if kerrs:
            sys.exit("KEYFRAME PLAN FAILED:\n  " + "\n  ".join(kerrs))
    else:
        kf_names[0] = gen_keyframe(node0, 0, identity_name)
        print(f"[plan] kf0 planned (master); generating {len(kfs)-1} more (mode={a.kf_mode})...", flush=True)
        if a.kf_mode == "master-parallel" and len(kfs) > 1:
            kerrs, kidx, klock = [], {"n": 1}, threading.Lock()

            def kf_worker(node):
                while True:
                    with klock:
                        if kerrs or kidx["n"] >= len(kfs):
                            return
                        i = kidx["n"]; kidx["n"] += 1
                    try:
                        nm = gen_keyframe(node, i, kf_names[0])
                        with klock:
                            kf_names[i] = nm
                        print(f"  kf{i} planned", flush=True)
                    except Exception as e:
                        with klock:
                            kerrs.append(f"kf{i}: {e}")
                        return

            kts = [threading.Thread(target=kf_worker, args=(n,)) for n in nodes]
            [t.start() for t in kts]; [t.join() for t in kts]
            if kerrs:
                sys.exit("KEYFRAME PLAN FAILED:\n  " + "\n  ".join(kerrs))
        else:
            for i in range(1, len(kfs)):
                first = kf_names[0] if a.kf_mode == "rooted" else kf_names[i - 1]
                kf_names[i] = gen_keyframe(node0, i, first)
                print(f"  kf{i} planned", flush=True)

    if a.plan_only:
        print(f"[plan-only] {len(kfs)} keyframes done in {(time.time()-t_start)/60:.1f} min -> {OUT}")
        print(f"RUNID={runid}")
        return

    # ---- Phase 2: ref2va spans in parallel (+ optional async x2) ----
    print(f"[render] {len(spans)} ref2va spans in parallel"
          + (" + async x2 upscale" if upscale else "") + "...", flush=True)
    results, errs, lock = {}, [], threading.Lock()
    idx = {"n": 0}
    ux_results, ux_claimed = {}, set()

    def upscale_wf(video_name, prefix):
        return {
            "1": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
            "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
            "3": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": a.upscale_model}},
            "4": {"class_type": "ImageUpscaleWithModel",
                  "inputs": {"upscale_model": ["3", 0], "image": ["2", 0]}},
            "5": {"class_type": "CreateVideo",
                  "inputs": {"images": ["4", 0], "fps": ["2", 2], "audio": ["2", 1]}},
            "6": {"class_type": "SaveVideo",
                  "inputs": {"video": ["5", 0], "filename_prefix": prefix,
                             "format": "mp4", "codec": "h264"}},
        }

    def upscale_worker(node):
        while True:
            with lock:
                if errs:
                    return
                todo = [i for i in results if i not in ux_claimed]
                if todo:
                    i = min(todo); ux_claimed.add(i)
                elif len(ux_claimed) >= len(spans):
                    return
                else:
                    i = None
            if i is None:
                time.sleep(3); continue
            try:
                name = f"{runid}_span{i}_src.mp4"
                W.upload_image(node, results[i], name)
                dest = OUT / f"{runid}_span{i}_x2.mp4"
                W.wait_and_fetch(node, W.submit(node, upscale_wf(name, f"video/{runid}_span{i}_x2")),
                                 dest, tag=f"x2 span{i}")
                with lock:
                    ux_results[i] = dest
            except Exception as e:
                with lock:
                    errs.append(f"x2 span{i}: {e}")
                return

    def worker(node):
        while True:
            with lock:
                if errs:
                    return
                if idx["n"] >= len(spans):
                    break
                i = idx["n"]; idx["n"] += 1
            try:
                L = spans[i].get("len", span_len)
                wf = ref_span_clip(template, args, span_prompt(plan, spans[i], L), L,
                                   seed + 100 + i, f"{runid}_span{i}",
                                   kf_names[i], kf_names[i + 1], audio_names[i], span_unet)
                dest = OUT / f"{runid}_span{i}.mp4"
                W.wait_and_fetch(node, W.submit(node, wf), dest, timeout=7200, tag=f"span{i}")
                with lock:
                    results[i] = dest
            except Exception as e:
                with lock:
                    errs.append(f"span{i}: {e}")
                return
        if upscale:
            upscale_worker(node)

    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(n,)) for n in nodes]
    [t.start() for t in threads]; [t.join() for t in threads]
    if errs:
        sys.exit("SPANS FAILED:\n  " + "\n  ".join(errs))
    print(f"[render] {len(spans)} spans done in {(time.time()-t0)/60:.1f} min", flush=True)
    if upscale:
        if len(ux_results) != len(spans):
            sys.exit(f"UPSCALE-ASYNC incomplete: {len(ux_results)}/{len(spans)}")
        print(f"[x2] all {len(spans)} spans upscaled", flush=True)
        results = ux_results

    # ---- Phase 3: stitch, then mux the original song over the timeline ----
    d = a.blend_frames / fps
    gen_out = OUT / f"{runid}_final_gen.mp4"
    cur = results[0]
    for i in range(1, len(spans)):
        merged = OUT / f"{runid}_upto{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cur), "-i", str(results[i]),
            "-filter_complex",
            f"[1:v]select=gte(n\\,1),setpts=PTS-STARTPTS[v1];[0:v][v1]concat=n=2:v=1:a=0[v];"
            f"[0:a][1:a]acrossfade=d={d:.4f}[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac",
            str(merged)], check=True)
        cur = merged
    Path(cur).replace(gen_out)

    # Song cut: NO dedup-frame drop — each span must start exactly at
    # i*(span_len/fps) so visuals stay frame-locked to the real track for the
    # whole song (dropping the duplicate boundary frame would slide the video
    # ~1 frame earlier per cut, ~1.4s of beat-drift by the end). The doubled
    # keyframe instant at each hard cut is an imperceptible 2-frame hold.
    song_out = OUT / f"{runid}_final_song.mp4"
    concat_list = OUT / f"{runid}_concat.txt"
    concat_list.write_text("".join(f"file '{results[i]}'\n" for i in range(len(spans))))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list), "-i", str(song),
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "16",
                    "-c:a", "aac", "-b:a", "256k",
                    "-af", "afade=t=out:st={:.2f}:d=1.5".format(max(dur - 1.5, 0)),
                    "-shortest", str(song_out)], check=True)

    for out in (song_out, gen_out):
        dur_s = probe_duration(out)
        print(f"DONE: {out}  ({dur_s:.1f}s, {out.stat().st_size/1e6:.1f} MB)")
    print(f"total wall: {(time.time()-t_start)/60:.1f} min")
    print(f"RUNID={runid}")


if __name__ == "__main__":
    main()
