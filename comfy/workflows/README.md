# Power Pack workflows (latest)

Dual-node MiniMax-H3 quality multishot packages. Dual-serve co-tenancy foundation:
**[@tonyd2wild / ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory)**.

## Packages

| Package | Path | Engine | Length class | Status |
|---------|------|--------|--------------|--------|
| **Anime 2K bench** | [anime_2k_bench/](./anime_2k_bench/) | `h3-spans.py` master-K0 + **ESRGAN×2** | ~5s (3×39f @704×1280 → ~1408×2560) | ✅ Proven dual `0811_012837` · full stack + optional realism |
| **Bee FPV rain** | [bee_fpv_rain_20s/](./bee_fpv_rain_20s/) | `h3-spans.py` master-K0 FL2VA | ~18–20s (6×73f) | ✅ Proven dual `0808_231552` |
| **JC Power Pack promo** | [jc_promo_powerpack_30s/](./jc_promo_powerpack_30s/) | `h3-talkinghead.py` ref2va | ~30s (10×73f) | ✅ Proven dual `0808_220007` |
| **Will Smith spaghetti** | [will_smith_spaghetti_15s/](./will_smith_spaghetti_15s/) | `h3-talkinghead.py` ref2va | ~15s multishot | ✅ Multishot path |

More plan JSON (student story, HP pigeon, etc.): [../plans/](../plans/)

## Engines (repo `comfy/`)

| Script | Role |
|--------|------|
| `h3-spans.py` | Multishot KF → FL2VA spans, **MiniMax official prompt guide** |
| `h3-talkinghead.py` | Face-lock ref2va parallel spans |
| `h3_prompt_guide.py` | Official H3 VIDEO_PROMPT_WRITING_GUIDE helpers |
| `h3-weld.py` | Shared Comfy submit / wait / stitch helpers |
| `h3-parallel.py` | Independent clip fan-out |
| `h3-multishot.py` / `multishot_flf.py` | Older FLF dual pipelines |
| `jc-baseline-workflow-api.json` | Span graph + ESRGAN ×2 |
| `jc-noupscale-api.json` | KF / no-upscale FL2VA |
| `h3-r2v-heretic-enhanced.json` | Heretic ref2va talking-head graph |

## Quality defaults (all packages)
- Heretic TE · Sage · Sol-engine/SolAttn/Triton · Spectrum **v0.2.1** audio fix · FBC · ESRGAN on spans  
- **`H3_TURBO=0`** — Turbo is **not** for quality  
- Co-tenant span cap **≤73f** with ESRGAN  
- **2K path:** native legal size (e.g. **704×1280**) → ESRGAN×2 → ~**1408×2560** — [docs/H3_UPGRADES_2K.md](../../docs/H3_UPGRADES_2K.md)  
- Motion/A-V chain upgrades: Contex-Loop · MultiRef · NKD (restart Comfy after install)  
- Optional realism LoRA: `REALISM=1` on anime_2k_bench  
- Nodes: override `HEAD`/`WORKER` (lab `.2`+`.3` or live `.1`+`.5`)  
- Dual-serve profile: ablit **888k** / util **0.76**

## Future work
N-node scale-out (3–5 Sparks) and long solo arms (~362f): see [docs/FUTURE_WORK.md](../../docs/FUTURE_WORK.md).
