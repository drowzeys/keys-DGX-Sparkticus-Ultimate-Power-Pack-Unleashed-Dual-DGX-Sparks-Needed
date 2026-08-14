# H3 Infinite Continuation — the v6 production stack (SEALED 2026-08-14)

The **continuous-take music-video pipeline** that produced *Hesitation v6*: latent-carried
clip chains where motion and native audio genuinely continue across joins, each clip
re-anchored by a fresh keyframe — enabling shots where **the world transforms around the
characters mid-action** (a couple dances on a campus path and the scene dissolves into a
mansion dining hall around them without the dance ever stopping).

Built on [Herrgott's H3 Infinite Continuation Suite](https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite)
(experimental community project) on top of this Power Pack's sealed bf16 config.

---

## The stack

| Piece | Value |
|---|---|
| Suite | `Herrgotts-H3-Infinite-Continuation-Suite` (git clone into custom_nodes) |
| DiT | `minimax_h3_fl2va_pruned_bf16` (finals tier — int8-convrot is draft only) |
| TE | STOCK `qwen3vl_32b_minimax_h3_int8_convrot` (heretic retired) |
| Sampler | res_multistep · simple · 20 steps · **CFG 1** · SigmaShift 12/3 |
| Clip length | 10 s (the suite's validated baseline) @ 864×480/24fps |
| Chain nodes | `H3ContinuousStartV11` → N× `H3ContinuousContinueV11` (+ SaveLatent + AnalyzeHandover `Balanced`) |
| Stitch | `H3ContinuousStitchSavedChainV11` per chain (memory-bounded, freeze-aware) |
| Cost | ~14.5 min per 10 s clip on a solo GB10 (bf16, no Sage/Sol) |
| Driver | [`comfy/h3-infinite-v6-driver.py`](../comfy/h3-infinite-v6-driver.py) + [`comfy/h3_infinite_v6_example_plan.json`](../comfy/h3_infinite_v6_example_plan.json) |

Chains are **strictly serial within a chain** (each clip continues the previous latent).
Parallelize across chains: v6 ran four chains on three GB10s (Act I on one node, Act III on
another, both solo-character chains on a third) — 23 clips of continuous footage in ~3 h wall.

## ⚠️ FINDING 1: one hook owner per process (two real collisions)

Only ONE pack may own the H3 `PackedLayout` runtime hooks in a ComfyUI process. The suite
detects conflicts and refuses to stack (good), but you must clear the field:

1. **ComfyUI-H3-Motion-Context / -MultiRef** — disable (rename `<dir>` → `<dir>.disabled`)
   on every node that renders chains, then restart ComfyUI.
2. **ComfyUI-SolAttn_triton** (`_morton_h3` patch) — the sneaky one: running ANY graph
   containing a `SolAttnPatch` node (e.g. this pack's own keyframe/span graphs) **poisons
   the process** for Continue nodes until restart. Strip the Sol node from keyframe graphs
   used alongside chains, or run keyframes and chains in separate ComfyUI processes.

Symptom of both: `cannot install its H3 runtime hooks: PackedLayout ... already owns`.
Fix: remove/strip the other pack, restart ComfyUI, resume the chain (latents persist).

## ⚠️ FINDING 2: the solo-cast rule applies to CHAIN PROMPTS

A cast preamble listing BOTH characters ("the same two people: ...") in a **solo-character
clip** summons the absent character and triggers mirror-image character doubling. This cost
v6 a full 4-clip chain re-render. For solo chains use:

> "ONLY ONE PERSON IN THIS ENTIRE SCENE: `<full character description>`. The `<other>` does
> NOT appear anywhere; no second person exists in any frame."

## FINDING 3: anchored re-rolls beat prompt engineering

When a keyframe repeatedly fails by text (doubled couples, camera-gaze, banquet crowds at
wide tables), generate it **anchored on a clean neighboring still** (I2V `first=`): the
composition inherits. A back-view anchor stays back-view; an embrace anchored on the
run-toward-him frame keeps one couple. Wide formal tables *love* to fill with guests —
"AT THE TABLE SIT ONLY TWO ELDERLY PEOPLE... every other chair EMPTY" + placing the table
far/small eventually holds, but anchoring is faster.

## FINDING 4: world-morph prompting

The money shots come from a Continue clip whose last-frame anchor is **the same characters
mid-action in a NEW location**, prompted:

> "THE WORLD CHANGES AROUND THEM WHILE THEY KEEP `<action>`: the same couple continue the
> same `<action>` without stopping as `<old location>` dissolves into `<new location>` ..."

The morph renders as an in-world cross-dissolve (~1.5 s) while the motion flows through —
because the motion context is carried in the latent, not restarted.

## FINDING 5: operational quirks

- **Stitcher output**: `StitchSavedChainV11` encodes directly into the node's
  `output/video/` dir and does NOT register an API output — poll the queue until empty,
  wait for the file size to stabilize, then fetch from disk.
- **Per-chain latent dirs** (`h3_continuous_<chain>/clip`) — multiple chains on one node
  collide without them.
- **Freeze-aware trims shorten acts ~10–15%** vs nominal clip-count × 10 s. Plan one extra
  clip per act if you need an exact song length (v6: 23 clips → 165.7 s vs a 177.8 s track).
- **Split-screen storylines**: never ask H3 for a split screen. Render two solo chains and
  compose in post: `crop=432:480:216:0` each + `hstack`.
- Suite + KJ SageAttention showed OOMs upstream; v6 ran chains with Sage disabled.

## v6 shape (reference)

Act I — 8-clip chain: meet → walk → dance → **campus-to-dining-hall morph mid-dance** →
seated dinner → argument → storm-out. Act II — two 4-clip SOLO chains (his world / her
world) composed as a split view. Act III — 7-clip chain: market reunion (wide freeze →
she runs) → embrace → map → **street-to-dunes morph** → beach → hands lace → silhouettes.
Keyframes: 27 stills, bf16, QC gate with ~40% re-roll rate (mostly camera-gaze / duplicate
/ crowd violations — see findings 2–3). Final: acts stitched per-chain, hard cuts between
acts, original song muxed with an end fade.

*Based on Tony's [ds4-h3-video-gen-factory](https://github.com/tonyd2wild/ds4-h3-video-gen-factory).*
