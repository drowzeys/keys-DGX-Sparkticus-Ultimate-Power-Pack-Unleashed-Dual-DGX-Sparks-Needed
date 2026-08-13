#!/usr/bin/env python3
"""Slow-cinema music-video driver: scene-grouped keyframes, in-scene spans, hard cuts.

Phases (run separately so the keyframe QC gate stays human):
  --phase kf        scene masters independent, in-scene keyframes anchored to their master
  --phase spans     27 in-scene FLF spans (song-slice audio refs, retry+liveness), native res
  --phase assemble  frame-exact concat of all spans + original master mux
"""
import argparse, importlib.util, json, subprocess, sys, threading, time
from pathlib import Path
from types import SimpleNamespace

_spec = importlib.util.spec_from_file_location("v2", str(Path(__file__).parent / "h3-spans-v2.py"))
v2 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(v2)
W = v2.W

ap = argparse.ArgumentParser()
ap.add_argument("--plan", default="/home/keyspark/comfy/hesitation_slow_plan.json")
ap.add_argument("--phase", required=True, choices=["kf", "spans", "assemble"])
ap.add_argument("--runid", help="required for spans/assemble (the kf phase prints one)")
ap.add_argument("--nodes", default="10.100.10.1:8188,10.100.10.5:8188")
ap.add_argument("--outdir", default=str(Path.home() / "Videos" / "hesitation_slow"))
a = ap.parse_args()

plan = json.loads(Path(a.plan).read_text())
NODES = [n.strip() for n in a.nodes.split(",")]
OUT = Path(a.outdir); OUT.mkdir(parents=True, exist_ok=True)
args = SimpleNamespace(te="keep", width=plan["width"], height=plan["height"])
template = json.loads((Path.home() / "comfy" / "jc-noupscale-api.json").read_text())
fps = 24.0
span_len = plan["span_len"]
span_sec = span_len / fps
seed = plan["seed"]
lock = threading.Lock()


def node_alive(node):
    try:
        W.api(node, "/system_stats", timeout=8)
        return True
    except Exception:
        return False


DS4 = "http://10.100.10.1:8888/v1/chat/completions"
DS4_MODEL = "deepseek-v4-flash-0731-ablit-l10-35-anchorstock"
ENH_SYS = ("You are a cinematographer writing generation prompts for the MiniMax-H3 video model. "
           "Rewrite the user's shot description into ONE richer paragraph (70-110 words) obeying ALL rules: "
           "photorealistic live-action romantic drama; ONE single continuous scene, one location, one camera; "
           "slow unhurried camera and natural human movement; sharp in-focus natural faces, real skin; "
           "no split screen, no collage, no text or signage anywhere; keep every stated character detail "
           "(hair, eyes, wardrobe) EXACTLY as given and do not invent clothing; keep the stated camera move; "
           "add concrete sensory detail that strengthens the same moment. Output ONLY the rewritten prompt.")

def enhance(text):
    """DSV4F prompt enrichment; falls back to the original text on any failure."""
    import urllib.request
    try:
        body = json.dumps({"model": DS4_MODEL,
                           "messages": [{"role": "system", "content": ENH_SYS},
                                        {"role": "user", "content": text}],
                           "max_tokens": 320, "temperature": 0.4}).encode()
        req = urllib.request.Request(DS4, data=body, headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=180).read())
        out = r["choices"][0]["message"]["content"].strip()
        return out if len(out) > 40 else text
    except Exception as e:
        print(f"  [enhance] fallback ({e})", flush=True)
        return text


def apply_te(t):
    te = plan.get("te_file")
    if te:
        t[W.cid(t, "CLIPLoader")]["inputs"]["clip_name"] = te
    return t


def kf_template():
    t = json.loads(json.dumps(template))
    t[W.cid(t, "UNETLoader")]["inputs"]["unet_name"] = plan["kf_unet"]
    return apply_te(t)


def gen_kf(node, runid, i, first_name):
    base = plan["keyframes"][i]["prompt"]
    if plan.get("enhance"):
        cast = plan.get("cast_block", "")
        base = enhance((cast + " SHOT: " + base) if cast else base)
    kfp = {"prompt": base}
    prompt = v2.kf_prompt(plan, kfp)
    wf = W.base_clip(kf_template(), args, prompt, plan["kf_frames"], seed + i,
                     f"{runid}_kf{i}", first=first_name)
    pid = W.submit(node, wf)
    dest = OUT / f"{runid}_kf{i}.mp4"
    W.wait_and_fetch(node, pid, dest, timeout=2400, tag=f"kf{i}")
    png = OUT / f"{runid}_kf{i}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.12", "-i", str(dest),
                    "-frames:v", "1", str(png)], check=True)
    name = f"slow_{runid}_kf{i}.png"
    for n in NODES:
        W.upload_image(n, png, name)
    return name


if a.phase == "kf":
    runid = time.strftime("%m%d_%H%M%S")
    print(f"KF phase, runid {runid}: {len(plan['keyframes'])} kfs in {len(plan['kf_scene_groups'])} scenes", flush=True)
    groups = list(plan["kf_scene_groups"])
    gidx = {"n": 0}
    errs = []

    def worker(node):
        while True:
            with lock:
                if errs or gidx["n"] >= len(groups):
                    return
                g = groups[gidx["n"]]; gidx["n"] += 1
            try:
                master = gen_kf(node, runid, g[0], None)
                print(f"  scene@kf{g[0]} master ok", flush=True)
                for i in g[1:]:
                    gen_kf(node, runid, i, master)
                    print(f"  kf{i} ok (anchored)", flush=True)
            except Exception as e:
                with lock:
                    errs.append(f"scene@{g[0]}: {e}")
                return

    ts = [threading.Thread(target=worker, args=(n,)) for n in NODES]
    [t.start() for t in ts]; [t.join() for t in ts]
    if errs:
        sys.exit("KF PHASE FAILED:\n  " + "\n  ".join(errs))
    print(f"KF phase complete. RUNID={runid}")
    sys.exit(0)

runid = a.runid or sys.exit("--runid required for this phase")
song = Path(plan["song"])
dur = v2.probe_duration(song)
N = len(plan["spans"])

if a.phase == "spans":
    # slice + upload audio
    for j in range(N):
        sp = OUT / f"{runid}_a{j}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{j*span_sec:.4f}",
                        "-t", f"{span_sec:.4f}", "-i", str(song), "-ac", "2", "-ar", "32000",
                        str(sp)], check=True)
        for n in NODES:
            W.upload_image(n, sp, f"slow_{runid}_a{j}.wav")
    print(f"[audio] {N} slices uploaded", flush=True)

    sidx = {"n": 0}
    failed = []

    def sworker(node):
        while True:
            with lock:
                if sidx["n"] >= N:
                    return
                j = sidx["n"]; sidx["n"] += 1
            kf_a, kf_b = plan["span_map"][j]
            for attempt in (1, 2):
                try:
                    if not node_alive(node):
                        raise RuntimeError(f"{node} down")
                    sp = dict(plan["spans"][j])
                    if plan.get("enhance"):
                        sp["motion"] = enhance(sp["motion"])
                    prompt = v2.span_prompt(plan, sp, span_len)
                    wf = v2.ref_span_clip(apply_te(json.loads(json.dumps(template))), args, prompt, span_len, seed + 500 + j,
                                          f"{runid}_span{j}", f"slow_{runid}_kf{kf_a}.png",
                                          f"slow_{runid}_kf{kf_b}.png", f"slow_{runid}_a{j}.wav",
                                          plan["unet"])
                    dest = OUT / f"{runid}_span{j}.mp4"
                    W.wait_and_fetch(node, W.submit(node, wf), dest, timeout=2400, tag=f"span{j}")
                    print(f"  [span{j}] ok", flush=True)
                    break
                except Exception as e:
                    print(f"  [span{j}] attempt {attempt} failed: {e}", flush=True)
                    if attempt == 2:
                        with lock:
                            failed.append(j)
                    else:
                        time.sleep(30)

    ts = [threading.Thread(target=sworker, args=(n,)) for n in NODES]
    [t.start() for t in ts]; [t.join() for t in ts]
    if failed:
        sys.exit(f"SPANS FAILED: {failed}")
    print("spans complete")
    sys.exit(0)

if a.phase == "assemble":
    missing = [j for j in range(N) if not (OUT / f"{runid}_span{j}.mp4").exists()]
    if missing:
        sys.exit(f"missing spans: {missing}")
    song_out = OUT / f"{runid}_final_song.mp4"
    concat = OUT / f"{runid}_concat.txt"
    concat.write_text("".join(f"file '{OUT / f'{runid}_span{j}.mp4'}'\n" for j in range(N)))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(concat), "-i", str(song),
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "16",
                    "-c:a", "aac", "-b:a", "256k",
                    "-af", "afade=t=out:st={:.2f}:d=1.5".format(max(dur - 1.5, 0)),
                    "-shortest", str(song_out)], check=True)
    print(f"DONE: {song_out}  ({v2.probe_duration(song_out):.1f}s, {song_out.stat().st_size/1e6:.1f} MB)")
