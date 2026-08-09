# Workflow: Will Smith spaghetti (~15s talking-head multishot)

Face-locked **ref2va** multishot — co-tenant safe alternative to continuous long gen (continuous 362f failed under dual-serve).

## Requirements
- Dual H3 · heretic TE · quality stack · **Turbo off**
- Local face ref at `ws_face.png` (or set `identity_portrait_png` / `IDENTITY_PNG`)

## Run
```bash
export HEAD=10.100.10.2 WORKER=10.100.10.3
bash comfy/workflows/will_smith_spaghetti_15s/run_ws_spaghetti_15s.sh
```

## Reference success
- Multishot run `0808_223919`: talking-head final under `~/Videos/will_smith_spaghetti_15s/`
- Continuous 362f under co-tenant: **interrupted** (use multishot)

## Files
| File | Role |
|------|------|
| `ws_spaghetti_15s_plan.json` | Scenes + lines |
| `run_ws_spaghetti_15s.sh` | Dual-node launcher |
