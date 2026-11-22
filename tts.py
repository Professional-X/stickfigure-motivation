"""Generate TTS narration per scene using Edge-TTS (free, no API key).

Human-cadence engine (the anti-"AI-slop" fix):
- Splits each scene into SENTENCES and synthesizes each separately with a
  rate/pitch chosen for its rhythm class:
    punch      (<=5 words)   : +2% rate, +2Hz pitch  -> snappy, sharp
    normal     (6-17 words)  : -8% rate              -> gravitas (baseline)
    reflective (>=18 words)  : -14% rate, -2Hz pitch -> slow, heavy
- Inserts a SILENCE gap after every sentence (short normally, longer after a
  punch line, longest at the scene tail) so the delivery breathes instead of
  running as one flat monotone wall.
- Returns per-sentence start/end timings so premium/compose.py can cut the
  visuals on sentence boundaries (beat-synced editing -> fast, intentional
  cuts instead of one slow zoom per 30s scene).

Edge-TTS sometimes raises NoAudioReceived on long inputs; per-sentence synth
sidesteps that (each chunk is short) and we still retry per sentence, with a
chunked fallback for any stubborn sentence.
"""
import os
import re
import shutil
import asyncio
import subprocess
import time

import edge_tts

import config


# ----- rhythm classification (in words) -------------------------------------
PUNCH_MAX_WORDS = 5
REFLECTIVE_MIN_WORDS = 18

# inter-sentence silence (seconds)
GAP_NORMAL = 0.12
GAP_PUNCH = 0.30
GAP_REFLECTIVE = 0.20
GAP_SCENE_TAIL = 0.45  # extra breathing room at the end of each scene


def _classify(sentence: str) -> str:
    n = len(sentence.split())
    if n <= PUNCH_MAX_WORDS:
        return "punch"
    if n >= REFLECTIVE_MIN_WORDS:
        return "reflective"
    return "normal"


def _prosody(cls: str) -> tuple[str, str]:
    """(rate, pitch) for edge-tts.Communicate, by rhythm class."""
    if cls == "punch":
        return ("+2%", "+2Hz")
    if cls == "reflective":
        return ("-14%", "-2Hz")
    return ("-8%", "+0Hz")  # normal


def _gap_for(cls: str, is_last: bool) -> float:
    if is_last:
        return GAP_SCENE_TAIL
    if cls == "punch":
        return GAP_PUNCH
    if cls == "reflective":
        return GAP_REFLECTIVE
    return GAP_NORMAL


def _split_sentences(text: str) -> list[str]:
    """Split narration into deliverable sentences.

    Primary split on sentence-end punctuation, then further split long
    sentences on semicolons + em-dashes so motivation cadence reads as short
    bursts (each gets its own prosody + a beat of silence after).
    """
    t = text.strip()
    sents = re.split(r"(?<=[.!?])\s+", t)
    out = []
    for s in sents:
        s = s.strip()
        if not s:
            continue
        sub = re.split(r"\s*;\s*|\s+—\s+", s)
        out.extend(x.strip() for x in sub if x.strip())
    return out or [t]


# ----- silence + probing -----------------------------------------------------
def _probe_audio(path: str) -> tuple[float, int, int]:
    """Return (duration_s, sample_rate, channels) for an audio file."""
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path]
    ).decode().strip())
    info = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels",
         "-of", "default=noprint_wrappers=1:nokey=1", path]
    ).decode().strip().splitlines()
    sr = int(info[0]) if len(info) > 0 and info[0] else 24000
    ch = int(info[1]) if len(info) > 1 and info[1] else 1
    return dur, sr, ch


def _silence_clip(duration: float, sample_rate: int, channels: int, out_path: str):
    """Render a silent mp3 matching the sentence clips' codec params (so the
    concat demuxer can -c copy without re-encoding)."""
    cl = "mono" if channels == 1 else "stereo"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"anullsrc=r={sample_rate}:cl={cl}",
         "-t", f"{duration:.3f}",
         "-c:a", "libmp3lame", "-b:a", "96k", out_path],
        check=True, capture_output=True,
    )


# ----- chunked fallback (kept from v1 for stubborn sentences) ---------------
def _split_text(text: str, max_chars: int = 250) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, current = [], ""
    for s in sentences:
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip() if current else s
        else:
            if current:
                chunks.append(current)
            while len(s) > max_chars:
                split_at = max_chars
                for sep in [", ", " "]:
                    last_sep = s.rfind(sep, 0, max_chars)
                    if last_sep > max_chars // 2:
                        split_at = last_sep + len(sep)
                        break
                chunks.append(s[:split_at].strip())
                s = s[split_at:].strip()
            current = s
    if current:
        chunks.append(current)
    return chunks


async def _synth_chunk(text: str, voice: str, rate: str, pitch: str, out_path: str) -> bool:
    try:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
        await communicate.save(out_path)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 100
    except Exception as e:
        print(f"  [tts] synth failed: {type(e).__name__}: {e}")
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        return False


async def _synth_sentence_robust(sent: str, voice: str, rate: str, pitch: str,
                                 out_path: str) -> bool:
    """Synth one sentence with retries; on persistent failure, chunk it."""
    for attempt in range(4):
        if await _synth_chunk(sent, voice, rate, pitch, out_path):
            return True
        await asyncio.sleep(1.5 * (attempt + 1))
    # chunked fallback at the same prosody
    chunks = _split_text(sent, max_chars=120)
    if len(chunks) <= 1:
        return False
    parts = []
    for j, ck in enumerate(chunks):
        cp = f"{out_path}.c{j:02d}.mp3"
        for attempt in range(3):
            if await _synth_chunk(ck, voice, rate, pitch, cp):
                parts.append(cp)
                break
            await asyncio.sleep(1.5 * (attempt + 1))
        else:
            return False
    list_file = out_path + ".clist.txt"
    with open(list_file, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", out_path],
        check=True, capture_output=True,
    )
    for p in parts:
        try:
            os.remove(p)
        except OSError:
            pass
    os.remove(list_file)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 100


# ----- the timed scene engine ------------------------------------------------
async def _synth_scene_timed_async(text: str, out_path: str) -> list[dict]:
    sentences = _split_sentences(text)
    voice = config.TTS_VOICE
    tmp_dir = out_path + "_parts"
    os.makedirs(tmp_dir, exist_ok=True)

    parts = []          # ordered mp3 paths (sentences + silences interleaved)
    timings = []
    t_cursor = 0.0
    sample_rate, channels = 24000, 1  # set after first sentence probes

    for i, sent in enumerate(sentences):
        cls = _classify(sent)
        rate, pitch = _prosody(cls)
        sp = os.path.join(tmp_dir, f"s{i:03d}.mp3")
        ok = await _synth_sentence_robust(sent, voice, rate, pitch, sp)
        if not ok:
            # last resort: plain default-rate synth of the whole sentence
            print(f"  [tts] s{i} prosody failed; default-rate fallback")
            ok = await _synth_sentence_robust(sent, voice, "-8%", "+0Hz", sp)
        if not ok:
            raise RuntimeError(f"TTS failed on sentence {i}: {sent[:80]}")

        sdur, sr, ch = _probe_audio(sp)
        if i == 0:
            sample_rate, channels = sr, ch  # match silence to edge-tts output

        timings.append({"text": sent, "cls": cls,
                        "start": round(t_cursor, 3),
                        "end": round(t_cursor + sdur, 3)})
        t_cursor += sdur
        parts.append(sp)

        is_last = (i == len(sentences) - 1)
        gap = _gap_for(cls, is_last)
        if gap > 0:
            gp = os.path.join(tmp_dir, f"g{i:03d}.mp3")
            _silence_clip(gap, sample_rate, channels, gp)
            parts.append(gp)
            t_cursor += gap

    # concat all parts into the final scene audio
    list_file = out_path + ".list.txt"
    with open(list_file, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", out_path],
        check=True, capture_output=True,
    )
    try:
        os.remove(list_file)
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except OSError:
        pass

    npunch = sum(1 for t in timings if t["cls"] == "punch")
    nrefl = sum(1 for t in timings if t["cls"] == "reflective")
    print(f"  [tts] scene: {len(sentences)} sentences, {t_cursor:.1f}s "
          f"({npunch} punch, {len(sentences)-npunch-nrefl} normal, {nrefl} reflective)")
    return timings


def synth_scene_timed(text: str, out_path: str) -> list[dict]:
    """Sync wrapper. Returns per-sentence timings [{text, cls, start, end}]."""
    return asyncio.run(_synth_scene_timed_async(text, out_path))


def synth_scene(text: str, out_path: str) -> str:
    """Backwards-compatible wrapper (old pipeline.py + smoke test).
    Synthesizes with the human-cadence engine; returns the output path."""
    synth_scene_timed(text, out_path)
    return out_path


def get_audio_duration(path: str) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path]
    ).decode().strip()
    return float(out)


def concat_audio(audio_paths: list[str], out_path: str) -> str:
    """Concatenate scene audios into one continuous narration MP3."""
    list_file = out_path + ".txt"
    with open(list_file, "w") as f:
        for p in audio_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", out_path],
        check=True, capture_output=True,
    )
    os.remove(list_file)
    return out_path


def process_narration(in_path: str, out_path: str) -> str:
    """Soften + humanize the full narration with a gentle ffmpeg chain.

    The raw Edge-TTS output is clean but a touch metallic and dynamically flat
    in a shouty way. This pass:
      - highpass 80Hz        : cut low rumble / desk hum
      - acompressor          : gentle 3:1 compression evens out the punchy peaks
                               so the delivery breathes instead of pushing forward
      - afftdn (light)       : tames the Edge-TTS metallic edge without going underwater
      - highshelf -3dB@5.5k  : de-ess / reduce harsh sibilance
      - lowshelf +2dB@160    : add a touch of chest warmth
      - lowpass 14k          : soften the very top end (less "digital")
      - dynaudnorm           : smooth, transparent loudness normalization (not
                               the aggressive one-pass loudnorm that pumps)

    Falls back to a straight copy if ffmpeg filtering fails, so the pipeline
    never breaks on audio post-processing.
    """
    fg = (
        "highpass=f=80,"
        "acompressor=threshold=-18dB:ratio=2.5:attack=25:release=300:knee=3:makeup=1,"
        "afftdn=nr=6:nf=-25,"
        "highshelf=f=5500:g=-3dB,"
        "lowshelf=f=160:g=+2dB,"
        "lowpass=f=14000,"
        "volume=5dB"
    )
    cmd = ["ffmpeg", "-y", "-i", in_path, "-af", fg,
           "-c:a", "libmp3lame", "-b:a", "192k", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) < 100:
        print(f"  [tts] narration post-process failed (rc={r.returncode}); using raw narration")
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        shutil.copyfile(in_path, out_path)
        return out_path
    print(f"  [tts] narration post-processed (softer/warmer/compressed) -> {os.path.basename(out_path)}")
    return out_path


if __name__ == "__main__":
    os.makedirs("./output", exist_ok=True)
    t0 = time.time()
    timings = synth_scene_timed(
        "You are not tired. You are weak. An easier life does not build a "
        "stronger person. It builds a quieter one, and quiet is not the same "
        "as strong. The Stoics understood this two thousand years ago.",
        "./output/test_tts.mp3")
    print(f"duration: {get_audio_duration('./output/test_tts.mp3'):.2f}s "
          f"({time.time()-t0:.1f}s to synth)")
    for t in timings:
        print(f"  [{t['start']:5.2f}-{t['end']:5.2f}] {t['cls']:10s} {t['text'][:60]}")
