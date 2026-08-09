# Multishot plan JSON library

Plans for `h3-spans.py` (FL2VA master-K0) or `h3-talkinghead.py` (ref2va face-lock).

| Plan | Engine | Notes |
|------|--------|-------|
| `bee_fpv_rain_20s_plan.json` | spans | Full package: `../workflows/bee_fpv_rain_20s/` |
| `jc_promo_powerpack_30s_plan.json` | talkinghead | Set `identity_portrait_png` to local face |
| `ws_spaghetti_15s_plan.json` | talkinghead | Set `identity_portrait_png` to local face |
| `student_talkinghead_plan.json` | talkinghead | Example dialogue plan |
| `student_story_plan.json` / `_56f` / `_narrated` | spans | Story multishot variants |
| `hp_pigeon_plan.json` / `_smoke` | spans | Scout / smoke FLF |

Face-locked plans ship with `./face_ref.png` (or `./ws_face.png`) placeholders — replace before run or pass `IDENTITY_PNG` to package runners.
