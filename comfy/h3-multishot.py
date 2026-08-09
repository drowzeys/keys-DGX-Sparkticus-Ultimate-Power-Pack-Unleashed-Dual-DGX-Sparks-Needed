#!/usr/bin/env python3
"""Dual-spark H3 multishot + batch renderer with a dependency-aware scheduler.

A VIDEO is a script of SHOTS separated by lines of `---`. By default each shot is an
independent HARD CUT (multishot look) and can render on any free node. Prefix a shot with
`@weld` to make it a seamless CONTINUATION of the previous shot (MiniMaxH3MotionContext:
same motion + same audio waveform); a welded shot is pinned to its predecessor's node and
runs after it. Optional per-shot directives on their own leading lines: `@len 124`, `@seed 42`.

Scheduling: every shot is a task; independent shots are dispatched to whichever of the two
nodes is free, welded shots wait for (and run on) their predecessor's node. This keeps BOTH
nodes saturated whether you render one multishot video (its cut-shots parallelize) or many
videos at once (--copies / multiple --script), i.e. batch throughput.

Memory-safe defaults: no inline upscale (use jc-noupscale-api.json); upscale later on .4.

Usage:
  ./h3-multishot.py --script story.txt [--copies 1] [--shot-len 124] [--seed 1000] \
     [--width 576 --height 768] [--workflow ~/comfy/jc-noupscale-api.json] [--te keep] \
     [--nodes 10.100.10.2:8188,10.100.10.3:8188] [--outdir ~/Videos/h3_multishot]
"""
import argparse, json, subprocess, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
import importlib.util

# reuse the proven helpers/builders from h3-weld.py
_spec = importlib.util.spec_from_file_location("h3weld", str(Path.home() / "comfy" / "h3-weld.py"))
W = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(W)


def parse_script(text):
    """-> list of shots: {prompt, join('cut'|'weld'), len(optional), seed(optional)}."""
    shots = []
    for block in text.split("\n---\n"):
        block = block.strip()
        if not block:
            continue
        join, length, seed, body = "cut", None, None, []
        for line in block.splitlines():
            s = line.strip()
            if s == "@weld":
                join = "weld"
            elif s.startswith("@len"):
                length = int(s.split()[1])
            elif s.startswith("@seed"):
                seed = int(s.split()[1])
            elif not s.startswith("#"):
                body.append(line)
        shots.append({"prompt": "\n".join(body).strip(), "join": join, "len": length, "seed": seed})
    return shots


def render_shot(node, host, template, args, shot, prefix, first_img=None, ctx_video=None,
                ctx_remote=None, target_img=None, tag=""):
    """Render one shot. ctx_video set => motion-context weld continuing ctx (serial)."""
    length = shot["len"] or args.shot_len
    seed = shot["seed"] if shot["seed"] is not None else shot["_seed"]
    if ctx_video:  # welded continuation
        ctx_name = f"msctx_{prefix}.mp4"
        W.ssh(host, f'cp "{ctx_remote}" "$HOME/h3-cotenancy/ComfyUI/input/{ctx_name}"')
        wf = W.weld_clip(template, args, shot["prompt"], max(length, 39), seed, prefix,
                         ctx_name, target_img)
    else:
        wf = W.base_clip(template, args, shot["prompt"], length, seed, prefix, first=first_img)
    dest = args._outdir / f"{prefix}.mp4"
    _, meta = W.wait_and_fetch(node, W.submit(node, wf), dest, tag=tag)
    if ctx_video:
        W.ssh(host, f'rm -f "$HOME/h3-cotenancy/ComfyUI/input/{ctx_name}"')
    return dest, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True, help="shot script (--- separated)")
    ap.add_argument("--copies", type=int, default=1, help="render N seed-variations (batch)")
    ap.add_argument("--shot-len", type=int, default=124)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--width", type=int, default=576)
    ap.add_argument("--height", type=int, default=768)
    ap.add_argument("--workflow", default=str(Path.home() / "comfy" / "jc-noupscale-api.json"))
    ap.add_argument("--te", choices=list(W.TE_FILES), default="keep")
    ap.add_argument("--nodes", default="10.100.10.2:8188,10.100.10.3:8188")
    ap.add_argument("--outdir", default=str(Path.home() / "Videos" / "h3_multishot"))
    ap.add_argument("--blend-frames", type=int, default=4, help="audio crossfade frames at cut joins")
    args = ap.parse_args()
    args.shot_len = args.shot_len

    template = json.loads(Path(args.workflow).expanduser().read_text())
    nodes = [n.strip() for n in args.nodes.split(",")][:2]
    hosts = {n: n.split(":")[0] for n in nodes}
    args._outdir = Path(args.outdir).expanduser(); args._outdir.mkdir(parents=True, exist_ok=True)
    runid = time.strftime("%m%d_%H%M%S")
    shots0 = parse_script(Path(args.script).expanduser().read_text())
    if not shots0:
        sys.exit("empty script")
    fps = 24.0
    print(f"run {runid}: {len(shots0)} shot(s) x {args.copies} copy(ies) @{args.width}x{args.height}, "
          f"nodes {'+'.join(nodes)}", flush=True)

    # build task list: one chain per (copy); shots within a chain ordered; weld depends on prev
    videos = []   # each: list of shot dicts (with _seed, _prefix, _id, _depends)
    for c in range(args.copies):
        chain = []
        for i, s in enumerate(shots0):
            sh = dict(s)
            sh["_seed"] = args.seed + c * 1000 + i
            sh["_prefix"] = f"{runid}_v{c}_s{i}"
            sh["_idx"] = i
            chain.append(sh)
        videos.append(chain)

    # flatten to tasks; weld shot depends on its predecessor (and inherits its node)
    for chain in videos:
        for sh in chain:
            sh["_dep"] = chain[sh["_idx"] - 1]["_prefix"] if (sh["join"] == "weld" and sh["_idx"] > 0) else None
    tasks = [sh for chain in videos for sh in chain]
    results = {}          # prefix -> (dest, meta)
    task_node = {}        # prefix -> node it ran on (for weld pinning)
    errs = []
    lock = threading.Lock()

    def next_task_for(node):
        """Pick a ready task this node may run. Cut tasks: any free node. Weld: only dep's node."""
        with lock:
            for sh in tasks:
                if sh.get("_state"):
                    continue
                dep = sh["_dep"]
                if dep is None:
                    sh["_state"] = "running"; return sh
                if dep in results and task_node.get(dep) == node:
                    sh["_state"] = "running"; return sh
            return None

    def all_done():
        with lock:
            return all(sh.get("_state") == "done" for sh in tasks)

    def worker(node):
        while True:
            if errs:
                return
            sh = next_task_for(node)
            if sh is None:
                if all_done():
                    return
                time.sleep(0.5); continue
            try:
                if sh["_dep"]:
                    _, pmeta = results[sh["_dep"]]
                    sub = pmeta.get("subfolder", "")
                    premote = f"$HOME/h3-cotenancy/ComfyUI/output/{sub + '/' if sub else ''}{pmeta['filename']}"
                    dest, meta = render_shot(node, hosts[node], template, args, sh, sh["_prefix"],
                                             ctx_video=True, ctx_remote=premote, target_img=None,
                                             tag=sh["_prefix"])
                else:
                    dest, meta = render_shot(node, hosts[node], template, args, sh, sh["_prefix"],
                                             tag=sh["_prefix"])
                with lock:
                    results[sh["_prefix"]] = (dest, meta)
                    task_node[sh["_prefix"]] = node
                    sh["_state"] = "done"
            except Exception as e:
                with lock:
                    errs.append(f"{sh['_prefix']}: {e}")
                return

    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(n,)) for n in nodes]
    [t.start() for t in threads]
    [t.join() for t in threads]
    if errs:
        sys.exit("FAILED:\n  " + "\n  ".join(errs))
    print(f"[render] all shots done in {(time.time()-t0)/60:.1f} min", flush=True)

    # stitch each video: weld joins = butt concat (already continuous); cut joins = hard cut + audio xfade
    d = args.blend_frames / fps
    outs = []
    for c, chain in enumerate(videos):
        cur = results[chain[0]["_prefix"]][0]
        for sh in chain[1:]:
            nxt = results[sh["_prefix"]][0]
            merged = args._outdir / f"{runid}_v{c}_upto{sh['_idx']}.mp4"
            if sh["join"] == "weld":
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cur), "-i", str(nxt),
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v];[0:a][1:a]concat=n=2:v=0:a=1[a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac",
                    str(merged)], check=True)
            else:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cur), "-i", str(nxt),
                    "-filter_complex", f"[0:v][1:v]concat=n=2:v=1:a=0[v];[0:a][1:a]acrossfade=d={d:.4f}[a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "aac",
                    str(merged)], check=True)
            cur = merged
        final = args._outdir / f"{runid}_video{c}.mp4"
        Path(cur).replace(final)
        dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout.strip()
        print(f"  video {c}: {final}  ({float(dur):.1f}s)")
        outs.append(final)
    print(f"\nDONE: {len(outs)} video(s) in {(time.time()-t0)/60:.1f} min total -> {args._outdir}")


if __name__ == "__main__":
    main()
