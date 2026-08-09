#!/usr/bin/env python3
"""Two-node H3 render dispatcher: fans clips across head + node3 ComfyUI replicas.

Each node renders whole clips independently (data parallel), so N nodes give N x
throughput on batches. Single-clip latency is unchanged -- that needs context
parallelism, which is a different project.

Usage:
    ./h3-dispatch.py prompts.txt              # one prompt per line
    ./h3-dispatch.py --prompt "a cat" --n 4   # same prompt, 4 seeds
"""
import argparse, json, itertools, threading, time, urllib.request, sys
from pathlib import Path

NODES = ["127.0.0.1:8188", "10.100.10.1:8188"]
WORKFLOW = Path.home() / "comfy" / "h3-fullstack.json"


def post(node, wf):
    req = urllib.request.Request(f"http://{node}/prompt",
                                 data=json.dumps({"prompt": wf}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["prompt_id"]


def wait(node, pid, timeout=3600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{node}/history/{pid}", timeout=15) as r:
                h = json.load(r)
            if pid in h:
                return h[pid]["status"]["status_str"]
        except Exception:
            pass
        time.sleep(10)
    return "timeout"


def render(node, prompt, seed, tag, results):
    wf = json.loads(WORKFLOW.read_text())
    wf["104"]["inputs"]["prompt"] = prompt
    wf["15"]["inputs"]["noise_seed"] = seed
    wf["92"]["inputs"]["filename_prefix"] = f"video/dispatch_{tag}"
    t0 = time.time()
    try:
        pid = post(node, wf)
        status = wait(node, pid)
    except Exception as e:
        status = f"error: {e}"
    results.append((tag, node, status, round(time.time() - t0, 1)))
    print(f"  [{node}] {tag}: {status} in {time.time()-t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="file with one prompt per line")
    ap.add_argument("--prompt", help="single prompt")
    ap.add_argument("--n", type=int, default=1, help="seeds per prompt")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--nodes", default=",".join(NODES))
    args = ap.parse_args()

    nodes = [n.strip() for n in args.nodes.split(",") if n.strip()]
    if args.file:
        prompts = [l.strip() for l in Path(args.file).read_text().splitlines() if l.strip()]
    elif args.prompt:
        prompts = [args.prompt]
    else:
        sys.exit("need a prompt file or --prompt")

    jobs = [(p, args.seed + i) for p in prompts for i in range(args.n)]
    print(f"{len(jobs)} clip(s) across {len(nodes)} node(s): {', '.join(nodes)}")

    # simple round-robin; each node runs one clip at a time (H3 peaks ~100 GB)
    results, threads = [], []
    for i, (prompt, seed) in enumerate(jobs):
        node = nodes[i % len(nodes)]
        t = threading.Thread(target=render, args=(node, prompt, seed, f"{i:02d}_s{seed}", results))
        threads.append((t, node))

    per_node = {n: [t for t, nn in threads if nn == n] for n in nodes}
    workers = []
    for n, ts in per_node.items():
        def run_serial(ts=ts):
            for t in ts:
                t.start(); t.join()
        w = threading.Thread(target=run_serial); w.start(); workers.append(w)
    t0 = time.time()
    for w in workers:
        w.join()

    ok = sum(1 for r in results if r[2] == "success")
    print(f"\n{ok}/{len(jobs)} succeeded in {time.time()-t0:.0f}s wall "
          f"({(time.time()-t0)/max(ok,1):.0f}s per clip effective)")


if __name__ == "__main__":
    main()
