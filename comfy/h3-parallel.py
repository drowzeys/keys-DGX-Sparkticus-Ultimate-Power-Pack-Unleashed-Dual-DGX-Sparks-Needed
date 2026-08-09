#!/usr/bin/env python3
"""Segment-parallel single-video H3 renderer across two ComfyUI nodes.

Splits one continuous video into two temporal segments joined at an anchor
frame, rendered simultaneously on two nodes:

  0. Identity pass (optional, ~min): 5-frame micro-clip of the subject
     (--identity-prompt) -> identity ref image, or supply --identity-image.
  1. Anchor pass (~min): 5-frame micro-clip of the seam moment (conditioned
     on the identity ref if present); middle frame becomes the anchor.
  2. Parallel pass: node A renders segment 1 (first=identity, last=anchor)
     while node B renders segment 2 (first=anchor). FLF2V conditioning makes
     both segments land on the same seam pixel with the same subject.
  3. Stitch: ffmpeg xfade+acrossfade (default 4 frames) centred on the seam.

The workflow template (--workflow, API format) supplies the whole model
stack; nodes are located by class_type, so any H3 workflow built around
MiniMaxH3ImageToVideo + RandomNoise + SaveVideo works (e.g. h3-fullstack.json
or jc-baseline-workflow-api.json with Sage+Sol+Spectrum+FBC+ESRGAN).

Usage:
  ./h3-parallel.py --prompt-a "..." --prompt-b "..." --anchor-prompt "..." \
      [--identity-prompt "..." | --identity-image face.png] \
      [--workflow ~/comfy/h3-fullstack.json] [--frames 362] \
      [--width 864] [--height 480] [--seed 1000] [--te keep] \
      [--nodes 10.100.10.2:8188,10.100.10.3:8188] [--blend-frames 4]

--te keep uses the template's text encoder unchanged; stock/heretic force
the respective encoder file on the target nodes.
"""
import argparse, json, mimetypes, subprocess, sys, threading, time, urllib.parse, urllib.request, uuid
from pathlib import Path

OUTDIR = Path.home() / "comfy" / "parallel_out"
TE_FILES = {
    "keep": None,
    "stock": "qwen3vl_32b_minimax_h3_nvfp4_awq.STOCK.safetensors",
    "heretic": "H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors",
}


def api(node, path, data=None, headers=None, timeout=30):
    req = urllib.request.Request(f"http://{node}{path}", data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def upload_image(node, img_path, name):
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(str(img_path))[0] or "image/png"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n").encode() + Path(img_path).read_bytes() + (
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue"
        f"\r\n--{boundary}--\r\n").encode()
    api(node, "/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def find_node(wf, class_type):
    hits = [k for k, v in wf.items() if v.get("class_type") == class_type]
    if len(hits) != 1:
        sys.exit(f"workflow needs exactly one {class_type} node, found {len(hits)}")
    return hits[0]


def build_wf(template, args, prompt, frames, seed, prefix, first=None, last=None):
    """Instantiate the template: set prompt/dims/seed/prefix, rewire frame conditioning."""
    wf = json.loads(json.dumps(template))
    i2v = find_node(wf, "MiniMaxH3ImageToVideo")
    wf[find_node(wf, "RandomNoise")]["inputs"]["noise_seed"] = seed
    wf[find_node(wf, "SaveVideo")]["inputs"]["filename_prefix"] = f"video/{prefix}"
    if TE_FILES[args.te]:
        wf[find_node(wf, "CLIPLoader")]["inputs"]["clip_name"] = TE_FILES[args.te]
    wf[i2v]["inputs"].update(prompt=prompt, width=args.width, height=args.height, length=frames)
    # strip template frame conditioning + its orphaned LoadImage nodes, then re-wire
    for key in ("first_frame", "last_frame"):
        ref = wf[i2v]["inputs"].pop(key, None)
        if isinstance(ref, list):
            wf.pop(ref[0], None)
    for key, img in (("first_frame", first), ("last_frame", last)):
        if img:
            nid = f"par_{key}"
            wf[nid] = {"class_type": "LoadImage", "inputs": {"image": img}}
            wf[i2v]["inputs"][key] = [nid, 0]
    return wf


def submit(node, wf):
    r = json.loads(api(node, "/prompt", json.dumps({"prompt": wf}).encode(),
                       {"Content-Type": "application/json"}))
    if r.get("error") or r.get("node_errors"):
        raise RuntimeError(f"{node} rejected workflow: {json.dumps(r)[:800]}")
    return r["prompt_id"]


def wait_and_fetch(node, pid, dest, timeout=7200, tag=""):
    """Poll history until done, then download the SaveVideo output to dest."""
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
                            q = urllib.parse.urlencode(
                                {"filename": v["filename"], "subfolder": v.get("subfolder", ""),
                                 "type": v.get("type", "output")})
                            dest.write_bytes(api(node, f"/view?{q}", timeout=600))
                            print(f"  [{tag}] done in {time.time()-t0:.0f}s -> {dest.name}", flush=True)
                            return dest
                raise RuntimeError(f"{tag}: completed but no video output found: {list(h[pid]['outputs'])}")
            if st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                raise RuntimeError(f"{tag} failed on {node}: {json.dumps(msgs)[:800]}")
        time.sleep(10)
    raise TimeoutError(f"{tag} timed out on {node}")


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def micro_pass(node, template, args, prompt, seed, prefix, clip_path, png_path, first=None, tag=""):
    """Render a 5-frame micro-clip and extract its middle frame."""
    pid = submit(node, build_wf(template, args, prompt, 5, seed, prefix, first=first))
    wait_and_fetch(node, pid, clip_path, timeout=2700, tag=tag)
    run(["ffmpeg", "-y", "-i", str(clip_path), "-vf", "select=eq(n\\,2)", "-frames:v", "1", str(png_path)])
    return png_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt-a", required=True, help="segment 1 prompt")
    ap.add_argument("--prompt-b", required=True, help="segment 2 prompt")
    ap.add_argument("--anchor-prompt", required=True, help="the seam moment (still image description)")
    ap.add_argument("--identity-prompt", help="optional: subject portrait prompt for an identity ref pass")
    ap.add_argument("--identity-image", help="optional: existing identity ref image file")
    ap.add_argument("--workflow", default=str(Path.home() / "comfy" / "h3-fullstack.json"),
                    help="API-format workflow template supplying the model stack")
    ap.add_argument("--frames", type=int, default=362, help="frames per segment (17k+5 grid)")
    ap.add_argument("--width", type=int, default=864)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--nodes", default="10.100.10.2:8188,10.100.10.3:8188")
    ap.add_argument("--te", choices=list(TE_FILES), default="keep",
                    help="keep = template's TE; stock/heretic force that encoder")
    ap.add_argument("--blend-frames", type=int, default=4,
                    help="crossfade width at the seam; 0 = hard cut (drop duplicate frame)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    template = json.loads(Path(args.workflow).expanduser().read_text())
    node_a, node_b = [n.strip() for n in args.nodes.split(",")][:2]
    runid = time.strftime("%m%d_%H%M%S")
    OUTDIR.mkdir(exist_ok=True)
    out = Path(args.out).expanduser() if args.out else OUTDIR / f"parallel_{runid}.mp4"
    seg_a, seg_b = OUTDIR / f"{runid}_segA.mp4", OUTDIR / f"{runid}_segB.mp4"

    # preflight: forced TE must exist on both nodes
    if TE_FILES[args.te]:
        for n in (node_a, node_b):
            clips = json.loads(api(n, "/object_info/CLIPLoader"))["CLIPLoader"]["input"]["required"]["clip_name"][0]
            if TE_FILES[args.te] not in clips:
                sys.exit(f"{n}: TE '{TE_FILES[args.te]}' not in CLIPLoader options")

    fps = 24.0
    print(f"run {runid}: 2x{args.frames}f @{args.width}x{args.height} "
          f"({2*args.frames/fps:.1f}s total), wf={Path(args.workflow).name}, te={args.te}, "
          f"nodes {node_a} + {node_b}", flush=True)
    t_start = time.time()

    # 0. identity ref (optional)
    identity_name = None
    if args.identity_image:
        identity_name = f"par_{runid}_id.png"
        for n in (node_a, node_b):
            upload_image(n, args.identity_image, identity_name)
        print(f"[identity] uploaded {args.identity_image}")
    elif args.identity_prompt:
        print("[identity] rendering 5-frame identity ref...", flush=True)
        png = micro_pass(node_b, template, args, args.identity_prompt, args.seed,
                         f"par_{runid}_id", OUTDIR / f"{runid}_id.mp4", OUTDIR / f"{runid}_id.png", tag="identity")
        identity_name = f"par_{runid}_id.png"
        for n in (node_a, node_b):
            upload_image(n, png, identity_name)

    # 1. anchor pass: 5-frame micro-clip of the seam moment (identity-conditioned if available)
    print("[anchor] rendering 5-frame seam anchor...", flush=True)
    anchor_png = micro_pass(node_a, template, args, args.anchor_prompt, args.seed,
                            f"par_{runid}_anchor", OUTDIR / f"{runid}_anchor.mp4",
                            OUTDIR / f"{runid}_anchor.png", first=identity_name, tag="anchor")
    anchor_name = f"par_{runid}_anchor.png"
    for n in (node_a, node_b):
        upload_image(n, anchor_png, anchor_name)
    print(f"[anchor] extracted + uploaded to both nodes")

    # 2. parallel segments: A runs identity->anchor, B runs anchor->free
    print(f"[segments] rendering in parallel ({args.frames}f each)...", flush=True)
    wf_a = build_wf(template, args, args.prompt_a, args.frames, args.seed + 1, f"par_{runid}_A",
                    first=identity_name, last=anchor_name)
    wf_b = build_wf(template, args, args.prompt_b, args.frames, args.seed + 2, f"par_{runid}_B",
                    first=anchor_name)
    errs = []

    def worker(node, wf, dest, tag):
        try:
            wait_and_fetch(node, submit(node, wf), dest, tag=tag)
        except Exception as e:
            errs.append(f"{tag}: {e}")

    threads = [threading.Thread(target=worker, args=j) for j in
               [(node_a, wf_a, seg_a, "segA"), (node_b, wf_b, seg_b, "segB")]]
    t0 = time.time()
    [t.start() for t in threads]
    [t.join() for t in threads]
    if errs:
        sys.exit("FAILED:\n  " + "\n  ".join(errs))
    par_min = (time.time() - t0) / 60
    print(f"[segments] both done in {par_min:.1f} min wall (serial would be ~{2*par_min:.0f} min)")

    # 3. stitch at the seam
    dur_a = args.frames / fps
    if args.blend_frames > 0:
        d = args.blend_frames / fps
        run(["ffmpeg", "-y", "-i", str(seg_a), "-i", str(seg_b), "-filter_complex",
             f"[0:v][1:v]xfade=transition=fade:duration={d:.4f}:offset={dur_a - d:.4f}[v];"
             f"[0:a][1:a]acrossfade=d={d:.4f}[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac", str(out)])
    else:  # hard cut: drop segB's first frame (duplicate of the anchor)
        run(["ffmpeg", "-y", "-i", str(seg_a), "-i", str(seg_b), "-filter_complex",
             f"[1:v]select=gte(n\\,1),setpts=PTS-STARTPTS[v1];[1:a]atrim=start={1/fps:.5f},asetpts=PTS-STARTPTS[a1];"
             f"[0:v][0:a][v1][a1]concat=n=2:v=1:a=1[v][a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac", str(out)])
    dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    total_min = (time.time() - t_start) / 60
    print(f"\nDONE: {out}  ({float(dur):.1f}s video, {out.stat().st_size/1e6:.1f} MB)")
    print(f"total wall: {total_min:.1f} min (identity+anchor+parallel segments+stitch)")
    print(f"kept: {seg_a.name}, {seg_b.name}, anchor {anchor_name}"
          + (f", identity {identity_name}" if identity_name else ""))


if __name__ == "__main__":
    main()
