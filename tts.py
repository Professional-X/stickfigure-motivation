"""Generate TTS narration per scene using Edge-TTS (free, no API key needed).

Edge-TTS provides high-quality Microsoft Azure voices. We use en-US-GuyNeural
which is the classic deep male motivation voice.
"""
import os
import asyncio
import subprocess
import edge_tts
import config


async def _synth(text: str, out_path: str):
    communicate = edge_tts.Communicate(
        text=text,
        voice=config.TTS_VOICE,
        rate=config.TTS_RATE,
    )
    await communicate.save(out_path)


def synth_scene(text: str, out_path: str) -> str:
    """Synchronous wrapper. Generates MP3 narration for one scene."""
    asyncio.run(_synth(text, out_path))
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
