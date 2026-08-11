# Live status — DSV4F DSpark 0731 **ABLIT** + MiniMax H3 **heretic TE** dual-boot

**Updated:** 2026-08-11  
**Profile:** Power Pack · H3 fleet **concurrency=2** · multishot **master-K0** video default  
**Live pair:** **`.1` + `.5`** (not the classic `.2`/`.3` lab pair)

**Upstream credit:** dual-serve co-tenancy by **[Tony / tonyd2wild](https://github.com/tonyd2wild)** —  
[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory). See [docs/CREDITS.md](../../docs/CREDITS.md).

## Stack: dual-boot (live on .1 / .5)

| Service | Node | Endpoint | Notes |
|---------|------|----------|-------|
| DS4 head (TP0) | `.1` gx10-5185 | `http://10.100.10.1:8888/v1` | **ablit L10–35 λ3.5** |
| DS4 worker (TP1) | `.5` gx10-5482 | headless | same |
| served model | | `deepseek-v4-flash-0731-ablit-l10-35-anchorstock` | |
| **Context** | | **`max_model_len=909312` (888k lucky)** | not full 1M on co-tenant |
| **GPU mem util** | | **0.76** | **room for heretic H3 to shine** |
| H3 Comfy (arm A) | `.1` | `http://10.100.10.1:8188` | heretic TE + Spectrum |
| H3 Comfy (arm B) | `.5` | `http://10.100.10.5:8188` | heretic TE + Spectrum |
| Hermes gateway | `.4` spark-13b3 | system unit | **points at `.1:8888`** (live Power Pack) |

## Config

- DS4 env: `deploy/keyspark/env.ablit-cotenancy-888k-u076-nodes-1-5` → `$RECIPE/.env.dspark`  
  (`MAX_MODEL_LEN=909312`, `GPU_MEMORY_UTILIZATION=0.76`, `MASTER_ADDR=10.100.10.1`, `WORKER_HOST=10.100.10.5`)
- Profile: `profile.ablit-heretic-dual-nodes-1-5.env` (video jobs)
- Classic `.2`/`.3` env remains: `env.ablit-cotenancy-888k-u076`
- Weights: local `~/dsv4f-0731-stock-reablit-l10-35` bind-mounted as  
  `~/.cache/huggingface/dsv4f-0731-ablit-l10-35-anchorstock` (same md5 as champion)
- Stock preflight: bind from `/mnt/models-node2/DeepSeek-V4-Flash-0731`
- H3 TE: `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` (**heretic**)
- Hermes (`.4`): `~/.hermes/config.yaml` → `model.base_url=http://10.100.10.1:8888/v1`,  
  `context_length=909312`, gateway restarted 2026-08-11
- H3 upgrades (2026-08-11): Spectrum v0.2.1 audio fix · Contex-Loop / MultiRef / NKD on disk  
  · Realism LoRA · **2K path** [anime_2k_bench](../../comfy/workflows/anime_2k_bench/) · [H3_UPGRADES_2K.md](../../docs/H3_UPGRADES_2K.md)  
  · sample run `0811_012837` (~18.8 min dual parallel @704×1280)
- Video: **multishot KFs matched to master K0** + parallel short spans  
  (`h3-spans.py --kf-mode master-parallel`) — see [PARALLEL_MASTER_K0.md](../../docs/PARALLEL_MASTER_K0.md)

## Ops

```bash
ROOT=~/keys-DGX-Sparkticus-Utimate-Power-Pack-Unleashed/deploy/keyspark
source $ROOT/profile.ablit-heretic-dual-nodes-1-5.env
export ENV_SRC=$ROOT/env.ablit-cotenancy-888k-u076-nodes-1-5
export STACK=ablit ENHANCE_H3=0

# status
curl -s http://10.100.10.1:8888/v1/models | jq .
HEAD=10.100.10.1 WORKER=10.100.10.5 bash $ROOT/status.sh

# restart (H3 first, then DS4)
HEAD=10.100.10.1 WORKER=10.100.10.5 bash $ROOT/teardown.sh
HEAD=10.100.10.1 WORKER=10.100.10.5 ENV_SRC=$ENV_SRC STACK=ablit ENHANCE_H3=0 bash $ROOT/bringup.sh
```

## Bring-up notes (2026-08-11)

- Pair was previously empty of recipe/image/H3; bootstrap used fabric rsync from `.2` + local ablit reablit dirs.
- Disk was tight on 916G roots; freed capture/caches; ablit bind-mounts avoid a second 156G copy.
- Docker image: `ghcr.io/anemll/dspark-vllm-gx10:0.1.1` loaded on both nodes.
- Smoke: `/v1/models` returns ablit @ `max_model_len=909312`; both H3 `:8188` system_stats OK.
