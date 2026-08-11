# H3 Speech Audio Fix — CFG 5.0 (gibberish speech in ComfyUI)

**Status:** ear-verified fix, 2026-08-11 · **Applies to:** every ComfyUI MiniMax-H3 stack (int8-convrot checkpoints, Comfy 0.31.1)

## Symptom

Generated people speak **fluent gibberish** — natural-sounding voice, correct timing and tone, but no intelligible words. Video is perfect. Native h3.c (Mac, bf16) renders the same prompt with clean speech.

## The fix

Sample with **CFG 5.0** instead of guidance-free `BasicGuider`. No negative prompt needed — a zeroed conditioning works:

```
MiniMaxH3ImageToVideo ──► ConditioningZeroOut ──► (negative)
                      └──────────────────────► (positive)
CFGGuider  { model, positive, negative, cfg: 5.0 }   ← replaces BasicGuider
```

That is the whole change. Same seed, same checkpoint, same TE: speech becomes clear and normal (A/B verified by ear against the corrupted and the h3.c-clean references, seed 777).

Reference graphs with the full wiring (also includes Spectrum v0.2.1 `offline_smoothing_replay=true` and the heretic TE): [`comfy/workflows/audio-fix-cfg5/`](../comfy/workflows/audio-fix-cfg5/)

## Cost

CFG runs two forward passes per step — expect roughly **2× sampling time**. Under DS4 co-tenancy budget one heavy job per Spark as usual.

## What it is NOT (all ruled out by isolation, seed-777 A/B)

| Suspect | Verdict |
|---|---|
| Checkpoint (stock vs realism-merged int8) | babble identical on both — not the weights |
| int8-convrot quantization / pruning | audio tensors intact; adaln curve table numerically exact (0.02% err vs bf16 MLP) |
| Audio VAE | round-trips real speech with near-perfect magnitude reconstruction |
| Text encoder (AWQ vs Heretic) | both babble without CFG |
| Spectrum / Sol-Attn / FBC / any custom pack | vanilla core Comfy (`--disable-all-custom-nodes`) still babbles |
| Per-modality sigma schedule (video shift 12 / audio 3) | ComfyUI's ModelSamplingAV carry is symbolically exact vs h3.c's formula |
| Prompt templating | ComfyUI tokenizes byte-identically to h3.c's raw encode (60/60 tokens matched) |

## Open question (why CFG is needed at all)

h3.c produces clean speech at **CFG ≡ 1** (it has no guidance machinery). With schedule, weights, VAE, and token ids all verified identical, the remaining candidates are second-order TE differences (hidden-state layer selection, attention-mask handling for short prompts) between h3.c's `h3_text_encode_bf16` and Comfy's `text_encoders/minimax.py`. If that delta is found and fixed, CFG could return to 1.0 and reclaim the 2× speed. Until then, CFG 5.0 is the production setting for any audio-bearing render.

## Prompt tips for speech

No special grounding syntax exists (prompts are raw-tokenized, unwrapped). But explicit structure measurably helps content adherence, especially under CFG: give the voice a concrete line, e.g.

```
… quiet room ambience. Audio: soft voice saying: "hello".
```
