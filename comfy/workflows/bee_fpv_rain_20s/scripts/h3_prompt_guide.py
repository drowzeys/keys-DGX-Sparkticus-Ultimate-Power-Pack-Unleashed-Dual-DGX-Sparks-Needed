#!/usr/bin/env python3
"""MiniMax-H3 official video prompt builder (T2VA / I2VA / FL2VA / L2VA).

Follows:
https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md

Final shape:
  [optional mode instruction line]

  integrated_multimodal_description: [Shot 1] ...
  overall_soundscape: ...
  non_diegetic_music: ...
"""
from __future__ import annotations

from typing import Optional


def _dur_ss(seconds: float) -> str:
    """Format duration as S.SS (two decimal places) for FL2VA/L2VA headers."""
    return f"{float(seconds):.2f}"


def frames_to_seconds(length_frames: int, fps: float = 24.0) -> float:
    return length_frames / fps


def dialogue_block(
    spoken: str,
    *,
    speaker_id: str = "S1",
    speaker_desc: str = "the person",
    voice_desc: str = "a natural clear voice",
    lang: str = "English",
    offscreen: bool = False,
) -> str:
    """Official speaker + <d>[Lang] verbatim</d> dialogue chunk."""
    line = (spoken or "").strip()
    if not line:
        return ""
    # Preserve user text; strip wrapping quotes only
    if (line.startswith('"') and line.endswith('"')) or (line.startswith("'") and line.endswith("'")):
        line = line[1:-1]
    if offscreen:
        return (
            f"{speaker_desc} with {voice_desc} ({speaker_id}) says in an off-screen voiceover: "
            f"<d>[{lang}] {line}</d> while their lips remain completely closed."
        )
    return (
        f"{speaker_desc} with {voice_desc} ({speaker_id}) says: "
        f"<d>[{lang}] {line}</d>"
    )


def assemble(
    multimodal_body: str,
    *,
    overall_soundscape: str,
    non_diegetic_music: str = "N/A",
    mode: str = "t2va",
    duration_s: Optional[float] = None,
    last_shot_index: int = 1,
) -> str:
    """Build full prompt with optional I2VA/FL2VA/L2VA instruction header."""
    mode = (mode or "t2va").lower()
    header = ""
    if mode == "i2va":
        header = (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced.\n\n"
        )
    elif mode == "fl2va":
        if duration_s is None:
            raise ValueError("fl2va requires duration_s")
        ss = _dur_ss(duration_s)
        n = max(1, int(last_shot_index))
        header = (
            "How the reference pictures align with the target video — "
            "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot {n}) aligns with the {ss}-second mark of the target video.\n\n"
        )
    elif mode == "l2va":
        if duration_s is None:
            raise ValueError("l2va requires duration_s")
        ss = _dur_ss(duration_s)
        n = max(1, int(last_shot_index))
        header = (
            "How the reference pictures align with the target video — "
            f"<Picture 1> (from [Shot {n}]) aligns with the {ss}-second mark of the target video.\n\n"
        )
    elif mode != "t2va":
        raise ValueError(f"unknown mode {mode!r}; use t2va|i2va|fl2va|l2va")

    body = multimodal_body.strip()
    if not body.lower().startswith("integrated_multimodal_description:"):
        body = f"integrated_multimodal_description: {body}"

    sc = (overall_soundscape or "N/A").strip()
    if not sc.lower().startswith("overall_soundscape:"):
        sc = f"overall_soundscape: {sc}"

    mu = (non_diegetic_music or "N/A").strip()
    if not mu.lower().startswith("non_diegetic_music:"):
        mu = f"non_diegetic_music: {mu}"

    return f"{header}{body}\n\n{sc}\n\n{mu}\n"


def t2va_shot1(
    *,
    style: str,
    composition: str,
    action: str,
    overall_soundscape: str,
    non_diegetic_music: str = "N/A",
    dialogue: str = "",
    speaker_desc: str = "the person",
    voice_desc: str = "a natural clear voice",
    no_onscreen_text: bool = True,
) -> str:
    """T2VA single continuous shot."""
    no_text = " No on-screen text, captions, subtitles, or watermark." if no_onscreen_text else ""
    dlg = dialogue_block(dialogue, speaker_desc=speaker_desc, voice_desc=voice_desc)
    multi = (
        f"[Shot 1] {style.strip()}. {composition.strip()}. "
        f"{action.strip()}. {dlg}{no_text}"
    ).replace("  ", " ").strip()
    return assemble(multi, overall_soundscape=overall_soundscape, non_diegetic_music=non_diegetic_music, mode="t2va")


def i2va_shot1(
    *,
    style: str,
    first_frame_anchor: str,
    action: str,
    overall_soundscape: str,
    non_diegetic_music: str = "N/A",
    dialogue: str = "",
    speaker_desc: str = "the person shown in <Picture 1>",
    voice_desc: str = "a natural clear voice",
    camera: str = "The camera holds a static shot with small amplitude motion only when needed.",
    no_onscreen_text: bool = True,
) -> str:
    """I2VA: develop forward from Picture 1 (first frame)."""
    no_text = " No on-screen text, captions, subtitles, or watermark." if no_onscreen_text else ""
    dlg = dialogue_block(dialogue, speaker_desc=speaker_desc, voice_desc=voice_desc)
    multi = (
        f"[Shot 1] {style.strip()}. {first_frame_anchor.strip()} "
        f"{camera.strip()} {action.strip()}. {dlg}{no_text}"
    ).replace("  ", " ").strip()
    return assemble(
        multi,
        overall_soundscape=overall_soundscape,
        non_diegetic_music=non_diegetic_music,
        mode="i2va",
    )


def fl2va_shot1(
    *,
    style: str,
    path_description: str,
    duration_s: float,
    overall_soundscape: str,
    non_diegetic_music: str = "N/A",
    dialogue: str = "",
    speaker_desc: str = "the subject",
    voice_desc: str = "a natural clear voice",
    no_onscreen_text: bool = True,
) -> str:
    """FL2VA single-shot path from Picture 1 (0s) to Picture 2 (duration)."""
    no_text = " No on-screen text, captions, subtitles, or watermark." if no_onscreen_text else ""
    dlg = dialogue_block(dialogue, speaker_desc=speaker_desc, voice_desc=voice_desc)
    multi = (
        f"[Shot 1] {style.strip()}. {path_description.strip()}. {dlg}{no_text}"
    ).replace("  ", " ").strip()
    return assemble(
        multi,
        overall_soundscape=overall_soundscape,
        non_diegetic_music=non_diegetic_music,
        mode="fl2va",
        duration_s=duration_s,
        last_shot_index=1,
    )


def talking_span_i2va(
    *,
    style: str,
    nat_skin: str,
    wardrobe: str,
    setting: str,
    motion: str,
    line: str,
    length_frames: int,
    fps: float = 24.0,
    pronoun: str = "she",
    non_diegetic_music: str = "N/A",
) -> str:
    """Guide-compliant prompt for face-locked talking spans (ref2va / I2VA-like)."""
    poss = {"she": "her", "he": "his", "they": "their"}.get(pronoun, "her")
    who = {"she": "young woman", "he": "young man", "they": "person"}.get(pronoun, "young woman")
    speaker = f"the {who} shown in <Picture 1>"
    voice = f"a soft natural {poss} speaking voice"
    anchor = (
        f"Live-action, cinematic, medium close-up of {speaker}, preserving exact face, identity, "
        f"and {wardrobe or 'clothing'} from <Picture 1>. {nat_skin} {setting}"
    )
    action = (
        f"{motion or 'slow subtle motion'}, looking directly at the camera with natural lip-sync. "
        f"Keep identity, wardrobe, and scene anchors consistent with <Picture 1>."
    )
    sound = (
        f"Quiet natural room tone and soft fabric movement. Light breath and {poss} natural speaking voice "
        f"as diegetic dialogue in the multimodal description."
    )
    # ref2va uses Picture 1 as identity; I2VA header still helps first-frame locking when I2V
    return i2va_shot1(
        style=style if style.lower().startswith("live") or "cinematic" in style.lower() else f"Live-action, cinematic, {style}",
        first_frame_anchor=anchor,
        action=action,
        overall_soundscape=sound,
        non_diegetic_music=non_diegetic_music,
        dialogue=line or "",
        speaker_desc=speaker,
        voice_desc=voice,
        camera="The camera holds a mostly static handheld shot with small amplitude at slow speed.",
        no_onscreen_text=True,
    )


def fl2va_span(
    *,
    style: str,
    lighting: str,
    tone: str,
    motion: str,
    audio_bed: str,
    extra_audio: str = "",
    say: str = "",
    length_frames: int,
    fps: float = 24.0,
    identity_note: str = "",
) -> str:
    """Guide-compliant FL2VA span between two keyframe pictures."""
    dur = frames_to_seconds(length_frames, fps)
    path = (
        f"Live-action, cinematic, begin in the pose, framing, and appearance of Picture 1 "
        f"and continuously reach Picture 2 by the end of the shot. "
        f"{identity_note} Lighting: {lighting}. Tone: {tone}. "
        f"Observable intermediate motion: {motion}. "
        f"The camera follows the action with small amplitude at slow speed when needed, "
        f"preferring a single continuous shot without unnecessary cuts."
    )
    sound = f"{audio_bed} {extra_audio}".strip()
    return fl2va_shot1(
        style=style if "cinematic" in style.lower() or "live" in style.lower() else f"Live-action, cinematic, {style}",
        path_description=path,
        duration_s=dur,
        overall_soundscape=sound or "Natural ambient room tone and soft physical action sounds.",
        non_diegetic_music="N/A",
        dialogue=say or "",
        speaker_desc="the subject",
        voice_desc="a natural clear voice",
    )


def kf_t2va_or_i2va(
    *,
    style: str,
    lighting: str,
    tone: str,
    kf_prompt: str,
    audio_bed: str,
    has_first_frame: bool = False,
) -> str:
    """Keyframe still-as-video (short length): T2VA or I2VA if rooted in a picture."""
    body = (
        f"[Shot 1] Live-action, cinematic, {style}. {kf_prompt}. "
        f"Lighting: {lighting}. Tone: {tone}. "
        f"The camera holds a static shot. No on-screen text or watermark."
    )
    if has_first_frame:
        return assemble(
            f"integrated_multimodal_description: {body} Preserve appearance and layout from <Picture 1>.",
            overall_soundscape=audio_bed or "Quiet ambient room tone.",
            non_diegetic_music="N/A",
            mode="i2va",
        )
    return assemble(
        f"integrated_multimodal_description: {body}",
        overall_soundscape=audio_bed or "Quiet ambient room tone.",
        non_diegetic_music="N/A",
        mode="t2va",
    )


def jc_continuous_i2va_powerpack(
    *,
    width: int = 576,
    height: int = 768,
    length_frames: int = 719,
    fps: float = 24.0,
) -> str:
    """Official-guide continuous JC Power Pack promo (~30s I2VA)."""
    dialogue = (
        "I want you to get keys DGX Sparkticus Utimate Power Pack Unleashed — dual DGX Sparks needed — "
        "running both DeepSeek Version Four Flash and MiniMax H3 abliterated with all the speed upgrades, "
        "multi-shot, seamless transition, quality dense sampling — because that is what I want. "
        "And… is this what you want in return?"
    )
    anchor = (
        f"medium close-up of the young woman in <Picture 1> in a closed department-store aisle at night, "
        f"soft fluorescent light and red-and-white logo bokeh. Preserve her luminous green eyes, "
        f"dark chestnut wavy hair, fair skin with real pores, white ribbed tank top, composition, and aisle layout. "
        f"Portrait framing about {width}x{height}."
    )
    action = (
        "She holds the camera with green eyes, turns for a look-back smile, then faces the lens again. "
        "Slow languid motion continues as she speaks with natural lip-sync. "
        "After the line she blows a soft kiss toward the camera and holds a warm smile."
    )
    return i2va_shot1(
        style="Live-action, cinematic, 35mm film grain, natural anamorphic lens, 24fps, 180 degree shutter",
        first_frame_anchor=anchor,
        action=action,
        overall_soundscape=(
            "Continuous quiet fluorescent store hum and soft fabric movement. "
            "Light breath and a soft kiss sound near the end."
        ),
        non_diegetic_music="N/A",
        dialogue=dialogue,
        speaker_desc="the young woman with a soft American voice shown in <Picture 1>",
        voice_desc="a soft natural American speaking voice",
        camera="The camera holds a mostly static handheld shot, then pushes in with small amplitude at slow speed.",
        no_onscreen_text=True,
    )
