"""Transcribe narration with faster-whisper and generate karaoke-style ASS subtitles.

Whisper runs locally on CPU in GitHub Actions — no OpenAI API key needed.
Output is an .ass file with \\k karaoke tags so ffmpeg burns word-by-word highlights.
"""
import os
import faster_whisper
import config


def transcribe(audio_path: str) -> list[dict]:
    """Returns list of {start, end, text, words: [{word, start, end}]}."""
    print(f"[subtitles] loading whisper model (base.en, CPU)...")
    model = faster_whisper.WhisperModel(
        "base.en",
        device="cpu",
        compute_type="int8",
    )
    print(f"[subtitles] transcribing {audio_path}...")
    segments, _ = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
        vad_filter=True,
    )
    out = []
    for seg in segments:
        words = [
            {"word": w.word.strip(), "start": w.start, "end": w.end}
            for w in (seg.words or [])
            if w.word.strip()
        ]
        if words:
            out.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
                "words": words,
            })
    print(f"[subtitles] {len(out)} segments, {sum(len(s['words']) for s in out)} words")
    return out


def _fmt_time(t: float) -> str:
    """ASS timestamp: H:MM:SS.cc"""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def to_ass(
    segments: list[dict],
    out_path: str,
    font_size: int = 48,
    font_name: str = "Impact",
) -> str:
    """Write an ASS file with word-by-word karaoke highlight.

    Each Dialogue line is a small chunk (4 words). \\k durations drive the highlight.
    PrimaryColour = white (highlighted/active), SecondaryColour = gray (upcoming).
    """
    header = f"""[Script Info]
Title: Stick Figure Motivation
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H00808080,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,80,80,80,1

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
            # build karaoke line: {\kNN}word for each word
            parts = []
            for w in chunk:
                dur = max(int((w["end"] - w["start"]) * 100), 1)  # centiseconds
                parts.append(f"{{\\k{dur}}}{w['word']}")
            text = " ".join(parts)
            lines.append(
                f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},"
                f"Default,,0,0,0,,{text}"
            )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(lines))
        f.write("\n")
    print(f"[subtitles] wrote {len(lines)} subtitle lines -> {out_path}")
    return out_path


if __name__ == "__main__":
    # smoke test on any mp3 in output/
    import sys
    if len(sys.argv) < 2:
        print("usage: python subtitles.py <audio.mp3>")
        sys.exit(1)
    segs = transcribe(sys.argv[1])
    to_ass(segs, "./output/test.ass")
