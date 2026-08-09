# keys-DGX-Sparkticus Utimate Power Pack Unleashed (Dual DGX-Sparks Needed)

**Dual DGX Spark power stack:** DeepSeek-V4-Flash (DSpark, abliterated) co-tenant with MiniMax-H3
(heretic TE + Spectrum audio fix + Sol-Attn / FBC / ESRGAN) across **two** NVIDIA GB10 Sparks.

> Based on [tonyd2wild/ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).  
> Keyspark dual-boot specialization + H3 campaign optimizations.

## Validated live profile (keyspark)

| Layer | Setting |
|-------|---------|
| Nodes | `.2` head + `.3` worker only (never steal a 3rd for co-tenancy) |
| DS4 | ablit L10–35 anchorstock, TP=2, API `:8888` |
| Context | **888k** (`max_model_len=909312`) |
| GPU util | **0.76** (leave headroom for H3; hard fleet cap 0.85) |
| H3 | ComfyUI 0.31.1 on both nodes `:8188` |
| Spectrum | **v0.2.1**, `offline_smoothing_replay=true` default |
| H3 soft VRAM | `--reserve-vram 48 --vram-headroom 10 --disable-pinned-memory` |

Env file: `deploy/keyspark/env.ablit-cotenancy-888k-u076`

## Bring-up order (hard rule)

1. **DS4 first** until `http://HEAD:8888/v1/models` OK  
2. **H3 second** on both Sparks  
3. Teardown reverse (H3 → DS4)

```bash
# from a machine with fabric SSH to both Sparks
export ENV_SRC=$PWD/deploy/keyspark/env.ablit-cotenancy-888k-u076
export STACK=ablit HEAD=10.100.10.2 WORKER=10.100.10.3
bash deploy/keyspark/bringup.sh   # or SKIP_H3=1 then launch_h3_dual.sh
bash deploy/keyspark/status.sh
```

## H3 video (head / orchestrator)

Scripts under `comfy/` (run where you orchestrate, pointing at both `:8188`):

| Script | Role |
|--------|------|
| `h3-talkinghead.py` | Face-locked ref2va talking-head, dual-node parallel spans |
| `h3-spans.py` | FLF multishot + master-parallel keyframes |
| `h3-parallel.py` | Independent clip fan-out |
| `jc_baseline_continuous_powerpack.py` | ~30s continuous JC promo (speaks **this** pack name) |

### Co-tenancy RAM law (learned the hard way)

- With DS4 co-resident: **≤73 frames** per span with inline ESRGAN (56f default). **90f OOMs → node reboot.**
- Continuous ~719f / 30s is a **quality reference** — only safe with large free UMA or DS4 down on that box.
- Keep a RAM guard; interrupt Comfy if free RAM &lt; 4 GB.

Full narrative: [`docs/H3_VIDEO_CAMPAIGN_HANDOFF.md`](docs/H3_VIDEO_CAMPAIGN_HANDOFF.md)

## Credits

- Tony dual-boot factory: https://github.com/tonyd2wild/ds4-h3-video-gen-factory  
- Anemll / MiaAI / DSpark ecosystem for DSV4F-on-Spark serving  
- Spectrum MiniMax H3 v0.2.1 audio path (`offline_smoothing_replay`)  
- Sol-Attn / FBC Blackwell ports on GB10  

## License

See upstream factory `LICENSE` where applicable. Model weights are **not** redistributed here — fetch your own checkpoints.
