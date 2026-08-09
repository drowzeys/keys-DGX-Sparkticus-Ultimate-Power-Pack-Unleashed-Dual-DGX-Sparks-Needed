# Live status — DSV4F DSpark 0731 **ABLIT** + MiniMax H3 **heretic TE** dual-boot

**Updated:** 2026-08-08  
**Profile:** Power Pack · H3 fleet **concurrency=2** · multishot **master-K0** video default  

**Upstream credit:** dual-serve co-tenancy by **[Tony / tonyd2wild](https://github.com/tonyd2wild)** —  
[ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory). See [docs/CREDITS.md](../../docs/CREDITS.md).

## Stack: dual-boot

| Service | Node | Endpoint | Notes |
|---------|------|----------|-------|
| DS4 head (TP0) | `.2` spark-7552 | `http://10.100.10.2:8888/v1` | **ablit L10–35 λ3.5** |
| DS4 worker (TP1) | `.3` spark-0060 | headless | same |
| served model | | `deepseek-v4-flash-0731-ablit-l10-35-anchorstock` | |
| **Context** | | **`max_model_len=909312` (888k lucky)** | not full 1M on co-tenant |
| **GPU mem util** | | **0.76** | **room for heretic H3 to shine** |
| H3 Comfy (arm A) | `.2` | `http://10.100.10.2:8188` | heretic TE + Spectrum |
| H3 Comfy (arm B) | `.3` | `http://10.100.10.3:8188` | heretic TE + Spectrum |
| Hermes gateway | `.4` spark-13b3 | system unit | points at `.2:8888` |

## Config

- DS4 env: `deploy/keyspark/env.ablit-cotenancy-888k-u076` → `$RECIPE/.env.dspark`  
  (`MAX_MODEL_LEN=909312`, `GPU_MEMORY_UTILIZATION=0.76`)
- Profile: `profile.ablit-heretic-dual.env` (video jobs)
- Weights: `dsv4f-0731-ablit-l10-35-anchorstock`
- H3 TE: symlink → `H3/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` (**heretic**)
- Hermes: `~/.hermes/config.yaml` `model.base_url=http://10.100.10.2:8888/v1`
- Video: **multishot KFs matched to master K0** + parallel short spans  
  (`h3-spans.py --kf-mode master-parallel`, `h3-talkinghead.py`) — see [PARALLEL_MASTER_K0.md](../../docs/PARALLEL_MASTER_K0.md)  
- **Future work:** multi-node parallel scale-out (2→5 Sparks, long solo arms) — [FUTURE_WORK.md](../../docs/FUTURE_WORK.md) · capacity plan [H3_PARALLEL_CAPACITY_PROJECT.md](../../docs/H3_PARALLEL_CAPACITY_PROJECT.md)

## Measured at ablit bring-up

- Weights load: **79.17 GiB**
- GPU KV: **1,496,343** tokens @ util 0.78
- Smoke: `ABLIT_OK` completion returned

## Ops

```bash
# status
curl -s http://10.100.10.2:8888/v1/models | jq .
bash ~/ds4-h3-video-gen-factory/deploy/keyspark/status.sh

# restart DS4 (stop H3 first)
bash ~/ds4-h3-video-gen-factory/deploy/keyspark/teardown.sh
# install env.ablit-cotenancy as .env.dspark, then:
ssh spark-7552 'cd ~/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark-0731 && ./start-deepseek-v4-flash-dspark.sh'

# Hermes after config change
sudo $(which hermes) gateway restart --system
```
