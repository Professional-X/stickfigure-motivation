"""Cinematic composer for the premium pipeline.

Stages (each a separate ffmpeg pass — robust + easy to debug):
  1. render_scene()   — per scene: cover-crop to 1920x1080, slow Ken Burns
                        zoom, teal-orange color grade, vignette, 0.3s fade-in.
                        Short source clips are looped to fill the scene.
  2. concat_scenes()  — lossless concat of scene clips -> visual.mp4 (no audio)
  3. make_gradient()  — bottom gradient PNG for subtitle legibility (Pillow)
  4. mix_audio()      — narration + music ducked via sidechaincompress
  5. burn_final()     — overlay gradient + burn ASS subtitles onto visual,
                        mux ducked audio -> final.mp4 (H.264/AAC, 1920x1080)

All footage is free Mixkit stock (no attribution). Music is free Incompetech
CC-BY (attribution handled in metadata). Narration is Edge-TTS (free).
"""
import os
import subprocess

from . import scripts as S


# ----- ffmpeg helper -------------------------------------------------------
def _run(cmd: list[str], desc: str) -> None:
    print(f"[compose] {desc}")
    # show stderr tail on failure for debugging
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        tail = "\n".join(res.stderr.splitlines()[-20:])
        raise RuntimeError(f"ffmpeg failed ({desc}):\n{tail}")


# ----- Stage 1: per-scene render -------------------------------------------
def render_scene(clip_path: str, duration: float, out_path: str, scene_idx: int) -> str:
    """Render one scene to a 1920x1080 clip with Ken Burns + grade + vignette."""
    n_frames = max(int(duration * S.FPS), 1)
    # scale up 15% so the zoom-in has headroom; cover-crop to 16:9; loop short clips
    vf = (
        f"scale={int(S.VIDEO_W*1.15)}:{int(S.VIDEO_H*1.15)}:force_original_aspect_ratio=increase,"
        f"crop={int(S.VIDEO_W*1.15)}:{int(S.VIDEO_H*1.15)},"
        # Ken Burns: 1.0 -> 1.08 slow zoom, centered
        f"zoompan=z='1+0.08*on/{n_frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={S.VIDEO_W}x{S.VIDEO_H}:fps={S.FPS},"
        # cinematic teal-orange grade
        f"eq=contrast=1.10:saturation=1.12:brightness=-0.02,"
        f"colorbalance=rs=-0.05:gs=0.0:bs=0.10:rm=0.02:gm=0.0:bm=-0.02:rh=0.06:gh=0.02:bh=-0.06,"
        f"vignette,"
        # subtle scene-transition fade from black
        f"fade=t=in:st=0:d=0.3,"
        f"setsar=1,format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",          # loop short source clips to fill duration
        "-i", clip_path,
        "-t", f"{duration:.3f}",
        "-an",
        "-vf", vf,
        "-r", str(S.FPS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        out_path,
    ]
    _run(cmd, f"scene {scene_idx} render ({duration:.1f}s, {os.path.basename(clip_path)})")
    return out_path


# ----- Stage 2: concat -----------------------------------------------------
def concat_scenes(scene_paths: list[str], out_path: str) -> str:
    list_file = out_path + ".list.txt"
    with open(list_file, "w") as f:
        for p in scene_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", out_path,
    ]
    _run(cmd, f"concat {len(scene_paths)} scenes -> visual.mp4")
    os.remove(list_file)
    return out_path


# ----- Stage 3: bottom gradient (subtitle legibility) ----------------------
def make_gradient(out_path: str, w: int = S.VIDEO_W, h: int = S.VIDEO_H) -> str:
    """Transparent -> semi-black at the bottom third (where subtitles sit)."""
    from PIL import Image
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    fade_start = int(h * 0.62)   # transparent until 62% down
    fade_end = h
    for y in range(fade_start, fade_end):
        t = (y - fade_start) / max(fade_end - fade_start, 1)
        alpha = int(170 * t)     # up to ~67% black at the very bottom
        for x in range(w):
            px[x, y] = (0, 0, 0, alpha)
    img.save(out_path)
    print(f"[compose] gradient saved: {out_path}")
    return out_path


# ----- Stage 4: audio mix (narration + ducked music) -----------------------
def mix_audio(narration_path: str, music_path: str, duration: float,
              out_path: str) -> str:
    """Narration full-volume + music ducked under speech via sidechaincompress."""
    fade_out_st = max(duration - 3.0, 0.1)
    # music: low base volume, 3s fade-in, 3s fade-out; looped to duration
    # sidechaincompress ducks music when narration is present
    # amix normalizes off so levels are preserved
    fg = (
        f"[1:a]volume=0.22,afade=t=in:st=0:d=3,afade=t=out:st={fade_out_st:.3f}:d=3[bgpre];"
        f"[bgpre][0:a]sidechaincompress=threshold=0.035:ratio=8:attack=10:release=350[bgduck];"
        f"[0:a][bgduck]amix=inputs=2:duration=first:normalize=0[a]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", narration_path,
        "-stream_loop", "-1", "-i", music_path,
        "-t", f"{duration:.3f}",
        "-filter_complex", fg,
        "-map", "[a]",
        "-c:a", "aac", "-b:a", "192k",
        out_path,
    ]
    _run(cmd, "audio mix (narration + ducked music)")
    return out_path


# ----- Stage 5: final burn (gradient overlay + subtitles + audio) ----------
def burn_final(visual_path: str, gradient_path: str, ass_path: str,
               audio_path: str, out_path: str) -> str:
    # inputs: 0=visual, 1=audio, 2=gradient  (gradient is index 2, NOT 1)
    if ass_path and os.path.exists(ass_path):
        esc = ass_path.replace("'", r"\'").replace(":", r"\:")
        fg = f"[0:v][2:v]overlay=0:0[grad];[grad]ass='{esc}'[v]"
    else:
        fg = f"[0:v][2:v]overlay=0:0[v]"
    cmd = [
        "ffmpeg", "-y",
        "-i", visual_path,
        "-i", audio_path,
        "-i", gradient_path,
        "-filter_complex", fg,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        out_path,
    ]
    _run(cmd, "final burn (gradient + subtitles + audio)")
    return out_path


# ----- Orchestrator --------------------------------------------------------
def _valid_video(path: str, min_size: int = 100_000) -> bool:
    """True if path is a readable video with a real duration (not a truncated
    encode). Catches the rare bad-source-clip case that produces a tiny or
    moov-less file."""
    import subprocess
    if not os.path.exists(path) or os.path.getsize(path) < min_size:
        return False
    try:
        d = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            text=True, timeout=30,
        ).strip()
        return bool(d) and float(d) > 1.0
    except Exception:
        return False


def compose_premium(scenes: list[dict], clips_map: dict, narration_path: str,
                    music_path: str, ass_path: str, work: str) -> str:
    """Run all stages. scenes must have 'duration' and 'audio_path'.
    clips_map = {scene_index: [clip_path,...]}. Returns final.mp4 path.

    Per-scene clips are tried in order until one renders + validates — a single
    bad Mixkit source clip won't crash the whole run.
    """
    scenes_dir = os.path.join(work, "scenes")
    os.makedirs(scenes_dir, exist_ok=True)

    scene_paths = []
    for i, scene in enumerate(scenes):
        clips = clips_map.get(i, [])
        if not clips:
            raise RuntimeError(f"scene {i} has no footage")
        sp = os.path.join(scenes_dir, f"scene_{i:03d}.mp4")
        rendered = False
        for j, clip in enumerate(clips):
            try:
                render_scene(clip, scene["duration"], sp, i)
                if _valid_video(sp):
                    rendered = True
                    break
                print(f"[compose] scene {i} clip {j+1} produced invalid output — trying next")
            except Exception as e:
                print(f"[compose] scene {i} clip {j+1} failed ({str(e)[:150]}) — trying next")
            if os.path.exists(sp):
                try:
                    os.remove(sp)
                except OSError:
                    pass
        if not rendered:
            raise RuntimeError(f"scene {i}: no clip rendered successfully out of {len(clips)}")
        scene_paths.append(sp)

    visual = os.path.join(work, "visual.mp4")
    concat_scenes(scene_paths, visual)

    gradient = os.path.join(work, "gradient.png")
    make_gradient(gradient)

    total = sum(s["duration"] for s in scenes)
    audio_mix = os.path.join(work, "audio_mix.m4a")
    mix_audio(narration_path, music_path, total, audio_mix)

    final = os.path.join(work, "final.mp4")
    burn_final(visual, gradient, ass_path, audio_mix, final)
    return final
