# Workflow: JC Power Pack promo (~30s talking-head multishot)

Face-locked **ref2va** multishot across dual H3 nodes — the Power Pack namesake continuous-*style* deliverable under co-tenancy (not one long sample).

## Requirements
- Dual H3 on `.2` + `.3` (Tony dual-serve co-tenancy OK)
- Heretic TE + quality stack; **Turbo off**
- Local face ref PNG at `face_ref.png` (or set `identity_portrait_png` in the plan)

## Run
```bash
# from repo root after dual H3 is up
export HEAD=10.100.10.2 WORKER=10.100.10.3
bash comfy/workflows/jc_promo_powerpack_30s/run_jc_promo_powerpack_30s.sh
```

## Reference success
- Run `0808_220007`: **30.4 s** (10×73f), 1152×1536, **~23 min** wall, dual Spark

## Files
| File | Role |
|------|------|
| `jc_promo_powerpack_30s_plan.json` | Scenes + spoken lines |
| `run_jc_promo_powerpack_30s.sh` | Dual-node launcher |
