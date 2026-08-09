#!/usr/bin/env python3
"""Face-locked on-camera talking-head story: ref2va spans, parallel across 2 nodes.

Each SPAN = one MiniMaxH3ReferenceToVideo generation from a single locked face portrait
(identity holds across all scenes) + a spoken line (native lip-sync) + scene/motion, at 73f
with inline ESRGAN upscale. No keyframe-planning phase. Spans grouped into SCENES (>=10s each);
scene changes are deliberate cuts, within-scene are vlog-style soft cuts. Renders all spans in
parallel across both nodes (each independent), then stitches in order with short audio crossfades.

Plan JSON: {identity_portrait_png?, style, nat_skin, width, height, span_len, seed,
            scenes:[{setting, spans:[{line, motion}]}]}
"""
import argparse, importlib.util, json, subprocess, threading, time
from pathlib import Path
from types import SimpleNamespace

_spec = importlib.util.spec_from_file_location("h3weld", str(Path.home()/"comfy"/"h3-weld.py"))
W = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(W)

R2V_TPL = json.loads((Path.home()/"comfy"/"h3-r2v-heretic-enhanced.json").read_text())
R = "136"  # MiniMaxH3ReferenceToVideo


def build_span(face_name, prompt, length, seed, prefix, width, height):
    wf = json.loads(json.dumps(R2V_TPL))
    for n in ("137", "139"):
        wf.pop(n, None)
    for k in list(wf[R]["inputs"]):
        if k.startswith("ref_images"):
            wf[R]["inputs"].pop(k)
    wf["ref_face"] = {"class_type": "LoadImage", "inputs": {"image": face_name}}
    wf[R]["inputs"]["ref_images.ref_image_0"] = ["ref_face", 0]
    wf[R]["inputs"].update(prompt=prompt, width=width, height=height, length=length)
    wf["51"]["inputs"]["degree"] = 1        # ref2va requires Spectrum degree==1
    wf["51"]["inputs"]["warmup_steps"] = 1  # ...and warmup_steps<=1
    wf["15"]["inputs"]["noise_seed"] = seed
    wf["92"]["inputs"]["filename_prefix"] = f"video/{prefix}"
    return wf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--nodes", default="10.100.10.2:8188,10.100.10.3:8188")
    ap.add_argument("--outdir", default=str(Path.home()/"Videos"/"talkinghead"))
    args = ap.parse_args()
    plan = json.loads(Path(args.plan).expanduser().read_text())
    nodes = [n.strip() for n in args.nodes.split(",")][:2]
    OUT = Path(args.outdir).expanduser(); OUT.mkdir(parents=True, exist_ok=True)
    runid = time.strftime("%m%d_%H%M%S")
    W_, H_ = plan.get("width", 576), plan.get("height", 768)
    L = plan.get("span_len", 73); seed0 = plan.get("seed", 9000)
    nat = plan.get("nat_skin", "NATURAL SKIN TEXTURE with visible pores, real human skin, no waxy/plastic/CGI look.")
    style = plan.get("style", "Photorealistic live-action cinema, 35mm film grain, 24fps.")
    wardrobe = plan.get("wardrobe", "")   # fix: pin outfit so it doesn't drift between shots
    NOTEXT = ("NO subtitles, NO captions, NO on-screen text, NO words or letters on screen, "
              "NO title cards, NO watermark.")   # fix: stop H3 burning the spoken line as captions
    t_start = time.time()

    # locked face portrait: use provided PNG, else generate one (serial), upload to both nodes
    face_name = f"th_{runid}_face.png"
    if plan.get("identity_portrait_png"):
        for n in nodes:
            W.upload_image(n, Path(plan["identity_portrait_png"]).expanduser(), face_name)
        print("using provided portrait")
    else:
        args_ns = SimpleNamespace(te="keep", width=W_, height=H_)
        pp = (f"{style} {nat}\n{plan['identity_prompt']} Facing camera, calm neutral expression, "
              f"evenly lit studio portrait.")
        port_tpl = json.loads((Path.home()/"comfy"/"jc-noupscale-api.json").read_text())
        W.wait_and_fetch(nodes[0], W.submit(nodes[0], W.base_clip(port_tpl, args_ns, pp, 9, seed0, f"{runid}_port")),
                         OUT/f"{runid}_port.mp4", timeout=1800, tag="portrait")
        subprocess.run(["ffmpeg","-y","-loglevel","error","-sseof","-0.12","-i",str(OUT/f"{runid}_port.mp4"),
                        "-frames:v","1",str(OUT/f"{runid}_face.png")],check=True)
        for n in nodes:
            W.upload_image(n, OUT/f"{runid}_face.png", face_name)
        print("portrait generated -> face locked")

    # flatten spans (carry scene index for stitch), render all in parallel across nodes
    tasks = []
    for si, sc in enumerate(plan["scenes"]):
        for j, sp in enumerate(sc["spans"]):
            prompt = (f"{style} {nat} {NOTEXT} "
                      f"Use <Picture 1> as the person: keep this exact same face and identity, {wardrobe}. "
                      f"{sc['setting']} {sp.get('motion','slow subtle motion')}, looking directly at the "
                      f"camera, talking casually to the viewer with natural lip-sync. "
                      f"Audio: quiet natural room tone and his natural, warm, human speaking voice "
                      f"(not synthetic, not robotic). He says out loud, conversationally: {sp['line']}")
            tasks.append({"si": si, "prompt": prompt, "prefix": f"{runid}_s{si}_{j}",
                          "seed": seed0 + 1 + len(tasks), "dest": OUT/f"{runid}_s{si}_{j}.mp4"})
    print(f"run {runid}: {len(tasks)} talking spans ({L}f) across {len(nodes)} nodes", flush=True)

    results = {}; errs = []; idx = {"n": 0}; lock = threading.Lock()

    def worker(node):
        while True:
            with lock:
                if errs or idx["n"] >= len(tasks):
                    return
                i = idx["n"]; idx["n"] += 1
            t = tasks[i]
            try:
                wf = build_span(face_name, t["prompt"], L, t["seed"], t["prefix"], W_, H_)
                W.wait_and_fetch(node, W.submit(node, wf), t["dest"], tag=t["prefix"])
                with lock:
                    results[i] = t["dest"]
            except Exception as e:
                with lock:
                    errs.append(f"{t['prefix']}: {e}")
                return

    t0 = time.time()
    th = [threading.Thread(target=worker, args=(n,)) for n in nodes]
    [t.start() for t in th]; [t.join() for t in th]
    if errs:
        raise SystemExit("SPANS FAILED:\n  " + "\n  ".join(errs))
    print(f"[render] {len(tasks)} spans in {(time.time()-t0)/60:.1f} min", flush=True)

    # stitch in order; short audio crossfade at every join (all cuts, talking-head)
    d = 3/24.0
    out = OUT/f"{runid}_talkinghead.mp4"
    cur = results[0]
    for i in range(1, len(tasks)):
        nxt = results[i]; merged = OUT/f"{runid}_upto{i}.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(cur),"-i",str(nxt),"-filter_complex",
            f"[0:v][1:v]concat=n=2:v=1:a=0[v];[0:a][1:a]acrossfade=d={d:.4f}[a]",
            "-map","[v]","-map","[a]","-c:v","libx264","-crf","16","-c:a","aac",str(merged)],check=True)
        cur = merged
    Path(cur).replace(out)
    dur = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","csv=p=0",str(out)],
                         capture_output=True,text=True).stdout.strip()
    print(f"\nDONE: {out}  ({float(dur):.1f}s)  total wall {(time.time()-t_start)/60:.1f} min")


if __name__ == "__main__":
    main()
