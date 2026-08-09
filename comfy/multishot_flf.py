#!/usr/bin/env python3
"""Generic dual-H3 multishot FLF engine (Hermes / keyspark architecture).

Correct seamless parallel pipeline for MiniMax-H3 concurrency=2:

  Phase 0  SEQUENTIAL quality KEYFRAMES K0..KN on one box (HEAD)
           — consistent identity / skin / lighting
           — each key can be re-anchored to H3_I0_REF (stops likeness drift)
           — OR chained so key_i first_frame = key_{i-1} last (pose continuity)

  Phase 1  Arms (three layouts):
           • PARALLEL no-MC: waves of 2 across HEAD(.2) ‖ WORKER(.3)
           • SEQUENTIAL MC: all arms on HEAD (full timeline audio)
           • PARALLEL MC (H3_MC_PARALLEL=1): split into 2 contiguous chains
             HEAD arms 1..⌈N/2⌉ ‖ WORKER arms ⌈N/2⌉+1..N
             MC audio continuous *within* each chain; one hard audio seam at mid
           — FLF seams are shared key pixels either way

  Phase 2  Stitch arms: hard-cut (H3_XFADE=0 default)
  Phase 3  optional FINAL-ONLY RealESRGAN — skip when per-arm H3_UPSCALE on
           Dual-Spark RealESRGAN x2: each arm (~5s / 124f) is upscaled inside its
           graph on .2 and .3 in parallel — small pieces over time, no full-clip pass

This is the workflow Hermes refined for dual-instance H3. Prefer it over
naive crossfade dual or independent T2V arms.

Usage (library):
  from multishot_flf import MultishotConfig, run_multishot
  run_multishot(cfg)

Usage (CLI demo — HP dragon 2-arm story):
  PYTHONPATH=... python3 multishot_flf.py
  H3_I0_REF=/path/to/face.png python3 multishot_flf.py

Env:
  H3_HEAD / H3_WORKER   default 10.100.10.2:8188 / .3:8188
  H3_W H3_H H3_LEN H3_LEN_KF H3_STEPS H3_STEPS_KF
  H3_SPECTRUM H3_UPSCALE (RealESRGAN_x2plus.pth per-arm on both boxes; 0=skip)
  H3_FINAL_UPSCALE=0   final-only after hardcut (prefer 0 when per-arm upscale on)
  H3_FINAL_UPSCALE_HOST=worker   if final-only used: default WORKER (.3)
  H3_XFADE=0.25            video+audio crossfade at each arm seam (0=hardcut only)
  H3_XFADE_TRANS=fade      ffmpeg xfade transition name
  H3_I0_REF             face/identity image for every key (recommended)
  H3_KEY_CHAIN=1        also chain keys (first=prev last) after face seed
  H3_KEY_MODE=face|chain|both   default face if ref else chain
  H3_MOTION_CONTEXT=1           MC audio/motion continuation
  H3_MC_PARALLEL=1              dual-chain MC on HEAD‖WORKER (~2× arm wall)
  H3_AUDIO_CONTEXT_LENGTH=120   audio pin frames @ 24fps
  OUT_DIR WORK_DIR

Credit: dual-H3 co-tenancy factory by tonyd2wild/ds4-h3-video-gen-factory;
        FLF multishot parallel architecture refined with Hermes on keyspark.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enhanced_graph import build_enhanced, build_video_upscale  # noqa: E402

# ---------------------------------------------------------------------------
# Natural skin / anti-plastic look (prepended to every prompt by default)
# ---------------------------------------------------------------------------
NATURAL_SKIN = """Skin & material truth (critical): real human (or creature) surface only —
visible pore texture, fine natural creases and folds, soft subsurface scatter,
subtle natural sheen (not plastic gloss), delicate peach-fuzz / body hair where
appropriate, faint freckling or natural unevenness. NO airbrushed porcelain,
NO CGI plastic, NO beauty-filter blur, NO mannequin smoothness, NO game-engine
shader look. Prefer 35mm film grain and practical light over digital perfection."""

HEAD = os.environ.get("H3_HEAD", "10.100.10.2:8188")
WORKER = os.environ.get("H3_WORKER", "10.100.10.3:8188")


@dataclass
class MultishotConfig:
    """N keys → N-1 motion arms; parallel waves of 2 on dual H3."""

    key_prompts: Sequence[str]
    arm_prompts: Sequence[str]
    # optional shared look bible prepended once
    look: str = ""
    # natural skin block
    natural_skin: bool = True
    # outputs
    out_dir: Path = field(default_factory=lambda: Path.home() / "Videos" / "multishot_flf")
    work_dir: Path = field(default_factory=lambda: Path("/tmp/multishot_flf"))
    final_name: str = "multishot_flf.mp4"
    # render
    width: int = int(os.environ.get("H3_W", "864"))
    height: int = int(os.environ.get("H3_H", "480"))
    kf_frames: int = int(os.environ.get("H3_LEN_KF", "49"))
    arm_frames: int = int(os.environ.get("H3_LEN", "124"))
    steps: int = int(os.environ.get("H3_STEPS", os.environ.get("STEPS", "20")))
    kf_steps: int = int(os.environ.get("H3_STEPS_KF", "20"))
    seed: int = int(os.environ.get("SEED", "42042"))
    spectrum: bool = os.environ.get("H3_SPECTRUM", "1") not in ("0", "false", "no")
    # Per-arm ESRGAN inside each sample graph on both H3 boxes (preferred).
    # Stitched hardcut is already x2 — set H3_FINAL_UPSCALE=0 (default).
    upscale: str | None = os.environ.get("H3_UPSCALE", os.environ.get("UPSCALE", "RealESRGAN_x2plus.pth"))
    # Final-only ESRGAN after stitch. Default OFF when per-arm is on.
    final_upscale: str | None = os.environ.get("H3_FINAL_UPSCALE", "0")
    # Prefer WORKER (.3) so full-clip ESRGAN never fights DS4 TP0 on HEAD (.2).
    # Empty / "worker" → cfg.worker; "head" → cfg.head; else host:port.
    final_upscale_host: str | None = os.environ.get("H3_FINAL_UPSCALE_HOST", "worker").strip() or "worker"
    # identity
    i0_ref: str | None = None
    # key generation: "face" re-anchors every key to ref; "chain" uses prev last;
    # "both" = first_frame=face (or prev) with chain for pose (uses prev last as first if no face)
    key_mode: str = "auto"  # auto | face | chain | both
    # hosts
    head: str = HEAD
    worker: str = WORKER
    # hard-cut default (FLF shared keys). Optional xfade via H3_XFADE>0 — often
    # looks worse (double-exposure jitter) on MC/dialogue arms; keep off unless needed.
    hardcut: bool = True
    # Seconds of xfade/acrossfade at each arm join. 0 = hard-cut only (default).
    xfade_s: float = float(os.environ.get("H3_XFADE", "0"))
    xfade_transition: str = os.environ.get("H3_XFADE_TRANS", "fade")
    # H3 Turbo LoRA (few-step) — QrusherZA ComfyUI-fixed / larryvrh original
    turbo: bool = os.environ.get("H3_TURBO", "0") not in ("0", "false", "no", "")
    turbo_lora: str = os.environ.get(
        "H3_TURBO_LORA", "minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors"
    )
    turbo_strength: float = float(os.environ.get("H3_TURBO_STRENGTH", "1.0"))
    turbo_low_vram: bool = os.environ.get("H3_TURBO_LOW_VRAM", "0") not in ("0", "false", "no", "")
    # Dual-sampler quality (ANe5s HF discussion #21) — rough ckpt850 then refine ckpt500
    # https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/discussions/21
    dual_turbo: bool = os.environ.get("H3_DUAL_TURBO", "0") not in ("0", "false", "no", "")
    turbo_lora_rough: str = os.environ.get(
        "H3_TURBO_LORA_ROUGH", "minimax_h3_turbo_4step_ckpt850.safetensors"
    )
    turbo_steps_rough: int = int(os.environ.get("H3_TURBO_STEPS_ROUGH", "4"))
    turbo_strength_rough: float = float(os.environ.get("H3_TURBO_STRENGTH_ROUGH", "1.0"))
    turbo_lora_refine: str = os.environ.get(
        "H3_TURBO_LORA_REFINE", "minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors"
    )
    turbo_steps_refine: int = int(os.environ.get("H3_TURBO_STEPS_REFINE", "6"))
    turbo_strength_refine: float = float(os.environ.get("H3_TURBO_STRENGTH_REFINE", "0.7"))
    # Motion Context — true audio/motion continuation (NikoDemon80)
    # https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context
    motion_context: bool = os.environ.get("H3_MOTION_CONTEXT", "0") not in ("0", "false", "no", "")
    context_length: int = int(os.environ.get("H3_CONTEXT_LENGTH", "22"))
    # Audio pin frames @ 24fps for MC timeline. Default 80 (~3.3s) balances natural bed
    # continuity vs double-speak (48=safer/shorter; 120≈full arm, more echo risk).
    audio_context_length: int = int(os.environ.get("H3_AUDIO_CONTEXT_LENGTH", "80"))
    # Natural audio policy: long pin + single turbo on MC arms (opt H3_MC_DUAL / H3_MC_DENSE)
    natural_audio: bool = os.environ.get("H3_NATURAL_AUDIO", "1") not in ("0", "false", "no", "")
    # Dual-chain parallel MC: split arms across HEAD‖WORKER (MC within each half)
    mc_parallel: bool = os.environ.get("H3_MC_PARALLEL", "1") not in ("0", "false", "no", "")

    def __post_init__(self):
        if isinstance(self.out_dir, str):
            self.out_dir = Path(self.out_dir)
        if isinstance(self.work_dir, str):
            self.work_dir = Path(self.work_dir)
        # Re-read upscale envs at instance time (class defaults freeze at import;
        # launchers often set H3_UPSCALE / H3_FINAL_UPSCALE after import).
        if "H3_UPSCALE" in os.environ or "UPSCALE" in os.environ:
            self.upscale = os.environ.get("H3_UPSCALE", os.environ.get("UPSCALE"))
        if "H3_FINAL_UPSCALE" in os.environ:
            self.final_upscale = os.environ.get("H3_FINAL_UPSCALE")
        if "H3_FINAL_UPSCALE_HOST" in os.environ:
            self.final_upscale_host = os.environ.get("H3_FINAL_UPSCALE_HOST", "worker").strip() or "worker"
        if self.upscale in ("0", "none", "None", ""):
            self.upscale = None
        if self.final_upscale in ("0", "none", "None", ""):
            self.final_upscale = None
        # Avoid double ESRGAN: if per-arm is on and final wasn't forced, keep final off
        if self.upscale and self.final_upscale and "H3_FINAL_UPSCALE" not in os.environ:
            self.final_upscale = None
        if "H3_XFADE" in os.environ:
            try:
                self.xfade_s = float(os.environ["H3_XFADE"])
            except ValueError:
                self.xfade_s = 0.0
        if "H3_XFADE_TRANS" in os.environ:
            self.xfade_transition = os.environ["H3_XFADE_TRANS"].strip() or "fade"
        if self.xfade_s < 0:
            self.xfade_s = 0.0
        n_keys = len(self.key_prompts)
        n_arms = len(self.arm_prompts)
        if n_keys < 2:
            raise ValueError("need at least 2 key prompts (start + end)")
        if n_arms != n_keys - 1:
            raise ValueError(f"arm_prompts must be n_keys-1 ({n_keys - 1}), got {n_arms}")
        if self.i0_ref:
            self.i0_ref = str(Path(self.i0_ref).expanduser().resolve())
        if self.key_mode == "auto":
            self.key_mode = "face" if self.i0_ref else "chain"
        if self.dual_turbo:
            self.turbo = True
            # dual path uses rough+refine step counts, not self.steps
        # Re-read step envs at instance time (class defaults freeze at import)
        if "H3_STEPS" in os.environ or "STEPS" in os.environ:
            self.steps = int(os.environ.get("H3_STEPS", os.environ.get("STEPS", str(self.steps))))
        if "H3_STEPS_KF" in os.environ:
            self.kf_steps = int(os.environ["H3_STEPS_KF"])
        elif self.turbo and self.kf_steps >= 16:
            self.kf_steps = 6
        if self.turbo and not self.dual_turbo and self.steps >= 16:
            if "H3_STEPS" not in os.environ and "STEPS" not in os.environ:
                self.steps = 6
        if self.turbo and self.kf_steps >= 16 and "H3_STEPS_KF" not in os.environ:
            self.kf_steps = 6
        # Spectrum v0.1.8 preliminary defaults work with Motion Context — keep user/env spectrum

    def full_prompt(self, body: str) -> str:
        parts = []
        if self.look:
            parts.append(self.look.strip())
        if self.natural_skin:
            parts.append(NATURAL_SKIN)
        parts.append(body.strip())
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# HTTP / Comfy helpers
# ---------------------------------------------------------------------------
def http_json(url, data=None, timeout=120):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def upload_image(host: str, path: Path, name: str) -> str:
    import mimetypes
    import uuid
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    raw = path.read_bytes()
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),
        raw,
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\ninput\r\n".encode(),
        f"--{boundary}--\r\n".encode(),
    ]
    req = urllib.request.Request(
        f"http://{host}/upload/image", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode()).get("name", name)


def queue(host: str, graph: dict, client_id: str) -> str:
    try:
        r = http_json(f"http://{host}/prompt", {"prompt": graph, "client_id": client_id}, timeout=60)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"queue {host}: {e.read().decode()[:2500]}") from e
    if "error" in r:
        raise RuntimeError(r)
    return r["prompt_id"]


def wait_done(host: str, pid: str, label: str, timeout: int = 9500) -> dict:
    t0 = time.time()
    last = 0
    while time.time() - t0 < timeout:
        try:
            hist = http_json(f"http://{host}/history/{pid}", timeout=30)
        except Exception:
            time.sleep(5)
            continue
        if pid in hist:
            entry = hist[pid]
            st = entry.get("status", {})
            s = st.get("status_str", "")
            if s == "success" or entry.get("outputs"):
                print(f"  [{label}] SUCCESS {time.time() - t0:.0f}s", flush=True)
                return entry
            if s == "error":
                for m in st.get("messages") or []:
                    if isinstance(m, list) and m and m[0] == "execution_error":
                        raise RuntimeError(f"{label}: {m[1].get('exception_message', '')[:1200]}")
                raise RuntimeError(f"{label}: {json.dumps(st)[:1200]}")
        if time.time() - last > 20:
            print(f"  [{label}] {time.time() - t0:.0f}s …", flush=True)
            last = time.time()
        time.sleep(4)
    raise TimeoutError(label)


def find_video(entry: dict) -> tuple[str, str, str]:
    for _nid, out in (entry.get("outputs") or {}).items():
        for _k, items in out.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and any(
                    it.get("filename", "").lower().endswith(e) for e in (".mp4", ".webm", ".mkv")
                ):
                    return it["filename"], it.get("subfolder", ""), it.get("type", "output")
    raise RuntimeError(f"no video: {json.dumps(entry.get('outputs'))[:1500]}")


def download(host: str, fn: str, sub: str, typ: str, dest: Path):
    from urllib.parse import quote
    q = f"filename={quote(fn)}&subfolder={quote(sub)}&type={typ}"
    with urllib.request.urlopen(f"http://{host}/view?{q}", timeout=600) as r:
        dest.write_bytes(r.read())
    print(f"  saved {dest} ({dest.stat().st_size / 1e6:.1f} MB)", flush=True)


def extract_frame(video: Path, out: Path, when: str = "last"):
    out.parent.mkdir(parents=True, exist_ok=True)
    if when == "first":
        cmd = ["ffmpeg", "-y", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)]
    elif when == "best_face":
        cmd = ["ffmpeg", "-y", "-ss", "0.35", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)]
    else:
        cmd = ["ffmpeg", "-y", "-sseof", "-0.05", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  frame[{when}] → {out}", flush=True)


def render(
    host: str,
    label: str,
    prompt: str,
    seed: int,
    prefix: str,
    length: int,
    steps: int,
    first: str | None,
    last: str | None,
    *,
    width: int,
    height: int,
    spectrum: bool,
    upscale: str | None,
    work: Path,
    turbo: bool = False,
    turbo_lora: str = "minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors",
    turbo_strength: float = 1.0,
    turbo_low_vram: bool = False,
    dual_turbo: bool = False,
    turbo_lora_rough: str = "minimax_h3_turbo_4step_ckpt850.safetensors",
    turbo_strength_rough: float = 1.0,
    turbo_steps_rough: int = 4,
    turbo_lora_refine: str = "minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors",
    turbo_strength_refine: float = 0.7,
    turbo_steps_refine: int = 6,
    motion_context: bool = False,
    prev_video: str | None = None,
    context_length: int = 22,
    audio_context_length: int = 120,
    motion_clip_index: int = 0,
) -> Path:
    g = build_enhanced(
        prompt, seed=seed, width=width, height=height, length=length, steps=steps,
        prefix=prefix, first_frame=first or None, last_frame=last or None,
        sage=os.environ.get("H3_SAGE", "auto"),
        spectrum=spectrum, upscale=upscale,
        turbo=turbo, turbo_lora=turbo_lora, turbo_strength=turbo_strength,
        turbo_low_vram=turbo_low_vram,
        dual_turbo=dual_turbo,
        turbo_lora_rough=turbo_lora_rough,
        turbo_strength_rough=turbo_strength_rough,
        turbo_steps_rough=turbo_steps_rough,
        turbo_lora_refine=turbo_lora_refine,
        turbo_strength_refine=turbo_strength_refine,
        turbo_steps_refine=turbo_steps_refine,
        motion_context=motion_context,
        prev_video=prev_video,
        context_length=context_length,
        audio_context_length=audio_context_length,
        motion_clip_index=motion_clip_index,
    )
    pid = queue(host, g, label)
    step_info = (
        f"dual={turbo_steps_rough}+{turbo_steps_refine}"
        if dual_turbo
        else f"steps={steps}"
    )
    print(
        f"  [{label}] queued {pid} on {host}  "
        f"len={length} {step_info} first={bool(first)} last={bool(last)} "
        f"mc={bool(prev_video)} dual_turbo={dual_turbo}",
        flush=True,
    )
    entry = wait_done(host, pid, label)
    fn, sub, typ = find_video(entry)
    dest = work / f"{label}.mp4"
    download(host, fn, sub, typ, dest)
    return dest


def run_parallel(jobs: Sequence[Callable[[], Path]]) -> list[Path]:
    results: dict[int, Path | BaseException] = {}

    def run(i, fn):
        try:
            results[i] = fn()
        except BaseException as ex:
            results[i] = ex

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(jobs)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - t0
    out: list[Path] = []
    for i in range(len(jobs)):
        r = results.get(i)
        if isinstance(r, BaseException):
            raise r
        out.append(r)  # type: ignore[arg-type]
    print(f"  parallel wave wall {wall:.0f}s", flush=True)
    return out


def prepare_face_ref(cfg: MultishotConfig) -> str | None:
    if not cfg.i0_ref:
        print("  [warn] no H3_I0_REF — weaker identity lock", flush=True)
        return None
    src = Path(cfg.i0_ref)
    if not src.is_file():
        raise FileNotFoundError(f"H3_I0_REF not found: {src}")
    norm = cfg.work_dir / "face_ref.png"
    if src.suffix.lower() in (".mp4", ".webm", ".mov", ".mkv"):
        subprocess.check_call(
            ["ffmpeg", "-y", "-ss", "0.5", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(norm)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.check_call(
            ["ffmpeg", "-y", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(norm)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    name = "face_ref.png"
    upload_image(cfg.head, norm, name)
    upload_image(cfg.worker, norm, name)
    print(f"  identity ref → both hosts as {name}", flush=True)
    return name


def hardcut_concat(clips: Sequence[Path], final: Path, work: Path):
    final.parent.mkdir(parents=True, exist_ok=True)
    lst = work / "concat_hardcut.txt"
    lst.write_text("\n".join(f"file '{p.resolve()}'" for p in clips) + "\n")
    subprocess.check_call(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-crf", "16", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final),
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"  FINAL hard-cut {final}", flush=True)


def _probe_duration(path: Path) -> float:
    return float(
        subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            text=True,
        ).strip()
    )


def _has_audio(path: Path) -> bool:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0", str(path),
            ],
            text=True,
        ).strip()
        return bool(out)
    except Exception:
        return False


def xfade_concat(
    clips: Sequence[Path],
    final: Path,
    work: Path,
    *,
    duration: float = 0.25,
    transition: str = "fade",
    fps: int = 24,
) -> Path:
    """Chain N arm clips with video xfade + audio acrossfade at each seam.

    Softens residual FLF/MC seam jitter (dual-chain mid cut, MC trim edges).
    Falls back to hardcut_concat on failure.
    """
    clips = [Path(c) for c in clips]
    if len(clips) < 2:
        raise ValueError("xfade_concat needs ≥2 clips")
    final.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    durs = [_probe_duration(c) for c in clips]
    min_d = min(durs)
    xf = float(duration)
    if xf <= 0:
        hardcut_concat(clips, final, work)
        return final
    # each clip must be longer than the fade
    max_xf = max(0.05, min_d * 0.45)
    if xf > max_xf:
        print(
            f"  [warn] xfade {xf:.2f}s clamped to {max_xf:.2f}s (shortest arm {min_d:.2f}s)",
            flush=True,
        )
        xf = max_xf

    all_audio = all(_has_audio(c) for c in clips)
    n = len(clips)
    parts: list[str] = []
    for i in range(n):
        parts.append(
            f"[{i}:v]fps={fps},format=yuv420p,setsar=1,setpts=PTS-STARTPTS[v{i}];"
        )
    # chained xfade: offset_k = sum(d[0..k]) - (k+1)*xf
    # after joining 0..k, running duration = sum(d[0..k]) - k*xf
    # next offset = that - xf = sum(d[0..k]) - (k+1)*xf
    for k in range(n - 1):
        # sum of durations of clips 0..k inclusive
        sum_prev = sum(durs[: k + 1])
        offset = max(0.0, sum_prev - (k + 1) * xf)
        left = f"v{k}" if k == 0 else f"x{k}"
        right = f"v{k + 1}"
        out_v = "v" if k == n - 2 else f"x{k + 1}"
        parts.append(
            f"[{left}][{right}]xfade=transition={transition}:duration={xf:.4f}:offset={offset:.4f}[{out_v}];"
        )

    if all_audio:
        for i in range(n):
            parts.append(
                f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                f"aresample=async=1:first_pts=0[a{i}];"
            )
        for k in range(n - 1):
            left = f"a{k}" if k == 0 else f"xa{k}"
            right = f"a{k + 1}"
            out_a = "a" if k == n - 2 else f"xa{k + 1}"
            parts.append(f"[{left}][{right}]acrossfade=d={xf:.4f}:c1=tri:c2=tri[{out_a}];")
        # strip trailing ;
        fc = "".join(parts).rstrip(";")
        map_args = ["-map", "[v]", "-map", "[a]"]
    else:
        fc = "".join(parts).rstrip(";")
        map_args = ["-map", "[v]", "-an"]
        print("  [warn] xfade: missing audio on some arms — video-only fade", flush=True)

    cmd = [
        "ffmpeg", "-y",
        *[x for c in clips for x in ("-i", str(c))],
        "-filter_complex", fc,
        *map_args,
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final),
    ]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"  [warn] xfade failed ({e}); hard-cut fallback", flush=True)
        hardcut_concat(clips, final, work)
        return final

    print(
        f"  FINAL xfade={xf:.2f}s×{n - 1} seams ({transition}) → {final}  "
        f"arms={'/'.join(f'{d:.2f}' for d in durs)}s",
        flush=True,
    )
    return final


def stitch_arms(
    clips: Sequence[Path],
    final: Path,
    work: Path,
    *,
    xfade_s: float = 0.0,
    xfade_transition: str = "fade",
    fps: int = 24,
    also_hardcut: Path | None = None,
) -> Path:
    """Phase 2 entry: optional xfade (preferred when xfade_s>0) + optional hardcut alias."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    if also_hardcut is not None:
        hardcut_concat(clips, also_hardcut, work)
    if xfade_s and xfade_s > 0:
        return xfade_concat(
            clips, final, work,
            duration=xfade_s, transition=xfade_transition, fps=fps,
        )
    hardcut_concat(clips, final, work)
    return final


def final_upscale_video(
    host: str,
    src: Path,
    dest: Path,
    model: str = "RealESRGAN_x2plus.pth",
    work: Path | None = None,
    *,
    label: str = "final_upscale",
    prefix: str = "video/final_upscale",
    timeout: int = 3600,
) -> Path:
    """Phase 3: RealESRGAN the stitched clip once (not per-arm).

    Uploads ``src`` into Comfy input/, runs build_video_upscale, downloads to
    ``dest``. Keeps audio from the native stitch. ~1–3 min for ~30s @ 576×768.
    """
    work = work or Path("/tmp/final_upscale")
    work.mkdir(parents=True, exist_ok=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        raise FileNotFoundError(f"final_upscale: missing source {src}")

    input_name = f"final_native_{int(time.time())}.mp4"
    host_ip = host.split(":")[0]
    comfy_root = os.environ.get("H3_COMFY_ROOT", "/home/keyspark/h3-cotenancy/ComfyUI")
    remote = f"{comfy_root}/input/{input_name}"
    # Prefer scp (same path MC uses) then refresh Comfy's file list via upload API.
    try:
        subprocess.check_call(["scp", "-q", str(src), f"keyspark@{host_ip}:{remote}"])
    except Exception as e:
        print(f"  [warn] scp final native: {e} — trying upload API only", flush=True)
    try:
        upload_image(host, src, input_name)
    except Exception as e:
        print(f"  [warn] upload final native: {e}", flush=True)

    g = build_video_upscale(input_name, model_name=model, prefix=prefix)
    pid = queue(host, g, label)
    print(
        f"  [{label}] queued {pid} on {host}  model={model}  src={src.name}",
        flush=True,
    )
    entry = wait_done(host, pid, label, timeout=timeout)
    fn, sub, typ = find_video(entry)
    download(host, fn, sub, typ, dest)
    print(f"  FINAL upscaled {dest} ({dest.stat().st_size / 1e6:.1f} MB)", flush=True)
    return dest


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------
def _preflight_motion_context(host: str) -> None:
    """Fail fast if NikoDemon80 Motion Context is missing on the host Comfy."""
    # host is "ip:8188" (same as queue/upload)
    base = host if host.startswith("http") else f"http://{host}"
    try:
        d = http_json(f"{base.rstrip('/')}/object_info", timeout=30)
    except Exception as e:
        raise RuntimeError(
            f"Motion Context preflight: Comfy unreachable at {base}: {e}"
        ) from e
    need = [
        "MiniMaxH3MotionContext",
        "MiniMaxH3MotionContextTrim",
        "MiniMaxH3MotionContextSaveLatent",
        "MiniMaxH3MotionContextLoadLatent",
        "LoadVideo",
        "GetVideoComponents",
    ]
    missing = [n for n in need if n not in d]
    if missing:
        raise RuntimeError(
            "Motion Context nodes missing on "
            f"{base}: {missing}. Install: bash deploy/keyspark/setup_h3_turbo.sh "
            "(NikoDemon80/ComfyUI-H3-Motion-Context)"
        )
    print(
        f"  MC preflight OK on {base}  "
        f"(timeline audio · context_latent Save/Load · len=22)",
        flush=True,
    )


def run_multishot(cfg: MultishotConfig) -> Path:
    t_all = time.time()
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    n_keys = len(cfg.key_prompts)
    n_arms = len(cfg.arm_prompts)
    if cfg.motion_context:
        _preflight_motion_context(cfg.head)
        if cfg.mc_parallel:
            _preflight_motion_context(cfg.worker)
    mc_mode = (
        "parallel-chains"
        if (cfg.motion_context and cfg.mc_parallel)
        else ("sequential" if cfg.motion_context else "off")
    )
    print(
        f"mode=FLF-MULTISHOT  keys={n_keys} arms={n_arms}  "
        f"key_mode={cfg.key_mode} natural_skin={cfg.natural_skin}\n"
        f"  spectrum={cfg.spectrum} per_arm_upscale={cfg.upscale}  "
        f"final_upscale={cfg.final_upscale}  "
        f"kf={cfg.kf_frames}x{cfg.kf_steps} arm={cfg.arm_frames}x{cfg.steps}\n"
        f"  turbo={cfg.turbo} dual_turbo={cfg.dual_turbo} "
        f"motion_context={cfg.motion_context} mc={mc_mode}\n"
        f"  dual: rough={cfg.turbo_lora_rough}@{cfg.turbo_strength_rough} "
        f"x{cfg.turbo_steps_rough} → refine={cfg.turbo_lora_refine}"
        f"@{cfg.turbo_strength_refine} x{cfg.turbo_steps_refine}\n"
        f"  hardcut={cfg.hardcut} xfade_s={cfg.xfade_s} "
        f"(xfade softens residual seam jitter; 0=hardcut only)",
        flush=True,
    )

    for host, name in ((cfg.head, ".2"), (cfg.worker, ".3")):
        try:
            s = http_json(f"http://{host}/system_stats", timeout=6)
            print(f"H3 {name} {host} ram_free={s['system']['ram_free'] / 1e9:.1f}G", flush=True)
        except Exception as e:
            print(f"H3 {name} DOWN: {e}", file=sys.stderr)
            sys.exit(1)

    # clear queues
    for host in (cfg.head, cfg.worker):
        try:
            http_json(f"http://{host}/interrupt", {}, timeout=10)
            http_json(f"http://{host}/queue", {"clear": True}, timeout=10)
        except Exception:
            pass

    face = prepare_face_ref(cfg)

    # --- Phase 0: keyframes ---
    # face mode: keys are independent → PARALLEL waves across .2 and .3
    # chain/both: depends on prev key → sequential on HEAD
    keys_parallel = cfg.key_mode == "face"
    print(
        f"\n=== PHASE 0: keyframes K0..K{n_keys - 1} "
        f"({'PARALLEL dual-H3' if keys_parallel else f'sequential on {cfg.head}'}) ===\n"
        f"  mode={cfg.key_mode}  hosts={cfg.head} ‖ {cfg.worker}",
        flush=True,
    )
    t0 = time.time()
    key_names: list[str] = []  # uploaded basenames on both hosts
    prev_last_name: str | None = None

    def _key_first(i: int) -> str | None:
        """first_frame for key i.

        face  — identity ref only (parallel; poses can jump → hardcut feels abrupt)
        chain — prev key last frame (sequential pose continuum; identity may drift)
        both  — K0=face ref; K1..=prev key (pose continuum + identity restated in prompt)
                best for hardcut multi-shot when keys are small variations of each other
        """
        first: str | None = None
        if cfg.key_mode == "face":
            first = face
        elif cfg.key_mode == "chain":
            first = prev_last_name
        elif cfg.key_mode == "both":
            # Prefer prev key for continuity; face only seeds K0
            first = prev_last_name if (i > 0 and prev_last_name) else face
        if i == 0 and face:
            first = face
        return first

    def _finish_key(i: int, vid: Path) -> str:
        key_png = cfg.work_dir / f"K{i}.png"
        extract_frame(vid, key_png, "last")
        shutil.copy2(key_png, cfg.out_dir / f"key_K{i}.png")
        kn = upload_image(cfg.head, key_png, f"K{i}.png")
        upload_image(cfg.worker, key_png, f"K{i}.png")
        return kn

    def _render_key(i: int, host: str) -> Path:
        # Keys always use *single* Turbo LoRA (few-step speed). Dual-sampler is
        # arm-only quality recipe — never strip turbo from keys when dual_turbo=1.
        use_key_turbo = cfg.turbo or cfg.dual_turbo
        return render(
            host, f"K{i}", cfg.full_prompt(cfg.key_prompts[i]), cfg.seed + i,
            f"video/kf_K{i}",
            cfg.kf_frames, cfg.kf_steps, _key_first(i), None,
            width=cfg.width, height=cfg.height, spectrum=cfg.spectrum,
            upscale=None,
            work=cfg.work_dir,
            turbo=use_key_turbo,
            turbo_lora=cfg.turbo_lora,  # ckpt500 — native few-step
            turbo_strength=cfg.turbo_strength,
            turbo_low_vram=cfg.turbo_low_vram,
            dual_turbo=False,
        )

    # H3_SKIP_KEYS=1 reuses work_dir/K{i}.png when all present (resume after arm fail)
    skip_keys = os.environ.get("H3_SKIP_KEYS", "0") not in ("0", "false", "no", "")
    existing_keys = [cfg.work_dir / f"K{i}.png" for i in range(n_keys)]
    if skip_keys and all(p.is_file() and p.stat().st_size > 1000 for p in existing_keys):
        print(f"  SKIP keys — reusing {n_keys} PNGs from {cfg.work_dir}", flush=True)
        for i, kp in enumerate(existing_keys):
            shutil.copy2(kp, cfg.out_dir / f"key_K{i}.png")
            kn = upload_image(cfg.head, kp, f"K{i}.png")
            upload_image(cfg.worker, kp, f"K{i}.png")
            key_names.append(kn)
            prev_last_name = kn
        phase0 = time.time() - t0
        print(f"  phase0 wall {phase0:.0f}s  — reused keys (skip render)", flush=True)
    elif keys_parallel:
        # wave of 2: even → HEAD (.2), odd → WORKER (.3)
        for w in range((n_keys + 1) // 2):
            batch = list(range(w * 2, min(w * 2 + 2, n_keys)))
            print(
                f"  -- key wave {w + 1}: "
                + ", ".join(
                    f"K{i}@{'HEAD' if i % 2 == 0 else 'WORKER'}" for i in batch
                ),
                flush=True,
            )

            def make_kjob(i: int):
                host = cfg.head if i % 2 == 0 else cfg.worker
                return lambda i=i, host=host: _render_key(i, host)

            vids = run_parallel([make_kjob(i) for i in batch])
            for j, i in enumerate(batch):
                kn = _finish_key(i, vids[j])
                key_names.append(kn)
                prev_last_name = kn
        phase0 = time.time() - t0
        print(
            f"  phase0 wall {phase0:.0f}s  — {n_keys} keys on both boxes "
            f"(parallel dual-H3)",
            flush=True,
        )
    else:
        for i in range(n_keys):
            vid = _render_key(i, cfg.head)
            kn = _finish_key(i, vid)
            key_names.append(kn)
            prev_last_name = kn
        phase0 = time.time() - t0
        print(
            f"  phase0 wall {phase0:.0f}s  — {n_keys} keys on both boxes "
            f"(sequential)",
            flush=True,
        )

    # --- Phase 1: FLF arms ---
    # Dual-Spark layout: one H3 Comfy per machine (:8188 on .2 and .3).
    # • no MC → PARALLEL waves (arm0@.2 ‖ arm1@.3)
    # • MC + H3_MC_PARALLEL=1 → two contiguous MC chains HEAD‖WORKER (~2×)
    # • MC sequential → all on HEAD (full timeline audio, no mid seam)
    use_mc_parallel = bool(cfg.motion_context and cfg.mc_parallel and n_arms >= 2)
    sequential = bool(cfg.motion_context and not use_mc_parallel)
    if use_mc_parallel:
        layout = "PARALLEL MC chains (HEAD‖WORKER, MC within each half)"
    elif sequential:
        layout = "SEQUENTIAL motion-context on HEAD"
    else:
        layout = "PARALLEL dual-H3 waves×2 (no MC)"
    _esr = cfg.upscale or "off"
    print(
        f"\n=== PHASE 1: FLF arms ({layout}) ===\n"
        f"  arm_i: first=K_i last=K_{{i+1}}  dual_turbo={cfg.dual_turbo}\n"
        f"  H3 instances: HEAD={cfg.head}  WORKER={cfg.worker}\n"
        f"  per-arm RealESRGAN x2: {_esr}  "
        f"(each arm ~{cfg.arm_frames}f upscaled on its host; dual-chain = 2 boxes parallel)",
        flush=True,
    )
    t1 = time.time()

    def arm_kwargs(
        i: int,
        prev_vid_name: str | None,
        *,
        chain_pos: int | None = None,
    ):
        # chain_pos = 0-based index *within* an MC chain (for parallel halves).
        # Global i still used for seed/prompt; clip index follows chain_pos.
        pos = int(chain_pos) if chain_pos is not None else i
        use_mc = cfg.motion_context and pos > 0 and bool(prev_vid_name)
        # Natural-audio speed path (default): single turbo + long audio pin.
        # Dual-stage on MC hits NestedTensor a(3)/b(2); dual arm1 is slower than
        # continuous .4 stock for little gain. Opt into dual with H3_MC_DUAL=1.
        steps_rough = cfg.turbo_steps_rough
        steps_refine = cfg.turbo_steps_refine
        dual = cfg.dual_turbo
        turbo = cfg.turbo
        arm_steps = cfg.steps
        audio_len = cfg.audio_context_length
        if cfg.motion_context and cfg.natural_audio:
            # Honor H3_AUDIO_CONTEXT_LENGTH exactly; only clamp to arm length.
            # Dialogue-heavy: 48–72 (bed/tone, less double-speak). Ambient: 120+.
            # Do NOT force min=120 — that re-introduced arm5-style echo on speech.
            audio_len = max(1, min(int(cfg.arm_frames), int(audio_len)))
            # default: single turbo N steps for ALL arms (arm1 + MC)
            # Opt into dual-stage on MC arms with H3_MC_DUAL=1 (quality vs invent).
            _mc_dual = os.environ.get("H3_MC_DUAL", "0") not in ("0", "false", "no", "")
            if _mc_dual and use_mc:
                dual = True
                turbo = True
                steps_rough = max(steps_rough, int(os.environ.get("H3_MC_STEPS_ROUGH", "6")))
                steps_refine = max(steps_refine, int(os.environ.get("H3_MC_STEPS_REFINE", "10")))
            else:
                dual = False
                turbo = True
                arm_steps = int(os.environ.get("H3_MC_STEPS", os.environ.get("H3_STEPS", "6")))
            # optional: dense non-turbo if H3_MC_DENSE=1
            if os.environ.get("H3_MC_DENSE", "0") not in ("0", "false", "no", ""):
                dual = False
                turbo = False
                arm_steps = int(os.environ.get("H3_MC_STEPS", "16"))
        return dict(
            width=cfg.width,
            height=cfg.height,
            spectrum=cfg.spectrum,
            upscale=cfg.upscale,
            work=cfg.work_dir,
            turbo=turbo,
            turbo_lora=cfg.turbo_lora,
            turbo_strength=cfg.turbo_strength,
            turbo_low_vram=cfg.turbo_low_vram,
            dual_turbo=dual,
            turbo_lora_rough=cfg.turbo_lora_rough,
            turbo_strength_rough=cfg.turbo_strength_rough,
            turbo_steps_rough=steps_rough,
            turbo_lora_refine=cfg.turbo_lora_refine,
            turbo_strength_refine=cfg.turbo_strength_refine,
            turbo_steps_refine=steps_refine,
            motion_context=use_mc,
            prev_video=prev_vid_name,
            context_length=cfg.context_length,
            audio_context_length=audio_len,
            # clip index is chain-local so each host's h3_context/ stays 1..len
            motion_clip_index=(pos + 1) if cfg.motion_context else 0,
            # arm_steps only used when not dual_turbo
            _arm_steps=arm_steps,
        )

    comfy_root = os.environ.get(
        "H3_COMFY_ROOT", "/home/keyspark/h3-cotenancy/ComfyUI"
    )

    def run_mc_chain(host: str, arm_indices: list[int], label: str) -> list[Path]:
        """Sequential MC along arm_indices on one host. Returns paths in chain order."""
        host_ip = host.split(":")[0]
        input_dir = f"{comfy_root}/input"
        out_ctx = f"{comfy_root}/output/h3_context"
        try:
            subprocess.check_call(
                [
                    "ssh",
                    f"keyspark@{host_ip}",
                    f"mkdir -p {out_ctx} {input_dir}; rm -f {out_ctx}/clip_*.safetensors",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"  [warn] {label} mkdir/clear ctx: {e}", flush=True)

        chain_paths: list[Path] = []
        prev_input_name: str | None = None
        print(
            f"  [{label}] host={host} arms={[a + 1 for a in arm_indices]} "
            f"(MC within chain)",
            flush=True,
        )
        for pos, i in enumerate(arm_indices):
            fn = i + 1
            ap = cfg.full_prompt(cfg.arm_prompts[i])
            if pos > 0:
                prev_path = chain_paths[-1]
                prev_input_name = f"mc_prev_arm{fn - 1}_{label}.mp4"
                remote = f"{input_dir}/{prev_input_name}"
                subprocess.check_call(
                    ["scp", "-q", str(prev_path), f"keyspark@{host_ip}:{remote}"],
                )
                try:
                    upload_image(host, prev_path, prev_input_name)
                except Exception as e:
                    print(f"  [warn] upload_image prev: {e}", flush=True)
                print(
                    f"  [{label}] mc prev → {host_ip}:{remote}",
                    flush=True,
                )
            ak = arm_kwargs(i, prev_input_name, chain_pos=pos)
            arm_steps = ak.pop("_arm_steps", cfg.steps)
            if cfg.motion_context and cfg.natural_audio and pos > 0:
                if ak.get("dual_turbo"):
                    step_s = (
                        f"dual={ak.get('turbo_steps_rough')}+"
                        f"{ak.get('turbo_steps_refine')}"
                    )
                else:
                    step_s = f"single_turbo steps={arm_steps}"
                print(
                    f"  [{label}] natural-audio arm{fn}: dual={ak.get('dual_turbo')} "
                    f"{step_s} audio_pin={ak.get('audio_context_length')}f "
                    f"(~{float(ak.get('audio_context_length', 0))/24:.1f}s)",
                    flush=True,
                )
            p = render(
                host,
                f"arm{fn}",
                ap,
                cfg.seed + 100 + i,
                f"video/arm{fn}",
                cfg.arm_frames,
                arm_steps,
                key_names[i],
                key_names[i + 1],
                **ak,
            )
            chain_paths.append(p)
            shutil.copy2(p, cfg.out_dir / f"arm{fn}.mp4")
            if cfg.motion_context:
                try:
                    listing = subprocess.check_output(
                        [
                            "ssh",
                            f"keyspark@{host_ip}",
                            f"ls -la {out_ctx}/ 2>/dev/null || true",
                        ],
                        text=True,
                    )
                    print(f"  [{label}] h3_context after arm{fn}:\n{listing}", flush=True)
                except Exception:
                    pass
        return chain_paths

    all_arms: list[Path] = []
    if use_mc_parallel:
        # Contiguous split: HEAD gets first half, WORKER second half.
        # MC continuous within half; visual seam at mid is shared key PNG;
        # audio may restart at the chain boundary (honest trade for ~2× wall).
        mid = (n_arms + 1) // 2  # 6 → 3+3; 5 → 3+2
        head_idx = list(range(0, mid))
        worker_idx = list(range(mid, n_arms))
        print(
            f"  MC parallel split: HEAD arms{[a+1 for a in head_idx]} ‖ "
            f"WORKER arms{[a+1 for a in worker_idx]}  "
            f"(audio seam after arm{mid})",
            flush=True,
        )

        def _chain_head():
            return run_mc_chain(cfg.head, head_idx, "HEAD")

        def _chain_worker():
            return run_mc_chain(cfg.worker, worker_idx, "WORKER")

        # run_parallel expects Path; use threads returning list[Path]
        chain_results: dict[int, list[Path] | BaseException] = {}

        def _run_chain(i: int, fn: Callable[[], list[Path]]):
            try:
                chain_results[i] = fn()
            except BaseException as ex:
                chain_results[i] = ex

        th = [
            threading.Thread(target=_run_chain, args=(0, _chain_head)),
            threading.Thread(target=_run_chain, args=(1, _chain_worker)),
        ]
        tw0 = time.time()
        for t in th:
            t.start()
        for t in th:
            t.join()
        print(f"  parallel MC chains wall {time.time() - tw0:.0f}s", flush=True)
        for i in (0, 1):
            r = chain_results.get(i)
            if isinstance(r, BaseException):
                raise r
        # reassemble global arm order
        by_idx: dict[int, Path] = {}
        for idx_list, paths in (
            (head_idx, chain_results[0]),  # type: ignore[arg-type]
            (worker_idx, chain_results[1]),  # type: ignore[arg-type]
        ):
            for gi, p in zip(idx_list, paths):  # type: ignore[arg-type]
                by_idx[gi] = p
        all_arms = [by_idx[i] for i in range(n_arms)]
    elif sequential:
        all_arms = run_mc_chain(cfg.head, list(range(n_arms)), "HEAD")
    else:
        arm_jobs: list[tuple[str, str, Callable[[], Path]]] = []
        for i in range(n_arms):
            host = cfg.head if i % 2 == 0 else cfg.worker
            fn = i + 1
            ap = cfg.full_prompt(cfg.arm_prompts[i])

            def make_job(i=i, host=host, fn=fn, ap=ap):
                def _run():
                    ak = arm_kwargs(i, None)
                    arm_steps = ak.pop("_arm_steps", cfg.steps)
                    return render(
                        host, f"arm{fn}", ap, cfg.seed + 100 + i, f"video/arm{fn}",
                        cfg.arm_frames, arm_steps, key_names[i], key_names[i + 1],
                        **ak,
                    )
                return _run

            arm_jobs.append((host, f"arm{fn}", make_job()))

        for w in range((n_arms + 1) // 2):
            wave = arm_jobs[w * 2 : w * 2 + 2]
            print(f"  -- wave {w + 1}: {[lab for _, lab, _ in wave]} --", flush=True)
            all_arms += run_parallel([fn for _, _, fn in wave])
        for i, p in enumerate(all_arms):
            shutil.copy2(p, cfg.out_dir / f"arm{i + 1}.mp4")

    phase1 = time.time() - t1
    print(f"  phase1 wall {phase1:.0f}s", flush=True)

    # --- Phase 2: stitch (hardcut + optional xfade for seam jitter) ---
    mode2 = (
        f"xfade {cfg.xfade_s:.2f}s ({cfg.xfade_transition})"
        if cfg.xfade_s > 0
        else "hard-cut only"
    )
    print(f"\n=== PHASE 2: stitch — {mode2} ===", flush=True)
    t2 = time.time()
    final = cfg.out_dir / cfg.final_name
    hardcut_alias = None
    if cfg.xfade_s > 0:
        hardcut_alias = final.with_name(final.stem + "_hardcut" + final.suffix)
    stitch_arms(
        all_arms,
        final,
        cfg.work_dir,
        xfade_s=cfg.xfade_s,
        xfade_transition=cfg.xfade_transition,
        fps=24,
        also_hardcut=hardcut_alias,
    )
    phase2 = time.time() - t2
    print(f"  phase2 wall {phase2:.0f}s", flush=True)

    # --- Phase 3: final-only RealESRGAN (optional) ---
    phase3 = 0.0
    native_path: Path | None = None
    if cfg.final_upscale:
        # Resolve host: worker (.3) default — ESRGAN off DS4 head
        _fh = (cfg.final_upscale_host or "worker").strip().lower()
        if _fh in ("", "worker", "work", ".3", "3"):
            up_host = cfg.worker
        elif _fh in ("head", ".2", "2"):
            up_host = cfg.head
        else:
            up_host = cfg.final_upscale_host  # explicit ip:port
        print(
            f"\n=== PHASE 3: final-only upscale ({cfg.final_upscale}) on {up_host} ===",
            flush=True,
        )
        t3 = time.time()
        native_path = final.with_name(final.stem + "_native" + final.suffix)
        shutil.copy2(final, native_path)
        up_dest = cfg.work_dir / "final_upscaled.mp4"
        try:
            final_upscale_video(
                up_host,
                native_path,
                up_dest,
                model=cfg.final_upscale,
                work=cfg.work_dir,
                label="final_upscale",
                prefix="video/final_upscale",
            )
            shutil.copy2(up_dest, final)
            print(
                f"  delivered upscaled → {final}\n"
                f"  native kept → {native_path}",
                flush=True,
            )
        except Exception as e:
            print(
                f"  [warn] final upscale failed ({e}); keeping native hard-cut as {final}",
                flush=True,
            )
            # final still has native content (we copied native aside first)
            if not final.is_file() and native_path.is_file():
                shutil.copy2(native_path, final)
        phase3 = time.time() - t3
        print(f"  phase3 wall {phase3:.0f}s", flush=True)
    else:
        print("\n=== PHASE 3: skipped (H3_FINAL_UPSCALE=0) ===", flush=True)

    total = time.time() - t_all
    try:
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(final)],
            text=True,
        ).strip())
    except Exception:
        dur = -1.0

    timing = (
        f"mode=FLF-MULTISHOT\n"
        f"total_wall_s={total:.1f}\n"
        f"phase0_keys_s={phase0:.1f}\n"
        f"phase1_parallel_arms_s={phase1:.1f}\n"
        f"phase2_stitch_s={phase2:.1f}\n"
        f"phase3_final_upscale_s={phase3:.1f}\n"
        f"keys={n_keys} arms={n_arms}\n"
        f"key_mode={cfg.key_mode} natural_skin={cfg.natural_skin}\n"
        f"spectrum={cfg.spectrum} per_arm_upscale={cfg.upscale}\n"
        f"final_upscale={cfg.final_upscale or '0'}\n"
        f"xfade_s={cfg.xfade_s} xfade_transition={cfg.xfade_transition}\n"
        f"turbo={cfg.turbo} turbo_lora={cfg.turbo_lora if cfg.turbo else ''} "
        f"steps={cfg.steps} kf_steps={cfg.kf_steps}\n"
        f"i0_ref={cfg.i0_ref or ''}\n"
        f"hardcut=True\n"
        f"duration_s={dur:.2f}\n"
        f"native_path={native_path or ''}\n"
        f"note=prev last frame == next first frame (shared key PNG); "
        f"final ESRGAN after stitch only\n"
        f"credit=tonyd2wild factory + Hermes FLF + larryvrh/QrusherZA H3 Turbo\n"
    )
    (cfg.out_dir / "TIMING.txt").write_text(timing)
    print(f"\nDone in {total:.0f}s wall (~{total / 60:.1f} min)  duration={dur:.2f}s", flush=True)
    print(f"  {final}", flush=True)
    if native_path and native_path.is_file():
        print(f"  native: {native_path}", flush=True)
    print(f"  keys: {cfg.out_dir}/key_K*.png  arms: arm*.mp4", flush=True)
    return final


# ---------------------------------------------------------------------------
# Default CLI story: HP → dragon ~10s (2 arms) using FLF multishot
# ---------------------------------------------------------------------------
def default_hp_dragon_cfg() -> MultishotConfig:
    look = """integrated_multimodal_description: Photorealistic live-action cinema, 8K IMAX detail,
natural anamorphic lens, 24fps, 180° shutter. Cinematography like Alfonso Cuarón x Roger Deakins.
Practical light only: grey Highland daylight through tall Gothic stone windows, warm floating
candles, cool stone bounce, soft volumetric dust. No cartoon, no anime, no text, no watermark.

Identity lock: same teen wizard when human — messy black hair, round wire spectacles, lightning
scar, black robe, red-and-gold Gryffindor scarf. Same emerald-and-obsidian Western dragon scale
pattern, horn shape, body proportions whenever the dragon appears."""

    keys = [
        """KEYFRAME / living portrait (minimal motion): teenage wizard alone in Hogwarts-like
great hall, medium shot center frame. Hands with golden sparks under the skin; quiet fear and
wonder; spectacles on; scar visible; REAL skin pores and fabric weave. NO dragon in frame yet.""",
        """KEYFRAME still-energy: fully transformed mid-sized Western dragon fills the same hall,
wings half-unfurled, head toward tall open Gothic window, emerald-obsidian scales with real scale
micro-detail (not plastic), coiled to leap.""",
        """KEYFRAME living aerial still: same dragon banks in hover over Hogwarts-like castle —
turrets, lake, misty Highlands. Wings fully extended, correct membrane stretch.""",
    ]
    arms = [
        """ONE continuous take, no cuts. FIRST FRAME = human wizard key. LAST FRAME = dragon at window key.
[0–1.5s] Boy, golden sparks, robe lifts, candles gutter — real skin pores, no plastic.
[1.5–3.5s] Visceral transform: spine, scales, snout, wings with weight and anatomy.
[3.5–5.2s] Fully formed dragon fills hall, head to open window.
overall_soundscape: fireplace, morphing flesh/scale, dragon inhale. No music. No dialogue.""",
        """ONE continuous take. FIRST FRAME = dragon at window. LAST FRAME = dragon over castle.
[0–1.5s] Coils and launches through Gothic window.
[1.5–3.5s] Exterior bank into hover over roofs and lake.
[3.5–5.2s] Hero aerial hold circling keep.
overall_soundscape: wind, wing beats, distant water. No music. No dialogue.""",
    ]
    return MultishotConfig(
        key_prompts=keys,
        arm_prompts=arms,
        look=look,
        natural_skin=True,
        out_dir=Path(os.environ.get("OUT_DIR", str(Path.home() / "Videos" / "hp_dragon_flf"))),
        work_dir=Path(os.environ.get("WORK_DIR", "/tmp/hp_dragon_flf")),
        final_name="harry_potter_dragon_flf_10s.mp4",
        i0_ref=os.environ.get("H3_I0_REF", "").strip() or None,
        key_mode=os.environ.get("H3_KEY_MODE", "auto"),
    )


def main():
    cfg = default_hp_dragon_cfg()
    run_multishot(cfg)


if __name__ == "__main__":
    main()
