#!/usr/bin/env python3
"""Measure peak GPU + RAM of a single inline-upscale H3 span, co-resident with DSV4F.
Guard-aborts before OOM. Run AFTER a render completes. Grid points only (17k+5)."""
import importlib.util, json, subprocess, threading, time
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("h3weld", "/home/keyspark/comfy/h3-weld.py")
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

NODE = "10.100.10.2:8188"; HOST = "10.100.10.2"
TPL = json.loads(Path("/home/keyspark/comfy/jc-baseline-workflow-api.json").read_text())  # ESRGAN inline
ARGS = SimpleNamespace(te="keep", width=576, height=768)
FLOOR_ABORT_G = 5          # interrupt comfy if free RAM dips below this (safety margin, no OOM)
LENGTHS = [39, 56, 73]     # grid points; 90 already known to OOM -> not re-run

def free_g(host):
    try:
        return int(subprocess.run(["ssh","-o","ConnectTimeout=5",f"keyspark@{host}",
            "free -g | awk '/Mem:/{print $7}'"],capture_output=True,text=True,timeout=8).stdout.strip())
    except Exception:
        return None

def comfy_gpu_mib(host):
    """Peak GPU MiB used by the ComfyUI python proc (exclude DSV4F workers)."""
    try:
        out = subprocess.run(["ssh","-o","ConnectTimeout=5",f"keyspark@{host}",
            "nvidia-smi --query-compute-apps=used_memory,process_name --format=csv,noheader,nounits"],
            capture_output=True,text=True,timeout=8).stdout
        mib = 0
        for line in out.splitlines():
            m,name = [x.strip() for x in line.split(",")]
            if "VLLM" not in name and ("python" in name or "main" in name):
                mib = max(mib, int(m))
        return mib
    except Exception:
        return 0

results = []
for L in LENGTHS:
    print(f"\n=== measuring {L}f + inline upscale (co-resident) ===", flush=True)
    stop = {"v": False}; peak = {"gpu": 0, "ramfloor": 99, "aborted": False}
    def mon():
        while not stop["v"]:
            f = free_g(HOST)
            if f is not None:
                peak["ramfloor"] = min(peak["ramfloor"], f)
                if f < FLOOR_ABORT_G:
                    peak["aborted"] = True
                    subprocess.run(["curl","-s","-m5","-X","POST",f"http://{NODE}/interrupt"],
                                   capture_output=True)
                    print(f"  ABORT: free={f}G < {FLOOR_ABORT_G}G", flush=True)
            peak["gpu"] = max(peak["gpu"], comfy_gpu_mib(HOST))
            time.sleep(2)
    t = threading.Thread(target=mon); t.start()
    wf = W.base_clip(TPL, ARGS, "A person stands in a room, gentle motion, cinematic. Soundscape: soft room tone.",
                     L, 12000 + L, f"memtest_{L}")
    t0 = time.time()
    try:
        W.wait_and_fetch(NODE, W.submit(NODE, wf), Path(f"/home/keyspark/comfy/weld_out/memtest_{L}.mp4"),
                         timeout=1200, tag=f"{L}f")
        ok = not peak["aborted"]
    except Exception as e:
        ok = False; print(f"  span error/abort: {str(e)[:120]}")
    stop["v"] = True; t.join()
    dt = time.time() - t0
    results.append((L, peak["gpu"], peak["ramfloor"], ok, dt))
    print(f"  {L}f: peak_comfy_GPU={peak['gpu']/1024:.1f}GiB  RAM_floor={peak['ramfloor']}G  "
          f"{'OK' if ok else 'ABORTED/UNSAFE'}  {dt:.0f}s", flush=True)
    time.sleep(10)

print("\n==== SUMMARY (co-resident with DSV4F @888k/0.76) ====")
print(f"{'len':>5} {'peakGPU(GiB)':>13} {'RAMfloor(G)':>12} {'verdict':>10}")
for L,g,r,ok,dt in results:
    print(f"{L:>5} {g/1024:>13.1f} {r:>12} {'SAFE' if ok else 'UNSAFE':>10}")
print("90f: known OOM (not re-run).")
