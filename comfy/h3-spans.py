#!/usr/bin/env python3
"""H3 pre-planned KEYFRAME-SPAN renderer: seamless hard cuts + true dual-spark parallelism.

The whole video is planned first as a chain of boundary KEYFRAMES. Each SPAN is rendered
FLF2V (first_frame = KF[i], last_frame = KF[i+1]) so it ends EXACTLY on the next keyframe;
the following span STARTS on that same image file, so the hard cut is seamless with no weld.
Because every span's endpoints are pre-decided shared images, no span depends on another's
output -> all spans render in parallel across both sparks (~Nx). Bounding each span on both
ends also holds identity/scene and kills drift.

Quality-first plan (JSON): global style + lighting + tone + a continuous audio bed are baked
into every keyframe and span, and each span adds its own motion + audio, so tone/lighting/
motion/audio are all captured per the plan. Keyframes are generated as a coherent chain
(cheap, serial) at render quality; spans (expensive) run parallel.

Plan schema (see --emit-example):
  {
    "identity_image": "face.png"  |  "identity_prompt": "...",
    "style":     "35mm live-action, photoreal, 24fps ...",   # applied everywhere
    "lighting":  "warm golden-hour, soft shadows ...",        # applied everywhere
    "tone":      "wistful, cinematic, muted palette ...",     # applied everywhere
    "audio_bed": "continuous quiet courtyard ambience ...",   # under every span
    "width": 576, "height": 768, "kf_frames": 9, "span_len": 124, "seed": 1000,
    "keyframes": [ {"prompt": "KF0 composition"}, {"prompt": "KF1 ..."}, ... ],   # N
    "spans":     [ {"motion": "camera+subject KF0->KF1", "audio": "..."}, ... ]   # N-1
  }

Usage:
  ./h3-spans.py --plan story.json [--nodes ...] [--te keep] [--outdir ...]
  ./h3-spans.py --emit-example > story.json
"""
import argparse, json, subprocess, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
import importlib.util

_spec = importlib.util.spec_from_file_location("h3weld", str(Path.home() / "comfy" / "h3-weld.py"))
W = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(W)

EXAMPLE = {
    "identity_prompt": "A young wizard boy about eleven, round wire-rim glasses, tousled dark hair, "
        "grey knitted jumper under a black open robe.",
    "style": "Photorealistic live-action cinema, 35mm film grain, natural anamorphic lens, 24fps, "
        "180 degree shutter. No cartoon, no text, no subtitles, no watermark.",
    "lighting": "warm golden-hour sunlight in an ancient stone castle courtyard, soft long shadows",
    "tone": "wistful and wondrous, cinematic, gently muted warm palette",
    "audio_bed": "continuous soft courtyard ambience, gentle breeze, distant birdsong, no music",
    "width": 576, "height": 768, "kf_frames": 9, "span_len": 124, "seed": 4242,
    "keyframes": [
        {"prompt": "the boy stands facing camera in the courtyard, arm relaxed at his side, calm"},
        {"prompt": "the boy holds his forearm out, a grey pigeon just settling onto it, both steady"},
        {"prompt": "the boy raises a wooden wand, the pigeon lifting off his arm mid-wingbeat"},
        {"prompt": "the boy laughs, a soft glowing light circling above as the pigeon wheels overhead"}
    ],
    "spans": [
        {"motion": "slow push-in; the boy lifts his forearm as a pigeon flutters down to land",
         "audio": "soft wing flutter easing to gentle cooing"},
        {"motion": "static hold then he begins to raise a wand; the pigeon tenses and lifts off",
         "audio": "gentle cooing, then sudden wing beats"},
        {"motion": "gentle tilt up following the bird; a warm magical glow trails it as he laughs",
         "audio": "wing beats, soft magical shimmer, a delighted laugh"}
    ]
}


def kf_prompt(plan, kf):
    return (f"{plan['style']}\n{kf['prompt']}.\nLighting: {plan['lighting']}.\n"
            f"Tone: {plan['tone']}.\nSoundscape: {plan['audio_bed']}.")


def span_prompt(plan, span):
    say = span.get("say", "").strip()
    speech = (f' The student speaks to camera with natural lip-sync, clear natural voice, saying: '
              f'"{say}".') if say else ""
    return (f"{plan['style']}\nONE continuous shot. {span['motion']}.{speech}\n"
            f"Lighting: {plan['lighting']}.\nTone: {plan['tone']}.\n"
            f"Soundscape: {plan['audio_bed']}, {span.get('audio','')}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan")
    ap.add_argument("--emit-example", action="store_true")
    ap.add_argument("--workflow", default=str(Path.home() / "comfy" / "jc-noupscale-api.json"),
                    help="keyframe/plan template (native res, no upscale)")
    ap.add_argument("--upscale", action="store_true",
                    help="inline ESRGAN x2 per span (uses jc-baseline-workflow-api.json); safe on SHORT spans, "
                         "parallel so it adds no serial pass. Watch memory on co-resident DSV4F.")
    ap.add_argument("--span-workflow", default=str(Path.home() / "comfy" / "jc-baseline-workflow-api.json"),
                    help="span template when --upscale (has ESRGAN x2 inline)")
    ap.add_argument("--te", choices=list(W.TE_FILES), default="keep")
    ap.add_argument("--kf-mode", choices=["master-parallel", "chain", "rooted"], default="master-parallel",
                    dest="kf_mode",
                    help="master-parallel: KF0 master (serial) then KF1..n rooted in KF0, rendered in "
                         "PARALLEL across nodes (all anchored to one look). chain: serial KF[i]<-KF[i-1]. "
                         "rooted: serial KF[i]<-KF0.")
    ap.add_argument("--nodes", default="10.100.10.2:8188,10.100.10.3:8188")
    ap.add_argument("--outdir", default=str(Path.home() / "Videos" / "h3_spans"))
    ap.add_argument("--blend-frames", type=int, default=3, help="audio crossfade frames at each cut")
    ap.add_argument("--plan-only", action="store_true", help="generate keyframes then stop (for A/B on consistency)")
    ap.add_argument("--reuse-kf-glob", help="reuse existing keyframe PNGs (glob) instead of generating; "
                    "must match keyframe count in order. Lets a narrated v2 reuse v1's exact keyframes.")
    a = ap.parse_args()
    if a.emit_example:
        print(json.dumps(EXAMPLE, indent=2)); return
    if not a.plan:
        sys.exit("need --plan FILE (or --emit-example)")

    plan = json.loads(Path(a.plan).expanduser().read_text())
    kfs, spans = plan["keyframes"], plan["spans"]
    if len(spans) != len(kfs) - 1:
        sys.exit(f"need len(spans)==len(keyframes)-1; got {len(spans)} spans, {len(kfs)} keyframes")
    template = json.loads(Path(a.workflow).expanduser().read_text())
    span_template = json.loads(Path(a.span_workflow).expanduser().read_text()) if a.upscale else template
    nodes = [n.strip() for n in a.nodes.split(",")][:2]
    hosts = {n: n.split(":")[0] for n in nodes}
    args = SimpleNamespace(te=a.te, width=plan.get("width", 576), height=plan.get("height", 768))
    OUT = Path(a.outdir).expanduser(); OUT.mkdir(parents=True, exist_ok=True)
    runid = time.strftime("%m%d_%H%M%S")
    seed = plan.get("seed", 1000)
    kf_frames, span_len = plan.get("kf_frames", 9), plan.get("span_len", 124)
    fps = 24.0
    print(f"run {runid}: {len(kfs)} keyframes -> {len(spans)} spans @{args.width}x{args.height}, "
          f"nodes {'+'.join(nodes)}", flush=True)
    t_start = time.time()

    # ---- Phase 1: plan the keyframe chain (serial, cheap, render-quality stills) ----
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

    # Keyframes are the video's skeleton; any variation between them propagates as jitter.
    #   chain          : serial on one node, KF[i]<-KF[i-1] (coherent sequential series).
    #   rooted         : serial on one node, KF[i]<-KF0 (less accumulated drift, one machine).
    #   master-parallel: KF0 master (serial) then KF1..n <-KF0 rendered IN PARALLEL across nodes,
    #                     all anchored to the one master look; fast, cross-machine anchored by KF0.
    def gen_keyframe(node, i, first):
        pid = W.submit(node, W.base_clip(template, args, kf_prompt(plan, kfs[i]), kf_frames,
                                         seed + i, f"{runid}_kf{i}", first=first))
        clip = OUT / f"{runid}_kf{i}.mp4"
        W.wait_and_fetch(node, pid, clip, timeout=2400, tag=f"kf{i}")
        png = OUT / f"{runid}_kf{i}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.12", "-i", str(clip),
                        "-frames:v", "1", str(png)], check=True)
        name = f"spans_{runid}_kf{i}.png"
        for n in nodes:            # upload to every node so any node can render spans against it
            W.upload_image(n, png, name)
        return name

    kf_names = [None] * len(kfs)
    if a.reuse_kf_glob:
        import glob
        pngs = sorted(glob.glob(str(Path(a.reuse_kf_glob).expanduser())))
        if len(pngs) != len(kfs):
            sys.exit(f"--reuse-kf-glob matched {len(pngs)} PNGs but plan has {len(kfs)} keyframes")
        print(f"[plan] reusing {len(pngs)} keyframes (skip generation): {[Path(p).name for p in pngs]}", flush=True)
        for i, p in enumerate(pngs):
            name = f"spans_{runid}_kf{i}.png"
            for n in nodes:
                W.upload_image(n, Path(p), name)
            kf_names[i] = name
        # jump straight to spans
        if a.plan_only:
            print("[plan-only] reused keyframes; nothing generated."); return
        goto_spans = True
    else:
        goto_spans = False
        kf_names[0] = gen_keyframe(node0, 0, identity_name)   # KF0 = master, always serial
        print(f"[plan] kf0 planned (master); generating {len(kfs)-1} more (mode={a.kf_mode})...", flush=True)
    if not goto_spans and a.kf_mode == "master-parallel" and len(kfs) > 1:
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
    elif not goto_spans:  # serial chain or rooted on node0
        for i in range(1, len(kfs)):
            first = kf_names[0] if a.kf_mode == "rooted" else kf_names[i - 1]
            kf_names[i] = gen_keyframe(node0, i, first)
            print(f"  kf{i} planned", flush=True)

    if a.plan_only:
        print(f"\n[plan-only] {len(kfs)} keyframes done in {(time.time()-t_start)/60:.1f} min "
              f"(mode={a.kf_mode}) -> {OUT}")
        for i in range(len(kfs)):
            print(f"  {OUT / f'{runid}_kf{i}.png'}")
        print(f"RUNID={runid}")
        return

    # ---- Phase 2: render spans FLF2V(KF[i]->KF[i+1]) in parallel across nodes ----
    print(f"[render] {len(spans)} spans in parallel...", flush=True)
    results = {}
    errs = []
    lock = threading.Lock()
    idx = {"n": 0}

    def worker(node):
        while True:
            with lock:
                if errs or idx["n"] >= len(spans):
                    return
                i = idx["n"]; idx["n"] += 1
            try:
                wf = W.base_clip(span_template, args, span_prompt(plan, spans[i]),
                                 spans[i].get("len", span_len), seed + 100 + i, f"{runid}_span{i}",
                                 first=kf_names[i], last=kf_names[i + 1])
                dest = OUT / f"{runid}_span{i}.mp4"
                W.wait_and_fetch(node, W.submit(node, wf), dest, tag=f"span{i}")
                with lock:
                    results[i] = dest
            except Exception as e:
                with lock:
                    errs.append(f"span{i}: {e}")
                return

    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(n,)) for n in nodes]
    [t.start() for t in threads]
    [t.join() for t in threads]
    if errs:
        sys.exit("SPANS FAILED:\n  " + "\n  ".join(errs))
    print(f"[render] {len(spans)} spans done in {(time.time()-t0)/60:.1f} min "
          f"(serial would be ~{len(spans)*(time.time()-t0)/max(len(nodes),1)/60:.0f}+ min)", flush=True)

    # ---- Phase 3: stitch. Each span ends on KF[i+1]; next starts on it -> drop dup, xfade audio ----
    d = a.blend_frames / fps
    out = OUT / f"{runid}_final.mp4"
    cur = results[0]
    for i in range(1, len(spans)):
        nxt = results[i]
        merged = OUT / f"{runid}_upto{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cur), "-i", str(nxt),
            "-filter_complex",
            f"[1:v]select=gte(n\\,1),setpts=PTS-STARTPTS[v1];[0:v][v1]concat=n=2:v=1:a=0[v];"
            f"[0:a][1:a]acrossfade=d={d:.4f}[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac",
            str(merged)], check=True)
        cur = merged
    Path(cur).replace(out)
    dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    print(f"\nDONE: {out}  ({float(dur):.1f}s, {out.stat().st_size/1e6:.1f} MB)")
    print(f"total wall: {(time.time()-t_start)/60:.1f} min  ({len(kfs)} kf plan + {len(spans)} parallel spans)")
    print(f"keyframes: {', '.join(str(OUT / f'{runid}_kf{i}.png') for i in range(len(kfs)))}")


if __name__ == "__main__":
    main()
