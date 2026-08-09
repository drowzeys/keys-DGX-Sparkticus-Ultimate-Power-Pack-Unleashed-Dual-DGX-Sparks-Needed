# AGENT ONE-SHOT RECIPE  
## keys-abliterated / heretic Dual-Boot — DSV4F DSpark 0731 + MiniMax-H3 (concurrency=2)

**Repo:** https://github.com/drowzeys/keys-abliterated-heretic-Dual-Boot-DSV4F-Dspark0731-with-MiniMax-H3-concurrency-2  
**Audience:** coding agents — follow **exactly**. Do not improvise util, start order, or node IPs.

### 🙏 REQUIRED CREDIT — Tony’s Video Gen Factory

When you document, tweet, or hand off this stack, **always shout out Tony first**:

| | |
|--|--|
| **Upstream** | **[tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)** |
| **Author** | [Tony / tonyd2wild](https://github.com/tonyd2wild) |

Tony invented the dual-H3 + full DS4 co-tenancy factory (start order, util 0.78,
idle/1×/2× H3 benches, write-up). This keyspark tree is a **fork**: ablit dual-boot
+ heretic H3 + quality parallel path. Full write-up: **[CREDITS.md](./CREDITS.md)**.

Agents: include in any user-facing summary:  
*“Based on Tony’s [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).”*

Measured results (pre/post ablit, H3 upgrade, sequential vs parallel):  
→ **[KEYSPARK_RESULTS.md](./KEYSPARK_RESULTS.md)**

---

## 0. Goal (definition of done)

On **two** DGX Sparks:

| Service | Endpoint | Must show |
|---------|----------|-----------|
| DS4 ablit OpenAI API | `http://10.100.10.2:8888/v1/models` | `deepseek-v4-flash-0731-ablit-l10-35-anchorstock` |
| H3 Comfy heretic | `http://10.100.10.2:8188/system_stats` | HTTP 200 |
| H3 Comfy heretic | `http://10.100.10.3:8188/system_stats` | HTTP 200 |
| Video path | `bash deploy/keyspark/run_quality_parallel.sh` | writes ~10 s mp4 under `~/Videos/` |

**Fleet H3 concurrency = 2** = one heavy job per node, both nodes at once.  
**Never** schedule two full FLF jobs on a single Spark under DS4 co-tenancy.

---

## 1. Inventory (fixed topology)

| Role | Host | Fabric IP | Do not use |
|------|------|-----------|------------|
| DS4 head TP0 + H3 arm A | spark-7552 | **10.100.10.2** | `.1`, 5482 |
| DS4 worker TP1 + H3 arm B | spark-0060 | **10.100.10.3** | `.1`, 5482 |

SSH as `keyspark@10.100.10.2` / `keyspark@10.100.10.3` (passwordless assumed).

---

## 2. Hard rules (violation = broken stack)

1. **DS4 first, H3 second.** Wait until `/v1/models` is healthy before any Comfy launch.
2. **`GPU_MEMORY_UTILIZATION=0.78`** for this co-tenancy profile.  
   Fleet hard cap **0.85** (keyspark GB10 OOM policy). **Never raise above 0.85.** Prefer 0.78–0.85. Do not squeeze past 0.85 for more ctx/seqs.
3. H3 flags: **`--disable-pinned-memory` only**. Do **not** pass `--reserve-vram` while co-tenanting.
4. Teardown order: **stop H3 on both nodes → then stop DS4**.
5. Spectrum requires **ComfyUI ≥ 0.30.1** (`time_shift_slope`). On 0.30.0 set Spectrum off or upgrade.
6. Only nodes **.2 and .3**.

---

## 3. Prerequisites (once per fleet)

### 3.1 Clone this fork

```bash
git clone https://github.com/drowzeys/keys-abliterated-heretic-Dual-Boot-DSV4F-Dspark0731-with-MiniMax-H3-concurrency-2.git \
  ~/ds4-h3-video-gen-factory
cd ~/ds4-h3-video-gen-factory
```

### 3.2 DS4 DSpark recipe tree (Anemll image)

```bash
# Expected path (edit only if your lab differs — then export RECIPE=...)
ls ~/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731/start-deepseek-v4-flash-dspark.sh
docker image inspect ghcr.io/anemll/dspark-vllm-gx10:0.1.1 >/dev/null
```

### 3.3 Weights

| Set | Path under `~/.cache/huggingface/` |
|-----|--------------------------------------|
| Ablit champion (default dual-boot) | `dsv4f-0731-ablit-l10-35-anchorstock/` |
| Stock 0731 (optional STACK=stock) | `dsv4f-0731-stock/` |

Both head and worker must see the same cache path (or synced).

### 3.4 H3 tree per node

```bash
# On each of .2 and .3:
test -d ~/h3-cotenancy/ComfyUI
# After setup_h3_enhanced: heretic TE symlink + custom nodes present
```

If missing, run `bash deploy/keyspark/setup_h3_enhanced.sh` (copies heretic TE, Sol-Attn, Spectrum, KJNodes, upscaler weights, restarts Comfy).

### 3.5 Network

- Head serves DS4 on **8888** (fabric IP 10.100.10.2).
- H3 on **8188** each node.
- NCCL fabric settings are already in `env.ablit-cotenancy` (roce / enp1s0f1 — do not invent new NIC names without measuring).

---

## 4. One-shot bring-up (ablit + heretic)

```bash
cd ~/ds4-h3-video-gen-factory

# Default STACK=ablit → env.ablit-cotenancy
bash deploy/keyspark/bringup.sh

# Stock 0731 instead:
# STACK=stock bash deploy/keyspark/bringup.sh

# If heretic nodes already installed and you only need restart:
# ENHANCE_H3=0 bash deploy/keyspark/bringup.sh
```

**What bringup does (in order):**

1. Installs env as `$RECIPE/.env.dspark` on head+worker  
2. Prep stock bind-mounts / docker image presence  
3. Drop page caches  
4. Start DS4 TP=2 (worker-first inside recipe script); wait ≤600s for `/v1/models`  
5. `setup_h3_enhanced.sh` (default) or `launch_h3_dual.sh` → Comfy on both nodes  
6. `status.sh`

### 4.1 Verify

```bash
bash deploy/keyspark/status.sh
curl -s http://10.100.10.2:8888/v1/models | jq '.data[].id'
# expect: deepseek-v4-flash-0731-ablit-l10-35-anchorstock
curl -sf http://10.100.10.2:8188/system_stats >/dev/null && echo H3.2_OK
curl -sf http://10.100.10.3:8188/system_stats >/dev/null && echo H3.3_OK
```

Object-info smoke (heretic chain nodes):

```bash
for ip in 10.100.10.2 10.100.10.3; do
  curl -sf "http://$ip:8188/object_info" | python3 -c '
import sys,json
d=json.load(sys.stdin)
need=["PathchSageAttentionKJ","SolAttnPatch","SpectrumApplyMiniMaxH3","H3FirstBlockCache","MiniMaxH3ImageToVideo"]
print(sys.argv[1], {n:(n in d) for n in need})
' "$ip"
done
```

---

## 5. Patches & enhancements (what this fork adds)

| Component | Path | Purpose |
|-----------|------|---------|
| Ablit DS4 env | `deploy/keyspark/env.ablit-cotenancy` | ablit weights, util 0.78, H3_FLEET_CONCURRENCY=2 |
| Stock env | `deploy/keyspark/env.cotenancy` | Tony stock 0731 profile |
| Dual-boot profile | `deploy/keyspark/profile.ablit-heretic-dual.env` | video job env |
| Enhanced graph | `deploy/keyspark/enhanced_graph.py` | Sage→Sol→Spectrum→FBC→ESRGAN, heretic TE, FLF |
| H3 setup | `deploy/keyspark/setup_h3_enhanced.sh` | heretic TE symlink, custom nodes, Comfy 0.30.1 |
| Sequential video | `deploy/keyspark/hp_dragon_dual.py` | best seam, ~2× wall |
| **Parallel quality video** | `deploy/keyspark/keyframe_dual_flf.py` | concurrency=2, quality-first default |
| Runner | `deploy/keyspark/run_quality_parallel.sh` | preflight + parallel pipeline |
| Bringup/teardown/status | `deploy/keyspark/*.sh` | order-safe ops |

### H3 graph chain (post-upgrade)

```
UNET (minimax_h3_fl2va_pruned_int8_convrot)
  → PathchSageAttentionKJ (sage auto)
  → SolAttnPatch (tau 1.3)
  → SpectrumApplyMiniMaxH3          # needs Comfy ≥0.30.1
  → H3FirstBlockCache
  → MiniMaxH3ImageToVideo (+ optional first/last frame)
  → VAE decode → RealESRGAN_x2plus → CreateVideo
TE: H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors
```

### Quality-first parallel algorithm (default)

```
Phase 0  PARALLEL  .2: I0 human full steps (optional H3_I0_REF face seed)
                   .3: I1 mid dragon full steps
                   # I0 is NOT last_frame-constrained to I1 (protects face)
Phase 1  serial    I2 end dragon first=I1
Phase 2  PARALLEL  .2: FLF I0→I1 full 5s   ‖  .3: FLF I1→I2 full 5s
Phase 3  stitch    xfade → ~10s 1728×960
```

Fast mode (worse faces): `H3_QUALITY_ID=0`.

---

## 6. Run video (one shot)

```bash
cd ~/ds4-h3-video-gen-factory

# Quality dual-H3 ~10s (recommended)
bash deploy/keyspark/run_quality_parallel.sh

# Seed face from a known-good frame / prior clip
H3_I0_REF=~/Videos/some_good_face.png \
  bash deploy/keyspark/run_quality_parallel.sh

# Skip ESRGAN if faces look over-processed
H3_UPSCALE=0 bash deploy/keyspark/run_quality_parallel.sh

# Sequential (tightest continuity, ~2× wall)
PYTHONPATH=deploy/keyspark python3 deploy/keyspark/hp_dragon_dual.py
```

Outputs default: `~/Videos/hp_dragon_parallel_q/` · timing sidecar `TIMING.txt`.

---

## 7. Point Hermes / apps at ablit DS4

```yaml
# ~/.hermes/config.yaml (example)
model:
  base_url: http://10.100.10.2:8888/v1
  # model id as served:
  # deepseek-v4-flash-0731-ablit-l10-35-anchorstock
```

Restart Hermes gateway after change.

---

## 8. Teardown / restart

```bash
bash deploy/keyspark/teardown.sh          # H3 then DS4
bash deploy/keyspark/bringup.sh           # full dual-boot again
SKIP_H3=1 bash deploy/keyspark/bringup.sh # DS4 only
SKIP_DS4=1 bash deploy/keyspark/bringup.sh # H3 only (only if DS4 already up)
```

---

## 9. Failure playbook (agent checklist)

| Symptom | Cause | Fix |
|---------|-------|-----|
| DS4 OOM / won't load | H3 started first | teardown H3; drop caches; bringup DS4 first |
| Spectrum crash `time_shift_slope` | Comfy &lt; 0.30.1 | upgrade Comfy or `H3_SPECTRUM=0` |
| H3 OOM mid-render | 2 jobs one node / util too high | one job/node; keep util 0.78 |
| Bad Harry face | cheap scout locked FLF | `H3_QUALITY_ID=1` + optional `H3_I0_REF` |
| Stock model name on API | wrong env | `STACK=ablit` bringup; check `.env.dspark` |
| Worker missing image | docker only on head | `docker save \| ssh worker docker load` (bringup does this) |
| util set &gt; 0.85 | policy violation | **stop and lower**; reduce max_model_len / max_num_seqs instead |

---

## 10. Do not

- Touch `.1` / 5482 for this dual-boot.
- Raise `GPU_MEMORY_UTILIZATION` above **0.85**.
- Run two full 5 s FLF graphs on the same Spark with DS4 loaded.
- Skip DS4 health wait before H3.
- Commit secrets, HF tokens, or raw multi‑GB weights into the repo.

---

## 11. Speed expectations (see KEYSPARK_RESULTS.md)

| Workload | Ballpark |
|----------|----------|
| DS4 stock idle C1 | ~89 tok/s |
| DS4 stock + idle H3 C1 | ~84 tok/s |
| DS4 ablit + H3 co-res peak decode | ~81–83 tok/s (≈ stock) |
| DS4 C1 while **2× H3 rendering** | ~28 tok/s |
| 10 s video sequential basic | ~11.3 min @ 832×480 |
| 10 s video parallel enhanced | **~10.4 min @ 1728×960** |
| 10 s sequential enhanced (est.) | ~14.2 min @ 1728×960 |

---

## 12. Agent copy-paste block

```bash
set -euo pipefail
REPO=https://github.com/drowzeys/keys-abliterated-heretic-Dual-Boot-DSV4F-Dspark0731-with-MiniMax-H3-concurrency-2.git
test -d ~/ds4-h3-video-gen-factory || git clone "$REPO" ~/ds4-h3-video-gen-factory
cd ~/ds4-h3-video-gen-factory
git pull --ff-only || true
bash deploy/keyspark/bringup.sh
bash deploy/keyspark/status.sh
bash deploy/keyspark/run_quality_parallel.sh
echo "DONE — check ~/Videos/hp_dragon_parallel_q/"
```
