#!/usr/bin/env python3
"""Hybrid motion-context WELD: parallel H3 segments joined by a seamless serial weld.

Timeline:
  identity ref (5f) -> anchor (5f, = B's start & weld's target)
  PARALLEL:  A (first=identity, free end) on node A   ||   B (first=anchor) on node B
  SERIAL:    weld (~1s) on node A: MiniMaxH3MotionContext continues A's REAL trailing
             frames + audio waveform, with last_frame=anchor so it lands exactly on B's
             start. Motion, direction/speed, and the *same* audio carry across A->weld.
  STITCH:    A ++ weld(trimmed)  [butt join, motion-context = seamless]
             ++ B[drop dup frame] [video hard cut on shared anchor; short audio crossfade,
                                   since B's audio was generated independently]

Keeps most of the 2x speedup (A,B parallel; only the short weld is serial) while giving
true motion/audio continuity at the A->weld join. The weld->B join is video-exact; its
audio gets a brief crossfade. Design the shot so the *action* (e.g. a wand raise, a
lighting change) happens INSIDE a segment, and the anchor/seam is a held, steady beat.

Usage:
  ./h3-weld.py --identity-prompt "..." --anchor-prompt "..." \
      --prompt-a "..." --weld-prompt "..." --prompt-b "..." \
      [--workflow ~/comfy/jc-noupscale-api.json] [--te keep] \
      [--la 175 --lb 175 --lw 39] [--width 576 --height 768] [--seed 1000] \
      [--nodes 10.100.10.2:8188,10.100.10.3:8188] [--out path.mp4]
"""
import argparse, json, mimetypes, subprocess, sys, threading, time, urllib.parse, urllib.request, uuid
from pathlib import Path

OUTDIR = Path.home() / "comfy" / "weld_out"
COMFY_ROOT = "~/h3-cotenancy/ComfyUI"   # on .2/.3
TE_FILES = {"keep": None,
            "stock": "qwen3vl_32b_minimax_h3_nvfp4_awq.STOCK.safetensors",
            "heretic": "H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors"}


def api(node, path, data=None, headers=None, timeout=30):
    req = urllib.request.Request(f"http://{node}{path}", data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def upload_image(node, img_path, name):
    b = uuid.uuid4().hex
    ctype = mimetypes.guess_type(str(img_path))[0] or "image/png"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode() + Path(img_path).read_bytes() + (
            f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue"
            f"\r\n--{b}--\r\n").encode()
    api(node, "/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={b}"})


def cid(wf, cls):
    hits = [k for k, v in wf.items() if v.get("class_type") == cls]
    if len(hits) != 1:
        sys.exit(f"template needs exactly one {cls}, found {len(hits)}")
    return hits[0]


def base_clip(template, args, prompt, length, seed, prefix, first=None, last=None):
    """Plain I2V clip: set prompt/dims/seed/prefix + optional first/last frame keyframes."""
    wf = json.loads(json.dumps(template))
    i2v, noise, save, clip = cid(wf, "MiniMaxH3ImageToVideo"), cid(wf, "RandomNoise"), \
        cid(wf, "SaveVideo"), cid(wf, "CLIPLoader")
    wf[noise]["inputs"]["noise_seed"] = seed
    wf[save]["inputs"]["filename_prefix"] = f"video/{prefix}"
    if TE_FILES[args.te]:
        wf[clip]["inputs"]["clip_name"] = TE_FILES[args.te]
    wf[i2v]["inputs"].update(prompt=prompt, width=args.width, height=args.height, length=length)
    for key in ("first_frame", "last_frame"):
        ref = wf[i2v]["inputs"].pop(key, None)
        if isinstance(ref, list):
            wf.pop(ref[0], None)
    for key, img in (("first_frame", first), ("last_frame", last)):
        if img:
            n = f"kf_{key}"
            wf[n] = {"class_type": "LoadImage", "inputs": {"image": img}}
            wf[i2v]["inputs"][key] = [n, 0]
    return wf


def weld_clip(template, args, prompt, length, seed, prefix, ctx_video_name, anchor_name):
    """Motion-context continuation: continue ctx_video's motion+audio, land on anchor."""
    wf = base_clip(template, args, prompt, length, seed, prefix, last=anchor_name)
    i2v, vvae, avae = cid(wf, "MiniMaxH3ImageToVideo"), None, None
    # two VAELoaders: video (fp16) vs audio (fp32) - pick by name
    for k, v in wf.items():
        if v.get("class_type") == "VAELoader":
            if "audio" in v["inputs"]["vae_name"]:
                avae = k
            else:
                vvae = k
    guider, vdec, adec, create = cid(wf, "BasicGuider"), cid(wf, "VAEDecode"), \
        cid(wf, "VAEDecodeAudio"), cid(wf, "CreateVideo")
    wf["mc_lv"] = {"class_type": "LoadVideo", "inputs": {"file": ctx_video_name}}
    wf["mc_gvc"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["mc_lv", 0]}}
    wf["mc_ctx"] = {"class_type": "MiniMaxH3MotionContext", "inputs": {
        "conditioning": [i2v, 0], "vae": [vvae, 0], "latent": [i2v, 1],
        "context_frames": ["mc_gvc", 0], "context_length": 22, "encode_mode": "video",
        "anchor_mode": "head", "crop": "disabled", "audio_context_length": 22,
        "audio_mode": "timeline", "audio_vae": [avae, 0], "context_audio": ["mc_gvc", 1]}}
    wf[guider]["inputs"]["conditioning"] = ["mc_ctx", 0]          # guider now from motion-context
    wf["mc_trim"] = {"class_type": "MiniMaxH3MotionContextTrim", "inputs": {
        "images": [vdec, 0], "audio": [adec, 0], "trim_frames": ["mc_ctx", 1],
        "fps": 24.0, "match_tail": True}}
    wf[create]["inputs"]["images"] = ["mc_trim", 0]
    wf[create]["inputs"]["audio"] = ["mc_trim", 1]
    return wf


def submit(node, wf):
    r = json.loads(api(node, "/prompt", json.dumps({"prompt": wf}).encode(),
                       {"Content-Type": "application/json"}))
    if r.get("error") or r.get("node_errors"):
        raise RuntimeError(f"{node} rejected workflow: {json.dumps(r)[:900]}")
    return r["prompt_id"]


def wait_and_fetch(node, pid, dest, timeout=7200, tag=""):
    """Poll to completion; download the video; return (dest, remote_meta)."""
    deadline, t0 = time.time() + timeout, time.time()
    while time.time() < deadline:
        try:
            h = json.loads(api(node, f"/history/{pid}", timeout=15))
        except Exception:
            h = {}
        if pid in h:
            st = h[pid]["status"]
            if st.get("completed") or st.get("status_str") == "success":
                for out in h[pid]["outputs"].values():
                    for v in out.get("images", []) + out.get("video", []) + out.get("gifs", []):
                        if v["filename"].endswith((".mp4", ".webm", ".mkv")):
                            q = urllib.parse.urlencode({"filename": v["filename"],
                                "subfolder": v.get("subfolder", ""), "type": v.get("type", "output")})
                            dest.write_bytes(api(node, f"/view?{q}", timeout=600))
                            print(f"  [{tag}] done in {time.time()-t0:.0f}s -> {dest.name}", flush=True)
                            return dest, v
                raise RuntimeError(f"{tag}: no video output: {list(h[pid]['outputs'])}")
            if st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                raise RuntimeError(f"{tag} error on {node}: {json.dumps(msgs)[:900]}")
        time.sleep(8)
    raise TimeoutError(f"{tag} timed out on {node}")


def ssh(host, cmd):
    subprocess.run(["ssh", "-o", "ConnectTimeout=8", f"keyspark@{host}", cmd],
                   check=True, capture_output=True, text=True)


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def micro(node, template, args, prompt, seed, prefix, first=None, tag=""):
    pid = submit(node, base_clip(template, args, prompt, 5, seed, prefix, first=first))
    clip = OUTDIR / f"{prefix}.mp4"
    wait_and_fetch(node, pid, clip, timeout=2400, tag=tag)
    png = OUTDIR / f"{prefix}.png"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip),
         "-vf", "select=eq(n\\,2)", "-frames:v", "1", str(png)])
    return png


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--identity-prompt")
    ap.add_argument("--identity-image")
    ap.add_argument("--anchor-prompt", required=True)
    ap.add_argument("--prompt-a", required=True)
    ap.add_argument("--weld-prompt", required=True, help="the transition motion from A's end to the anchor")
    ap.add_argument("--prompt-b", required=True)
    ap.add_argument("--workflow", default=str(Path.home() / "comfy" / "jc-noupscale-api.json"))
    ap.add_argument("--te", choices=list(TE_FILES), default="keep")
    ap.add_argument("--la", type=int, default=175)
    ap.add_argument("--lb", type=int, default=175)
    ap.add_argument("--lw", type=int, default=39, help="weld length (17k+5 grid); ~39 = short")
    ap.add_argument("--width", type=int, default=576)
    ap.add_argument("--height", type=int, default=768)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--nodes", default="10.100.10.2:8188,10.100.10.3:8188")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    template = json.loads(Path(args.workflow).expanduser().read_text())
    node_a, node_b = [n.strip() for n in args.nodes.split(",")][:2]
    host_a = node_a.split(":")[0]
    runid = time.strftime("%m%d_%H%M%S")
    OUTDIR.mkdir(exist_ok=True)
    out = Path(args.out).expanduser() if args.out else OUTDIR / f"weld_{runid}.mp4"
    seg_a, seg_b, weld = (OUTDIR / f"{runid}_A.mp4", OUTDIR / f"{runid}_B.mp4",
                          OUTDIR / f"{runid}_weld.mp4")
    fps = 24.0
    print(f"run {runid}: A({args.la}) ‖ B({args.lb}) + weld({args.lw}) @{args.width}x{args.height}, "
          f"wf={Path(args.workflow).name}, te={args.te}, nodes {node_a}+{node_b}", flush=True)
    t_start = time.time()

    # 0. identity ref
    identity_name = None
    if args.identity_image:
        identity_name = f"weld_{runid}_id.png"
        for n in (node_a, node_b):
            upload_image(n, args.identity_image, identity_name)
    elif args.identity_prompt:
        print("[identity] 5f ref...", flush=True)
        png = micro(node_b, template, args, args.identity_prompt, args.seed, f"{runid}_id", tag="identity")
        identity_name = f"weld_{runid}_id.png"
        for n in (node_a, node_b):
            upload_image(n, png, identity_name)

    # 1. anchor (B's start & weld's target)
    print("[anchor] 5f seam anchor...", flush=True)
    anchor_png = micro(node_a, template, args, args.anchor_prompt, args.seed, f"{runid}_anchor",
                       first=identity_name, tag="anchor")
    anchor_name = f"weld_{runid}_anchor.png"
    for n in (node_a, node_b):
        upload_image(n, anchor_png, anchor_name)

    # 2. parallel A (identity->free) on node_a, B (anchor->free) on node_b
    print(f"[parallel] A({args.la}f) on {node_a}  ||  B({args.lb}f) on {node_b}...", flush=True)
    a_meta = {}
    errs = []

    def render_a():
        try:
            _, m = wait_and_fetch(node_a, submit(node_a,
                base_clip(template, args, args.prompt_a, args.la, args.seed + 1, f"{runid}_A",
                          first=identity_name)), seg_a, tag="segA")
            a_meta.update(m)
        except Exception as e:
            errs.append(f"segA: {e}")

    def render_b():
        try:
            wait_and_fetch(node_b, submit(node_b,
                base_clip(template, args, args.prompt_b, args.lb, args.seed + 2, f"{runid}_B",
                          first=anchor_name)), seg_b, tag="segB")
        except Exception as e:
            errs.append(f"segB: {e}")

    ta, tb = threading.Thread(target=render_a), threading.Thread(target=render_b)
    t0 = time.time()
    ta.start(); tb.start(); ta.join(); tb.join()
    if errs:
        sys.exit("PARALLEL FAILED:\n  " + "\n  ".join(errs))
    print(f"[parallel] both done in {(time.time()-t0)/60:.1f} min", flush=True)

    # weld target = B's ACTUAL first frame (not the loose anchor), so weld->B is pixel-exact
    b0 = OUTDIR / f"{runid}_B0.png"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(seg_b),
         "-vf", "select=eq(n\\,0)", "-frames:v", "1", str(b0)])
    b0_name = f"weld_{runid}_B0.png"
    upload_image(node_a, b0, b0_name)

    # 3. weld on node_a: continue A's real frames+audio, land on B's real first frame
    ctx_name = f"weldctx_{runid}.mp4"
    sub = a_meta.get("subfolder", "")
    remote = f"$HOME/h3-cotenancy/ComfyUI/output/{sub + '/' if sub else ''}{a_meta['filename']}"
    ssh(host_a, f"cp \"{remote}\" \"$HOME/h3-cotenancy/ComfyUI/input/{ctx_name}\"")
    print(f"[weld] motion-context weld ({args.lw}f) on {node_a} continuing A -> B's frame 0...", flush=True)
    wpid = submit(node_a, weld_clip(template, args, args.weld_prompt, args.lw, args.seed + 3,
                                    f"{runid}_weld", ctx_name, b0_name))
    wait_and_fetch(node_a, wpid, weld, timeout=2400, tag="weld")

    # 4. stitch: (A ++ weld) butt join, then ++ B with dup-frame drop + short audio crossfade
    aw = OUTDIR / f"{runid}_AW.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(seg_a), "-i", str(weld), "-filter_complex",
         "[0:v][1:v]concat=n=2:v=1:a=0[v];[0:a][1:a]concat=n=2:v=0:a=1[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac", str(aw)])
    d = 4 / fps  # short audio crossfade at the weld->B seam
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aw), "-i", str(seg_b), "-filter_complex",
         f"[1:v]select=gte(n\\,1),setpts=PTS-STARTPTS[v1];[0:v][v1]concat=n=2:v=1:a=0[v];"
         f"[0:a][1:a]acrossfade=d={d:.4f}[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac", str(out)])
    ssh(host_a, f"rm -f \"$HOME/h3-cotenancy/ComfyUI/input/{ctx_name}\"")
    dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    print(f"\nDONE: {out}  ({float(dur):.1f}s, {out.stat().st_size/1e6:.1f} MB)")
    print(f"total wall: {(time.time()-t_start)/60:.1f} min")
    print(f"kept: {seg_a.name} {weld.name} {seg_b.name}  (seams: A→weld motion-context, weld→B anchor+xfade)")


if __name__ == "__main__":
    main()
