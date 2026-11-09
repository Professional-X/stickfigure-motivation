"""Compose final video with ffmpeg.

Pipeline:
1. For each scene: build an MP4 with STATIC still image + scene narration.
   (No Ken Burns zoom — viewers hated it.)
2. Concat all scene MP4s with 0.5s crossfade transitions.
3. Mix in background music at lower volume.
4. Burn in subtitles from ASS file.
5. Output: final.mp4 (1280x720, H.264 + AAC).
"""
import os
import subprocess
import config
from tts import get_audio_duration


def _run_ffmpeg(args: list[str], desc: str = ""):
    """Run ffmpeg, raise on failure with stderr captured."""
    if desc:
        print(f"[compose] {desc}")
    try:
        subprocess.run(
            ["ffmpeg", "-y", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[compose] ffmpeg failed: {e.stderr[-1500:]}")
        raise


def build_scene_clip(image_path: str, audio_path: str, duration: float, out_path: str):
    """Build a single scene MP4: STATIC still image (no zoom, no Ken Burns) + narration audio.

    The zoom/pan was making viewers dizzy and looked amateurish. Static frames
    with crossfade transitions look more professional and match the
    "presentation / quote card" aesthetic.
    """
    # Static image — just scale to fit + crop to 1280x720, no zoompan filter.
    static_filter = (
        f"scale={config.IMAGE_WIDTH}:{config.IMAGE_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={config.IMAGE_WIDTH}:{config.IMAGE_HEIGHT},"
        f"format=yuv420p"
    )

    _run_ffmpeg(
        [
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-filter_complex", f"[0:v]{static_filter}[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-tune", "stillimage",
            "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-shortest",
            out_path,
        ],
        desc=f"scene clip -> {os.path.basename(out_path)}"
    )


def concat_clips(clip_paths: list[str], out_path: str):
    """Concat scene clips with a 0.5s crossfade between each (smoother than hard cuts)."""
    if len(clip_paths) == 1:
        # Single clip — just copy
        _run_ffmpeg(["-i", clip_paths[0], "-c", "copy", out_path], desc="single clip")
        return

    # Build xfade chain: each transition is 0.5s, offset = sum of previous durations - 0.5s
    # First, probe durations
    durations = []
    for p in clip_paths:
        d = get_audio_duration(p)  # works for video files too (returns format duration)
        durations.append(d)

    # Build the filter_complex string
    # [0:v][1:v]xfade=transition=fade:duration=0.5:offset=D0-0.5[v01];
    # [v01][2:v]xfade=transition=fade:duration=0.5:offset=D0+D1-1.0[v012]; ...
    # Also do the same for audio.
    filter_parts = []
    prev_v = "[0:v]"
    prev_a = "[0:a]"
    cumulative = 0.0
    xf_duration = 0.5

    for i in range(1, len(clip_paths)):
        cumulative += durations[i - 1]
        offset = max(0, cumulative - xf_duration)
        out_v = f"[v{i}]"
        out_a = f"[a{i}]"
        filter_parts.append(
            f"{prev_v}[{i}:v]xfade=transition=fade:duration={xf_duration}:offset={offset}{out_v}"
        )
        filter_parts.append(
            f"{prev_a}[{i}:a]acrossfade=d={xf_duration}{out_a}"
        )
        prev_v = out_v
        prev_a = out_a

    filter_complex = ";".join(filter_parts)

    args = ["-y"]
    for p in clip_paths:
        args.extend(["-i", p])
    args.extend([
        "-filter_complex", filter_complex,
        "-map", prev_v,
        "-map", prev_a,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        out_path,
    ])

    _run_ffmpeg(args, desc=f"concat {len(clip_paths)} clips with crossfade")


def add_music_and_subtitles(
    video_path: str,
    music_path: str | None,
    subtitle_path: str,
    out_path: str,
):
    """Mix background music + burn in ASS subtitles."""
    if music_path:
        # Build filter: lower music volume, mix with narration audio, burn subs on video
        filter_complex = (
            f"[1:a]volume={config.BG_MUSIC_VOLUME_DB}dB,aloop=loop=-1:size=2e9[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a];"
            f"[0:v]ass={subtitle_path}[v]"
        )
        _run_ffmpeg(
            [
                "-i", video_path,
                "-i", music_path,
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                out_path,
            ],
            desc="add music + burn subtitles"
        )
    else:
        # No music — just burn subtitles
        _run_ffmpeg(
            [
                "-i", video_path,
                "-vf", f"ass={subtitle_path}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy",
                out_path,
            ],
            desc="burn subtitles (no music)"
        )


def compose_video(
    scenes: list[dict],
    music_path: str | None,
    subtitle_path: str,
    out_path: str,
) -> str:
    """Full composition pipeline. Returns path to final.mp4.

    Each scene in `scenes` must have:
      - image_path: str
      - audio_path: str
      - duration: float (seconds)
    """
    work_dir = os.path.dirname(out_path)
    clip_dir = os.path.join(work_dir, "clips")
    os.makedirs(clip_dir, exist_ok=True)

    # 1. Build per-scene clips
    clip_paths = []
    for i, scene in enumerate(scenes):
        clip_path = os.path.join(clip_dir, f"scene_{i:03d}.mp4")
        build_scene_clip(
            scene["image_path"],
            scene["audio_path"],
            scene["duration"],
            clip_path,
        )
        clip_paths.append(clip_path)

    # 2. Concat
    concat_mp4 = os.path.join(work_dir, "concat.mp4")
    concat_clips(clip_paths, concat_mp4)

    # 3. Add music + subtitles
    add_music_and_subtitles(concat_mp4, music_path, subtitle_path, out_path)

    # 4. Cleanup intermediates
    try:
        os.remove(concat_mp4)
        for c in clip_paths:
            os.remove(c)
        os.rmdir(clip_dir)
    except OSError:
        pass

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"[compose] final video: {out_path} ({size_mb:.1f} MB)")
    return out_path


if __name__ == "__main__":
    # manual test
    import json
    print("compose.py is invoked by pipeline.py — see that file for usage.")
