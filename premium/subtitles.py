"""Premium subtitles: 1920x1080 ASS with clean word-highlight karaoke.

Reuses the repo's faster-whisper transcription (subtitles.transcribe) so the
heavy model loads once. Only the ASS styling differs from the stickfigure
path: bigger font, DejaVu Sans Bold, bottom margin tuned for the gradient
band, white fill + soft shadow (no heavy outline — cinematic, not cartoon).
"""
import os
from subtitles import transcribe


def _fmt(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def to_ass_1080(segments: list[dict], out_path: str,
                font_size: int = 58, font_name: str = "DejaVu Sans Bold",
                margin_v: int = 72) -> str:
    """Write a 1920x1080 ASS with word-by-word karaoke highlight (4 words/line)."""
    header = f"""[Script Info]
Title: StickVerse Premium
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H00B0B0B0,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,2,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    chunk_size = 4
    for seg in segments:
        if not seg["words"]:
            continue
        for i in range(0, len(seg["words"]), chunk_size):
            chunk = seg["words"][i:i + chunk_size]
            start = chunk[0]["start"]
            end = chunk[-1]["end"]
            parts = []
            for w in chunk:
                dur = max(int((w["end"] - w["start"]) * 100), 1)
                parts.append(f"{{\\k{dur}}}{w['word']}")
            text = " ".join(parts)
            lines.append(
                f"Dialogue: 0,{_fmt(start)},{_fmt(end)},Default,,0,0,0,,{text}"
            )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(lines))
        f.write("\n")
    print(f"[subtitles] wrote {len(lines)} lines -> {out_path}")
    return out_path


def transcribe_and_ass(audio_path: str, out_path: str) -> str:
    """Transcribe narration with whisper + write a 1080p ASS. Resilient:
    if whisper fails (model download, etc.), returns None so the pipeline can
    ship the video without burned subtitles rather than crash."""
    try:
        segments = transcribe(audio_path)
        if not segments:
            print("[subtitles] whisper returned no segments — skipping subtitles")
            return None
        return to_ass_1080(segments, out_path)
    except Exception as e:
        print(f"[subtitles] WARNING: transcription failed ({e}) — shipping without subtitles")
        return None
