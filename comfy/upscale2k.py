#!/usr/bin/env python3
"""Standalone RealESRGAN ×2 for an already-rendered H3 clip (Comfy API).

Claude / keyspark async-2K path: after native spans finish (or mid-pipeline via
`h3-spans.py --upscale-async`), upscale a single mp4 on any free H3 node.

Usage:
  python3 upscale2k.py /path/to/clip.mp4 10.100.10.1:8188 video/myclip_x2

Requires: RealESRGAN_x2plus.pth in Comfy models/upscale_models, LoadVideo + VHS/KJ nodes.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    src, host, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
    model = sys.argv[4] if len(sys.argv) > 4 else "RealESRGAN_x2plus.pth"
    if "://" not in host and not host.startswith("http"):
        base = f"http://{host}"
    else:
        base = host.rstrip("/")

    up = subprocess.run(
        ["curl", "-s", "-m", "120", "-F", f"image=@{src}", f"{base}/upload/image"],
        capture_output=True,
        text=True,
        check=False,
    )
    if up.returncode != 0 or not up.stdout.strip():
        print("UPLOAD FAIL:", up.stderr or up.stdout, file=sys.stderr)
        sys.exit(1)
    name = json.loads(up.stdout)["name"]
    print("uploaded as", name, flush=True)

    wf = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": name}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
        "4": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {"upscale_model": ["3", 0], "image": ["2", 0]},
        },
        "5": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["4", 0], "fps": ["2", 2], "audio": ["2", 1]},
        },
        "6": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["5", 0],
                "filename_prefix": prefix,
                "format": "mp4",
                "codec": "h264",
            },
        },
    }
    body = json.dumps({"prompt": wf}).encode()
    req = urllib.request.Request(
        f"{base}/prompt", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        pid = json.loads(urllib.request.urlopen(req, timeout=30).read())["prompt_id"]
    except urllib.error.HTTPError as e:
        print("SUBMIT ERROR:", e.read().decode()[:800], file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    while True:
        time.sleep(8)
        h = json.loads(urllib.request.urlopen(f"{base}/history/{pid}", timeout=30).read())
        if pid not in h:
            if time.time() - t0 > 1800:
                print("TIMEOUT", file=sys.stderr)
                sys.exit(1)
            continue
        st = h[pid].get("status", {})
        if st.get("completed"):
            outs = h[pid].get("outputs", {})
            for o in outs.values():
                for v in o.get("images", []) + o.get("gifs", []) + o.get("video", []):
                    print("OUTPUT:", v.get("subfolder", ""), v.get("filename"))
            print(f"done in {time.time() - t0:.0f}s")
            return
        if st.get("status_str") == "error":
            print("EXEC ERROR:", json.dumps(st)[:800], file=sys.stderr)
            sys.exit(1)
        if time.time() - t0 > 1800:
            print("TIMEOUT", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
