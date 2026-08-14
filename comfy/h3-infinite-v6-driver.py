#!/usr/bin/env python3
"""Hesitation v6 — Infinite-Continuation production driver (triple-node).

Phases:
  kf                    render all 27 keyframes on the head (co-tenant-free)
  kf --only a1_hall...  re-roll specific keyframes
  chain --act act1      run one act's clip chain on its assigned node (serial)
  stitch --act act1     suite Stitch Saved Chain -> act video (on act's node)
  assemble              split-view comp + act concat + song mux -> final draft

Chains store latents under h3_continuous/v6_<act> on their node; every phase is
resumable (chain --from N).
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace

os.environ["H3_CFG"] = "1"

import importlib.util
_here = Path.home() / "comfy"
_s = importlib.util.spec_from_file_location("h3weld", str(_here / "h3-weld.py"))
W = importlib.util.module_from_spec(_s); _s.loader.exec_module(W)
_s2 = importlib.util.spec_from_file_location("spansv2", str(_here / "h3-spans-v2.py"))
V2 = importlib.util.module_from_spec(_s2); _s2.loader.exec_module(V2)

PLAN = json.loads((_here / "hesitation_v6_plan.json").read_text())
OUT = Path.home() / "Videos" / "hesitation_v6"
OUT.mkdir(parents=True, exist_ok=True)
EX = _here / "h3-infinite-examples"
HEAD = "localhost:8188"
ALL_NODES = [HEAD, "10.100.10.1:8188", "10.100.10.5:8188"]
MAN, WOMAN, STYLE = PLAN["man"], PLAN["woman"], PLAN["style"]
BOTH = f"The same two people as always: {MAN}; {WOMAN}. "


def kf_prefix(kf_id):
    if kf_id.startswith("h_"):
        return f"{MAN}. "
    if kf_id.startswith("w_"):
        return f"{WOMAN}. "
    return BOTH


def load_api(name):
    return json.loads((EX / name).read_text())


def common_fix(g):
    for node in g.values():
        ct = node["class_type"]
        if ct == "UNETLoader":
            node["inputs"]["unet_name"] = PLAN["unet"]
        elif ct == "CLIPLoader":
            node["inputs"]["clip_name"] = PLAN["te_file"]
        elif ct == "KSamplerSelect":
            node["inputs"]["sampler_name"] = "res_multistep"
        elif ct == "BasicScheduler":
            node["inputs"] = {k: v for k, v in node["inputs"].items() if isinstance(v, list)}
            node["inputs"].update({"scheduler": "simple", "steps": 20, "denoise": 1.0})
        elif ct == "PathchSageAttentionKJ":
            node["inputs"]["sage_attention"] = "disabled"
        elif ct == "SaveVideo":
            node["inputs"].setdefault("format", "mp4")
            node["inputs"].setdefault("codec", "h264")
    return g


def phase_kf(only=None):
    template = json.loads(V2._find("jc-noupscale-api.json").read_text())
    template[W.cid(template, "UNETLoader")]["inputs"]["unet_name"] = PLAN["unet"]
    # strip SolAttnPatch: its runtime hook conflicts with the continuation suite
    if "sol" in template:
        sol_src = template["sol"]["inputs"]["model"]
        for nd in template.values():
            for k, v in list(nd["inputs"].items()):
                if isinstance(v, list) and v[0] == "sol":
                    nd["inputs"][k] = sol_src
        del template["sol"]
    args = SimpleNamespace(te="keep", width=PLAN["width"], height=PLAN["height"])
    pseudo = {"kf_style": STYLE, "style": STYLE,
              "lighting": "natural motivated lighting true to each location",
              "tone": "young love, cold disapproval, aching distance, reunion and freedom",
              "audio_bed": "gentle romantic score"}
    ids = only or list(PLAN["keyframes"])
    for i, kf_id in enumerate(ids):
        prompt = V2.kf_prompt(pseudo, {"prompt": kf_prefix(kf_id) + PLAN["keyframes"][kf_id]})
        wf = W.base_clip(json.loads(json.dumps(template)), args, prompt, PLAN["kf_frames"],
                         PLAN["seed"] + hash(kf_id) % 9999, f"v6_{kf_id}", first=None)
        pid = W.submit(HEAD, wf)
        clip = OUT / f"kf_{kf_id}.mp4"
        W.wait_and_fetch(HEAD, pid, clip, timeout=2400, tag=f"kf:{kf_id}")
        png = OUT / f"kf_{kf_id}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.12", "-i", str(clip),
                        "-frames:v", "1", str(png)], check=True)
        for n in ALL_NODES:
            W.upload_image(n, png, f"v6_{kf_id}.png")
        print(f"[{i+1}/{len(ids)}] kf {kf_id} done", flush=True)


def act_cast(act):
    if act == "act2_him":
        return ("ONLY ONE PERSON IN THIS ENTIRE SCENE: " + MAN + ". The young woman does NOT "
                "appear anywhere; no second person exists in any frame. ")
    if act == "act2_her":
        return ("ONLY ONE PERSON IN THIS ENTIRE SCENE: " + WOMAN + ". The young man does NOT "
                "appear anywhere in person; no second person exists in any frame (he may appear "
                "only inside small printed photographs). ")
    return BOTH


def phase_chain(act, start_from=0):
    a = PLAN["acts"][act]
    node = a["node"]
    clips = a["clips"]
    # per-act latent DIRECTORY so parallel/sequential chains can never collide
    lat_prefix = f"h3_continuous_v6_{act}/clip"
    for i, clip in enumerate(clips):
        if i < start_from:
            continue
        t0 = time.time()
        if i == 0:
            g = common_fix(load_api("api_01_start.json"))
            g["5"]["inputs"]["image"] = f"v6_{clip['kf_first']}.png"
            g["6"]["inputs"]["image"] = f"v6_{clip['kf_last']}.png"
            g["7"]["inputs"]["image"] = f"v6_{clip['kf_first']}.png"
            g["8"]["inputs"].update({"prompt": act_cast(act) + STYLE + " " + clip["motion"],
                                     "width": PLAN["width"], "height": PLAN["height"],
                                     "duration": PLAN["clip_duration"]})
        else:
            g = common_fix(load_api("api_02_continue.json"))
            for nd in g.values():
                if nd["class_type"] == "H3ContinuousLoadLatent":
                    nd["inputs"].update({"latent_path": f"h3_continuous_v6_{act}", "clip_index": i})
                elif nd["class_type"] == "LoadImage":
                    nd["inputs"]["image"] = f"v6_{clip['kf_last']}.png"
                elif nd["class_type"] == "H3ContinuousContinueV11":
                    nd["inputs"].update({"prompt": act_cast(act) + STYLE + " " + clip["motion"],
                                         "width": PLAN["width"], "height": PLAN["height"],
                                         "duration": PLAN["clip_duration"]})
        for nd in g.values():
            if nd["class_type"] == "RandomNoise":
                nd["inputs"]["noise_seed"] = PLAN["seed"] + 1000 * (list(PLAN["acts"]).index(act) + 1) + i
            elif nd["class_type"] == "SaveVideo":
                nd["inputs"]["filename_prefix"] = f"video/v6_{act}_clip{i}"
            elif nd["class_type"] == "H3ContinuousSaveLatent":
                nd["inputs"]["filename_prefix"] = lat_prefix
                nd["inputs"]["clip_index"] = i + 1
        dest = OUT / f"{act}_clip{i}.mp4"
        for attempt in (1, 2):
            try:
                pid = W.submit(node, g)
                W.wait_and_fetch(node, pid, dest, timeout=3600, tag=f"{act}:clip{i}")
                break
            except Exception as e:
                print(f"  {act} clip{i} attempt {attempt} failed: {e}", flush=True)
                if attempt == 2:
                    raise
                time.sleep(30)
        print(f"[{act}] clip {i+1}/{len(clips)} done in {time.time()-t0:.0f}s", flush=True)
    print(f"CHAIN {act} COMPLETE", flush=True)


def phase_stitch(act):
    a = PLAN["acts"][act]
    g = load_api("api_04_stitch.json")
    for nd in g.values():
        if nd["class_type"] == "H3ContinuousStitchSavedChainV11":
            nd["inputs"].update({"latent_prefix": f"h3_continuous_v6_{act}/clip",
                                 "first_clip": 1, "last_clip": len(a["clips"]),
                                 "filename_prefix": f"video/v6_{act}_stitched"})
    pid = W.submit(a["node"], g)
    W.wait_and_fetch(a["node"], pid, OUT / f"{act}_stitched.mp4", timeout=3600, tag=f"stitch:{act}")
    print(f"STITCH {act} COMPLETE", flush=True)


def phase_assemble():
    # split view: him | her, center-crop each to 432x480
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(OUT / "act2_him_stitched.mp4"),
                    "-i", str(OUT / "act2_her_stitched.mp4"),
                    "-filter_complex",
                    "[0:v]crop=432:480:216:0[l];[1:v]crop=432:480:216:0[r];"
                    "[l][r]hstack=inputs=2[v]",
                    "-map", "[v]", "-r", "24", str(OUT / "act2_split.mp4")], check=True)
    # concat acts (video only), then mux the song
    concat = OUT / "acts_concat.txt"
    concat.write_text("".join(f"file '{OUT / f}'\n"
                              for f in ("act1_stitched.mp4", "act2_split.mp4", "act3_stitched.mp4")))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(concat), "-an", "-c:v", "libx264", "-crf", "18",
                    str(OUT / "v6_video_only.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(OUT / "v6_video_only.mp4"), "-i", PLAN["song"],
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest",
                    str(OUT / "v6_final_song.mp4")], check=True)
    print("ASSEMBLE COMPLETE:", OUT / "v6_final_song.mp4", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["kf", "chain", "stitch", "assemble"])
    ap.add_argument("--act")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--from", dest="start_from", type=int, default=0)
    ap.add_argument("--kf-node")
    a = ap.parse_args()
    if a.phase == "kf":
        if a.kf_node:
            HEAD = a.kf_node
            globals()["HEAD"] = a.kf_node
        phase_kf(a.only)
    elif a.phase == "chain":
        phase_chain(a.act, a.start_from)
    elif a.phase == "stitch":
        phase_stitch(a.act)
    else:
        phase_assemble()
