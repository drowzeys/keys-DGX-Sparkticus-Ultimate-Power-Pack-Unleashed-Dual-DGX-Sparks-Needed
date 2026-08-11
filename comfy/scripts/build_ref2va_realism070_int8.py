#!/usr/bin/env python3
"""Build a realism-merged int8-convrot MiniMax-H3 checkpoint for ComfyUI.

Takes the stock pruned int8-convrot checkpoint, dequantizes each quantized
layer, applies the Realism-People LoRA delta offline (W' = W + B@A), and
requantizes with the same convrot int8 recipe. token_refiner attn layers are
stored unquantized (BF16) in the stock file, so their deltas are applied by
direct addition. All other tensors are copied verbatim.

This avoids the runtime-LoRA corruption seen when ComfyUI applies LoRA deltas
on top of convrot-rotated int8 weights.

Usage:
  python3 build_realism_int8.py [--check-only]
"""

import argparse
import json
import struct
import sys

import torch
from safetensors import safe_open
from safetensors.torch import save_file

STOCK = "/home/keyspark/comfy/ComfyUI/models/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
LORA = "/home/keyspark/comfy/ComfyUI/models/loras/h3-realism-people-t2v-i2v-r2v.safetensors"
OUT = "/home/keyspark/comfy/ComfyUI/models/diffusion_models/minimax_h3_ref2va_realism070_int8_convrot_localmerge.safetensors"
STRENGTH = 0.7
GROUPSIZE = 256

try:
    from comfy_kitchen.tensor.int8 import TensorWiseINT8Layout as Layout
except ImportError:
    sys.path.insert(0, "/home/keyspark/comfy/ComfyUI")
    from comfy.quant_ops import _CKTensorWiseINT8Layout as Layout


def read_header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(n))


def dequant(qdata, scale):
    params = Layout.Params(
        scale=scale,
        orig_dtype=torch.float32,
        orig_shape=tuple(qdata.shape),
        is_weight=True,
        convrot=True,
        convrot_groupsize=GROUPSIZE,
    )
    return Layout.dequantize(qdata, params)


def requant(w):
    qdata, params = Layout.quantize(
        w, is_weight=True, per_channel=True, convrot=True, convrot_groupsize=GROUPSIZE
    )
    scale = params.scale
    if scale.dim() == 1:
        scale = scale.unsqueeze(1)
    return qdata, scale.to(torch.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="run kernel parity check and exit")
    args = ap.parse_args()

    dev = "cuda"
    hdr = read_header(STOCK)
    hdr.pop("__metadata__", None)

    stock = safe_open(STOCK, "pt", device="cpu")
    lora = safe_open(LORA, "pt", device="cpu")

    qlayers = sorted(k[: -len(".comfy_quant")] for k in hdr if k.endswith(".comfy_quant"))
    lora_layers = sorted({k.rsplit(".lora_", 1)[0].removeprefix("diffusion_model.") for k in lora.keys()})
    qset = set(qlayers)
    stock_keys = set(hdr)

    covered = [l for l in lora_layers if l in qset]
    unquant_targets = [l for l in lora_layers if l not in qset and f"{l}.weight" in stock_keys]
    missing = [l for l in lora_layers if l not in qset and f"{l}.weight" not in stock_keys]
    print(f"quantized layers: {len(qlayers)}; lora targets: {len(lora_layers)} "
          f"({len(covered)} quantized, {len(unquant_targets)} unquantized, {len(missing)} MISSING)")
    if missing:
        print("MISSING targets (delta will be skipped):", missing)

    # Kernel parity: requantizing a dequantized stock layer must reproduce it.
    k = covered[0]
    q0 = stock.get_tensor(f"{k}.weight").to(dev)
    s0 = stock.get_tensor(f"{k}.weight_scale").to(dev)
    q1, s1 = requant(dequant(q0, s0))
    bit_match = (q1 == q0).float().mean().item()
    off_by_one = ((q1 - q0).abs() <= 1).float().mean().item()
    scale_err = ((s1 - s0).abs() / s0.abs().clamp_min(1e-12)).max().item()
    print(f"parity check on {k}: int8 exact={bit_match:.6f}, |diff|<=1={off_by_one:.6f}, "
          f"max scale rel err={scale_err:.3e}")
    if off_by_one < 0.999:
        print("FATAL: round-trip does not reproduce stock quantization; kernel/recipe mismatch.")
        sys.exit(1)
    if args.check_only:
        return

    def delta_for(layer):
        a = lora.get_tensor(f"diffusion_model.{layer}.lora_A.weight").to(dev, torch.float32)
        b = lora.get_tensor(f"diffusion_model.{layer}.lora_B.weight").to(dev, torch.float32)
        return STRENGTH * (b @ a)

    out = {}
    max_rt_err = 0.0
    for i, layer in enumerate(covered):
        q = stock.get_tensor(f"{layer}.weight").to(dev)
        s = stock.get_tensor(f"{layer}.weight_scale").to(dev)
        w = dequant(q, s) + delta_for(layer)
        qn, sn = requant(w)
        rt = (dequant(qn, sn) - w).abs().max().item() / w.abs().max().clamp_min(1e-12).item()
        max_rt_err = max(max_rt_err, rt)
        out[f"{layer}.weight"] = qn.cpu()
        out[f"{layer}.weight_scale"] = sn.cpu()
        if (i + 1) % 50 == 0:
            print(f"  merged+requantized {i + 1}/{len(covered)}")

    for layer in unquant_targets:
        w = stock.get_tensor(f"{layer}.weight").to(dev, torch.float32)
        w = w + delta_for(layer)
        out[f"{layer}.weight"] = w.to(stock.get_tensor(f"{layer}.weight").dtype).cpu()
        print(f"  applied delta to unquantized {layer}")

    for key in hdr:
        if key not in out:
            out[key] = stock.get_tensor(key)

    print(f"max requant round-trip rel err: {max_rt_err:.3e}")
    print(f"writing {len(out)} tensors -> {OUT}")
    save_file(out, OUT)
    print("done")


if __name__ == "__main__":
    main()
