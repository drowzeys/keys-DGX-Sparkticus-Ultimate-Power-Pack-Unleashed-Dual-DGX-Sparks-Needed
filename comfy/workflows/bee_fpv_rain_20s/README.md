# Workflow: Bee FPV — flowers → forest → rain → dry (~20s)

**Saved for dual H3 stacks** (keyspark `.2` + `.3` co-tenant with DSV4F).

## What it is
- First-person **bee** flight through a **flower field** into a **forest**
- **Rain hits**, then **clears / dries**
- **Close-to-continuous**: 7 master-K0 keyframes + 6 FL2VA spans (73f each ≈ **18s**)
- **Two H3 instances** in parallel (`master-parallel` + dual span workers)
- Prompts follow MiniMax official guide (FL2VA headers, `[Shot 1]`, soundscape)

## Quality stack (required on both Comfy installs)
Heretic TE · Sage (`PathchSageAttentionKJ`) · SolAttn/Triton · Spectrum **v0.2.1**  
`offline_smoothing_replay=true` · FBC · ESRGAN ×2 on spans · **no Turbo**

## Run
```bash
# from this Power Pack repo (after dual H3 is up)
bash comfy/workflows/bee_fpv_rain_20s/run_bee_fpv_rain_20s.sh

# lab copies (if synced to stacks)
bash ~/comfy/workflows/bee_fpv_rain_20s/run_bee_fpv_rain_20s.sh
bash ~/h3-cotenancy/workflows/bee_fpv_rain_20s/run_bee_fpv_rain_20s.sh
```

Outputs: `~/Videos/bee_fpv_rain_20s/{runid}_final.mp4`

## Reference success
- Run `0808_231552`: **18.0s**, 1728×960, **22 min** wall, dual Spark, DS4 stayed up  
- Plan: `bee_fpv_rain_20s_plan.json`

## Files
| File | Role |
|------|------|
| `bee_fpv_rain_20s_plan.json` | Keyframes + span motions |
| `run_bee_fpv_rain_20s.sh` | One-shot dual-instance launcher |
| `scripts/h3-spans.py` | Multishot engine |
| `scripts/h3_prompt_guide.py` | Official MiniMax prompt builder |
| `jc-*-api.json` | Comfy API templates (KF / span+ESRGAN) |
| `keyframes_sample/` | Sample KF stills from 0808_231552 |

## Co-tenancy note
Do **not** use one continuous 20s sample while DSV4F is co-resident (OOM risk).  
This multishot recipe is the saved production path.
