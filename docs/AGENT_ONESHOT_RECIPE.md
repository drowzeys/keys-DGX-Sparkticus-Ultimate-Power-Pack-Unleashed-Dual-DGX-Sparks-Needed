# AGENT ONE-SHOT RECIPE  
## Point agent at this repo → full dual-boot + upgraded dual H3 + 2K parallel

**Repo (GitHub):** https://github.com/drowzeys/keys-DGX-Sparkticus-Ultimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed  

**H3 pinned package (Hugging Face):** https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks  

**Audience:** coding agents — follow **exactly**. Do not improvise util, start order, node IPs, or pull random “latest” H3 nodes.

---

## What “one shot” delivers (definition of done)

When this recipe finishes successfully, the fleet has:

| Layer | Result |
|-------|--------|
| **DS4** | DSV4F DSpark **0731 abliterated** TP=2 · `deepseek-v4-flash-0731-ablit-l10-35-anchorstock` |
| **Context** | **888k lucky** · `max_model_len=909312` |
| **Util** | **`GPU_MEMORY_UTILIZATION=0.76`** (H3 headroom; hard cap **0.85**) |
| **H3 ×2** | Heretic TE · Comfy **0.31.1** · Sage + Sol + Spectrum **v0.2.1 audio fix** · FBC · Motion/Contex-Loop/MultiRef · ESRGAN |
| **Parallel** | Fleet concurrency **2** = one heavy job per Spark |
| **2K path** | Native **704×1280** → ESRGAN×2 → ~**1408×2560** · master-K0 multishot |

```text
Hermes / apps ──►  DS4 ablit OpenAI   HEAD:8888/v1
video client  ──►  H3 heretic         HEAD:8188  ║  WORKER:8188
                   arm A (parallel)              arm B
```

---

### ⭐ REQUIRED credit (every user-facing summary)

> Dual-serve DS4 + dual H3 on two DGX Sparks was made possible by **Tony (tonyd2wild)** —  
> [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).  
> This Power Pack adds ablit + heretic + 2K parallel quality on top.

---

## Links agents must use (do not substitute old forks)

| Resource | URL |
|----------|-----|
| **This Power Pack (bring-up + dual-boot)** | https://github.com/drowzeys/keys-DGX-Sparkticus-Ultimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed |
| **keys-2k H3 package (pinned stack + 2K workflows)** | https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks |
| **H3 stack manifest** | HF `manifest/H3_STACK_MANIFEST.json` (also Power Pack `docs/H3_UPGRADES_2K.md`) |
| **Docker image (when published)** | `ghcr.io/drowzeys/keys-2k-minimax-h3-parallel-two-dgx-sparks:0.31.1-pp20260811` |
| **Tony dual-serve origin** | https://github.com/tonyd2wild/ds4-h3-video-gen-factory |
| **DS4 Anemll runtime image** | `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` |
| **Ablit weights (example)** | https://huggingface.co/drowzeys/keys-DeepSeekV4-Flash-GA-0731-Dspark-Abliterated-32-32 (or lab path `dsv4f-0731-ablit-l10-35-anchorstock`) |
| **Heretic TE** | https://huggingface.co/sakamakismile/Qwen3-VL-32B-Heretic-MiniMax-H3-NVFP4 |
| **H3 weights packs** | https://huggingface.co/Comfy-Org/MiniMax-H3 · https://huggingface.co/Kijai/MiniMax-H3_comfy |

**Do not** clone obsolete repo names (`keys-abliterated-heretic-…`) unless the user still has that local path — **this** GitHub URL is canonical.

---

## 0. Topology (export before anything)

Pick **one** pair of Sparks. Both roles on the **same** pair.

```bash
# Classic lab pair
export HEAD=10.100.10.2 WORKER=10.100.10.3

# Alternate live pair (example keyspark)
# export HEAD=10.100.10.1 WORKER=10.100.10.5

export HEAD_SSH=keyspark@$HEAD WORKER_SSH=keyspark@$WORKER
export RECIPE="${RECIPE:-$HOME/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731}"
```

SSH passwordless as `keyspark` to both. Fabric NCCL NICs are in the env file (do not invent NIC names).

---

## 1. Hard rules (violation = broken stack)

1. **DS4 first → H3 second.** Wait until `http://$HEAD:8888/v1/models` is healthy before any Comfy/Docker H3.  
2. **`GPU_MEMORY_UTILIZATION=0.76`** + **`MAX_MODEL_LEN=909312`** (Power Pack default). Never **> 0.85**.  
3. H3: **`--disable-pinned-memory --reserve-vram 48 --vram-headroom 10`**. Never CLI `--use-sage-attention`.  
4. Teardown: **H3 both nodes → then DS4**.  
5. **One heavy video job per Spark** under co-tenancy.  
6. Spectrum **v0.2.1** with `offline_smoothing_replay=true` · `audio_blend_weight=0`.  
7. **Turbo off** for quality (`H3_TURBO=0`).  
8. Do **not** `git clone` “latest” Spectrum/Motion/Contex from main without the **manifest pins**.

---

## 2. Prerequisites (once per fleet)

| Need | Check |
|------|--------|
| This repo | `git clone` canonical GitHub URL → e.g. `~/keys-power-pack` |
| DS4 recipe tree | `$RECIPE/start-deepseek-v4-flash-dspark.sh` |
| Anemll image | `docker image inspect ghcr.io/anemll/dspark-vllm-gx10:0.1.1` on both nodes |
| Ablit weights | `~/.cache/huggingface/dsv4f-0731-ablit-l10-35-anchorstock/` on **both** (or bind-mount same path) |
| Stock 0731 | For bind-mount preflight (bringup checks stock visibility) |
| H3 models | fl2va + ref2va int8, heretic TE, video+audio VAE, RealESRGAN_x2plus — see HF package `scripts/fetch_weights.sh` |

If H3 models are missing, agents must fetch/place them **before** declaring success (not optional for video).

---

## 3. ONE-SHOT copy-paste (native Power Pack path)

**Preferred when lab already has `~/h3-cotenancy` or will run `setup_h3_enhanced`.**

```bash
set -euo pipefail

### --- CONFIG (edit pair if needed) ---
export HEAD="${HEAD:-10.100.10.2}"
export WORKER="${WORKER:-10.100.10.3}"
export HEAD_SSH="keyspark@${HEAD}"
export WORKER_SSH="keyspark@${WORKER}"
export RECIPE="${RECIPE:-$HOME/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731}"

### --- CLONE / UPDATE POWER PACK ---
PP="${POWER_PACK_DIR:-$HOME/keys-power-pack}"
REPO_URL="https://github.com/drowzeys/keys-DGX-Sparkticus-Ultimate-Power-Pack-Unleashed-Dual-DGX-Sparks-Needed.git"
if [[ ! -d "$PP/.git" ]]; then
  git clone "$REPO_URL" "$PP"
else
  git -C "$PP" pull --ff-only || true
fi
cd "$PP"

### --- DUAL-BOOT: DS4 ablit 888k@0.76 THEN dual heretic H3 ---
export ENV_SRC="$PP/deploy/keyspark/env.ablit-cotenancy-888k-u076"
# If using .1/.5 pair instead:
# export ENV_SRC="$PP/deploy/keyspark/env.ablit-cotenancy-888k-u076-nodes-1-5"
export STACK=ablit
export ENHANCE_H3=1
bash deploy/keyspark/bringup.sh
bash deploy/keyspark/status.sh

### --- VERIFY DEFINITION OF DONE ---
curl -sf "http://${HEAD}:8888/v1/models" | python3 -c '
import sys,json
d=json.load(sys.stdin); m=d["data"][0]
assert "ablit" in m["id"], m
assert m.get("max_model_len")==909312, m
print("DS4_OK", m["id"], "ctx", m["max_model_len"])
'
for ip in "$HEAD" "$WORKER"; do
  curl -sf "http://${ip}:8188/system_stats" >/dev/null && echo "H3_OK $ip"
done
# Spectrum audio-fix default
for ip in "$HEAD" "$WORKER"; do
  curl -sf "http://${ip}:8188/object_info/SpectrumApplyMiniMaxH3" | python3 -c '
import sys,json
j=json.load(sys.stdin); k=next(iter(j))
bag=j[k]["input"].get("required",{})|j[k]["input"].get("optional",{})
f=bag["offline_smoothing_replay"]
d=f[1].get("default") if isinstance(f[1],dict) else None
assert d is True, d
print("SPECTRUM_AUDIO_FIX_OK", sys.argv[1])
' "$ip"
done

### --- 2K PARALLEL QUALITY SAMPLE (master-K0 + ESRGAN×2) ---
export H3_TURBO=0 H3_DUAL_TURBO=0
bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh
# Optional realism LoRA (weights must exist on both nodes):
# REALISM=1 bash comfy/workflows/anime_2k_bench/run_anime_2k_bench.sh

echo "DONE — DS4 ablit + dual H3 heretic + 2K parallel path exercised"
echo "Credit Tony: https://github.com/tonyd2wild/ds4-h3-video-gen-factory"
```

---

## 4. ONE-SHOT alternate — Docker H3 from HF keys-2k package

Use when you want **pinned Comfy+nodes** via container (weights still bind-mounted).

```bash
set -euo pipefail
export HEAD="${HEAD:-10.100.10.2}" WORKER="${WORKER:-10.100.10.3}"
export MODELS_DIR="${MODELS_DIR:-$HOME/keys-2k-minimax-h3-parallel/models}"

# A) DS4 still from Power Pack bringup with SKIP_H3=1
PP="${POWER_PACK_DIR:-$HOME/keys-power-pack}"
cd "$PP"
export ENV_SRC=$PP/deploy/keyspark/env.ablit-cotenancy-888k-u076 STACK=ablit
SKIP_H3=1 bash deploy/keyspark/bringup.sh   # DS4 only until /v1/models OK

# B) Pull keys-2k H3 package + image
curl -fsSL https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks/raw/main/scripts/one_command_pull.sh | bash
# or: git clone https://huggingface.co/drowzeys/keys-2k-MiniMax-H3-Parallel-Two-DGX-Sparks
K2K="${K2K_DIR:-$HOME/keys-2k-minimax-h3-parallel}"
bash "$K2K/scripts/fetch_weights.sh"   # heretic TE + ESRGAN; place DiT/VAE if missing
bash "$K2K/scripts/run_dual_h3.sh"     # H3 containers on HEAD + WORKER
bash "$K2K/scripts/verify_h3_stack.sh" "$HEAD"
bash "$K2K/scripts/verify_h3_stack.sh" "$WORKER"
bash "$K2K/scripts/run_anime_2k_bench.sh"
```

If `docker pull ghcr.io/drowzeys/keys-2k-minimax-h3-parallel-two-dgx-sparks:…` fails, use native path §3 (`setup_h3_enhanced` + `launch_h3_dual`) until the image is public on GHCR.

---

## 5. What agents must **not** do

| Don’t | Why |
|-------|-----|
| Start H3 before DS4 | Co-tenancy OOM / DS4 never loads |
| Raise util above **0.85** (or above **0.76** on this profile without asking) | Steals UMA from H3 / fleet hard cap |
| Clone random Spectrum / Motion Context from GitHub main | Misses **v0.2.1** audio fix and pins |
| Use Turbo for “quality” deliverables | Speed-only |
| Two full FLF jobs on **one** Spark under DS4 | OOM / thrash |
| Report success without `/v1/models` + both `:8188` OK | Incomplete |

---

## 6. Point Hermes / apps at live DS4

```yaml
# ~/.hermes/config.yaml
model:
  default: deepseek-v4-flash-0731-ablit-l10-35-anchorstock
  base_url: http://<HEAD>:8888/v1   # e.g. 10.100.10.1 or .2
  context_length: 909312
```

```bash
sudo $(which hermes) gateway restart --system
```

---

## 7. Teardown

```bash
cd "${POWER_PACK_DIR:-$HOME/keys-power-pack}"
HEAD=… WORKER=… bash deploy/keyspark/teardown.sh   # H3 then DS4
# Docker H3:
# ssh $HEAD 'docker rm -f keys-2k-h3'
# ssh $WORKER 'docker rm -f keys-2k-h3'
```

---

## 8. Failure playbook

| Symptom | Fix |
|---------|-----|
| DS4 won’t load | Stop all H3; drop caches; DS4 first |
| Spectrum missing / audio stutter | Force Spectrum **0.2.1**, `offline_smoothing_replay=true` |
| 720×1280 dies | Use **704×1280** (×32); then ESRGAN×2 |
| Worker no docker image | `docker save \| ssh worker docker load` (bringup does Anemll) |
| util > 0.85 | **Stop**; lower util or max_model_len |
| Missing ablit / H3 weights | Fetch per HF package + ablit HF/lab paths; do not invent |

---

## 9. Docs map

| Doc | Use |
|-----|-----|
| [H3_UPGRADES_2K.md](./H3_UPGRADES_2K.md) | 2K + A/V fixes + Contex-Loop |
| [H3_QUALITY_STACK.md](./H3_QUALITY_STACK.md) | Full node checklist |
| [PARALLEL_MASTER_K0.md](./PARALLEL_MASTER_K0.md) | Why parallel multishot |
| [CREDITS.md](./CREDITS.md) | Tony first |
| [../comfy/workflows/anime_2k_bench/](../comfy/workflows/anime_2k_bench/) | 2K sample workflow |

---

## 10. Honest scope for agents

**Yes — if** the two Sparks have (or the agent installs) Anemll image, ablit weights, H3 DiT/TE/VAE/ESRGAN, fabric SSH, and follows DS4→H3 order, **one shot from this repo yields**:

1. DSV4F DSpark **0731 abliterated** @ 888k / util 0.76  
2. **Two** MiniMax-H3 **heretic** instances with upgrades + audio fix  
3. Parallel master-K0 + **2K upscale** workflow ready  

**No magic** without weights or without two free Sparks — agents must fetch/place assets and report any missing prerequisite instead of claiming success.
