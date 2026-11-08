"""Generate TTS narration per scene using Edge-TTS (free, no API key needed).

Edge-TTS provides high-quality Microsoft Azure voices. We use en-US-GuyNeural
which is the classic deep male motivation voice.

Known issue: Edge-TTS sometimes raises NoAudioReceived when text is too long
or contains certain characters. We retry with chunking + sentence-splitting.
"""
import os
import re
import asyncio
import subprocess
import edge_tts
import config


def _split_text(text: str, max_chars: int = 250) -> list[str]:
    """Split text into chunks under max_chars, preferring sentence boundaries.

    Edge-TTS sometimes chokes on long inputs. We split on sentence-end punctuation
    first, then on commas, then hard-split if needed.
    """
    if len(text) <= max_chars:
        return [text]

    # Try sentence split first
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = ""
    for s in sentences:
        if not s:
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip() if current else s
        else:
            if current:
                chunks.append(current)
            # If a single sentence is too long, hard-split it
            while len(s) > max_chars:
                # try to split at a comma or space near the limit
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


async def _synth_chunk(text: str, out_path: str) -> bool:
    """Synthesize one chunk. Returns True on success, False on failure."""
    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice=config.TTS_VOICE,
            rate=config.TTS_RATE,
        )
        await communicate.save(out_path)
        # Verify the file is non-empty
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            return True
        return False
    except Exception as e:
        print(f"  [tts] chunk synth failed: {type(e).__name__}: {e}")
        # Cleanup partial file
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        return False


async def _synth_with_retry(text: str, out_path: str, max_attempts: int = 4) -> str:
    """Synthesize text, retrying with smaller chunks on failure."""
    # First attempt: full text
    for attempt in range(max_attempts):
        if await _synth_chunk(text, out_path):
            return out_path
        # Wait briefly and retry
        await asyncio.sleep(2 * (attempt + 1))

    # Full text failed — split into chunks
    print(f"  [tts] full-text synth failed; splitting into chunks")
    chunks = _split_text(text, max_chars=250 if len(text) > 500 else 150)
    if len(chunks) == 1:
        # Already small enough — try once more with the smaller limit
        chunks = _split_text(text, max_chars=100)

    chunk_paths = []
    for i, chunk in enumerate(chunks):
        chunk_path = f"{out_path}.chunk{i:03d}.mp3"
        success = False
        for attempt in range(max_attempts):
            if await _synth_chunk(chunk, chunk_path):
                chunk_paths.append(chunk_path)
                success = True
                break
            await asyncio.sleep(2 * (attempt + 1))
        if not success:
            raise RuntimeError(f"TTS failed on chunk {i}: {chunk[:100]}")

    # Concatenate chunks into final file
    list_file = f"{out_path}.chunks.txt"
    with open(list_file, "w") as f:
        for p in chunk_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out_path],
        check=True, capture_output=True,
    )
    # Cleanup
    try:
        os.remove(list_file)
        for p in chunk_paths:
            os.remove(p)
    except Exception:
        pass

    return out_path


def synth_scene(text: str, out_path: str) -> str:
    """Synchronous wrapper. Generates MP3 narration for one scene.

    Handles Edge-TTS flakiness with retries + automatic chunking for long inputs.
    """
    asyncio.run(_synth_with_retry(text, out_path))
    return out_path


def get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
    ).decode().strip()
    return float(out)


def concat_audio(audio_paths: list[str], out_path: str) -> str:
    """Concatenate scene audios into one continuous narration MP3."""
    list_file = out_path + ".txt"
    with open(list_file, "w") as f:
        for p in audio_paths:
            # ffmpeg concat demuxer requires absolute or properly escaped paths
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            out_path,
        ],
        check=True,
        capture_output=True,
    )
    os.remove(list_file)
    return out_path


if __name__ == "__main__":
    # smoke test
    os.makedirs("./output", exist_ok=True)
    synth_scene("Discipline is choosing what you want most over what you want now.", "./output/test_tts.mp3")
    print(f"duration: {get_audio_duration('./output/test_tts.mp3'):.2f}s")
