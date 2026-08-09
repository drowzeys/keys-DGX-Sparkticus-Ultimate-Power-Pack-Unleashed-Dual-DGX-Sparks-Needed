# Agents — keyspark dual-boot (read first)

**Full one-shot recipe:** [`docs/AGENT_ONESHOT_RECIPE.md`](../../docs/AGENT_ONESHOT_RECIPE.md)  
**Measured speeds:** [`docs/KEYSPARK_RESULTS.md`](../../docs/KEYSPARK_RESULTS.md)  
**Credits:** [`docs/CREDITS.md`](../../docs/CREDITS.md)

## Credit Tony (required in user-facing output)

Upstream video factory is **Tony’s**:  
https://github.com/tonyd2wild/ds4-h3-video-gen-factory  

Always mention: *“Based on tonyd2wild/ds4-h3-video-gen-factory.”*  
Do not present keyspark dual-boot as the original factory.

## Non-negotiables

- Nodes: **10.100.10.2** + **10.100.10.3** only (never `.1`/5482)
- Order: **DS4 first → H3 second**; teardown reverse
- `GPU_MEMORY_UTILIZATION` default **0.78**, hard cap **0.85**
- H3 fleet concurrency **2** = one heavy job per Spark
- Default stack: ablit DS4 + heretic H3 (`STACK=ablit`)

## Video pipeline (default) — FLF multishot

Hermes-refined architecture (do not “simplify” to xfade dual T2V):

1. Sequential shared **keyframes** (first/last images)
2. Parallel arms with `first=K_i` `last=K_{i+1}` on both H3 boxes
3. **Hard-cut** stitch only (prev last == next first → seamless)

Natural skin / anti-plastic look is ON by default (`multishot_flf.NATURAL_SKIN`).
Prefer real pore texture language in prompts; skip ESRGAN if skin looks over-processed (`H3_UPSCALE=0`).

## Commands

```bash
bash deploy/keyspark/bringup.sh
bash deploy/keyspark/setup_h3_turbo.sh               # once: Turbo LoRA + nodes
bash deploy/keyspark/status.sh
# dual-Spark: 1× H3 Comfy on .2 + 1× H3 on .3, parallel key/arm waves
bash deploy/keyspark/run_quality_parallel.sh          # FLF multishot HP dragon
H3_I0_REF=/path/to/face.png bash deploy/keyspark/run_quality_parallel.sh
# few-step turbo (~4–8 steps):
H3_TURBO=1 bash deploy/keyspark/run_quality_parallel.sh
# dual-sampler HQ (ANe5s #21) + PARALLEL arms on both Sparks (default):
H3_DUAL_TURBO=1 H3_MOTION_CONTEXT=0 bash deploy/keyspark/run_quality_parallel.sh
# seamless audio (MC) — arms sequential on HEAD only:
H3_DUAL_TURBO=1 H3_MOTION_CONTEXT=1 bash deploy/keyspark/run_quality_parallel.sh
# longer FLF stories (Hermes scripts):
python3 deploy/keyspark/connelly_flf_20s.py
python3 deploy/keyspark/connelly_flf_30s.py
bash deploy/keyspark/teardown.sh
```
See `docs/DUAL_TURBO_MOTION.md`.
