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


# ----- Stage 1b: rapid-cut montage (the "fast frames + effects" engine) -----
# Instead of one slow 30s zoom per scene, each scene is broken into ~2-4s
# segments cut on the narration's sentence boundaries, each rendered with a
# rotating motion (zoom-in / pan-L / zoom-out / pan-R), stitched with quick
# 0.12s xfades. This is the classic retention trick: the eye gets a fresh
# composition every couple of seconds, so attention never settles long enough
# to scroll. Motion is fast but not violent (we learned earlier that dizzying
# zoompan hurts); the energy comes from CUTS + direction alternation.

MOTIONS = ("in", "pan_lr", "out", "pan_rl")


def _motion_expr(motion: str, n_frames: int) -> tuple[str, str, str]:
    """Return (z, x, y) zoompan expressions for a motion type."""
    Z = 0.10        # max zoom delta
    PZ = 1.08       # fixed zoom factor for pan segments
    nf = max(n_frames, 1)
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if motion == "in":
        return (f"1+{Z}*on/{nf}", cx, cy)
    if motion == "out":
        return (f"1+{Z}-{Z}*on/{nf}", cx, cy)
    if motion == "pan_lr":
        return (f"{PZ}", f"(iw-iw/zoom)*on/{nf}", cy)
    if motion == "pan_rl":
        return (f"{PZ}", f"(iw-iw/zoom)*(1-on/{nf})", cy)
    return ("1.0", cx, cy)  # static


def _segment_plan(duration: float, timings: list[dict],
                  min_seg: float = 1.6, max_seg: float = 4.0) -> list[tuple[float, float]]:
    """Turn sentence timings into (start, end) cut points, enforcing a 1.6-4.0s
    segment window. Falls back to even ~3s splits when no timings are passed."""
    if not timings:
        n = max(1, int(round(duration / 3.0)))
        edges = [duration * i / n for i in range(n + 1)]
        return [(edges[i], edges[i + 1]) for i in range(n)]
    cuts = [0.0] + [t["end"] for t in timings] + [duration]
    merged = [0.0]
    for c in cuts[1:]:
        if c - merged[-1] >= min_seg or abs(c - duration) < 0.05:
            merged.append(min(c, duration))
    if merged[-1] < duration - 0.05:
        merged.append(duration)
    merged[-1] = duration
    segs = []
    for i in range(len(merged) - 1):
        s, e = merged[i], merged[i + 1]
        while e - s > max_seg:
            segs.append((s, s + max_seg))
            s += max_seg
        if e - s > 0.1:
            segs.append((s, e))
    return segs or [(0.0, duration)]


def _render_segment(clip_path: str, seg_dur: float, motion: str, seg_idx: int,
                    scenes_dir: str, fade_in: bool = False,
                    is_image: bool = False) -> str:
    """Render one short segment with its motion + cinematic grade + vignette.

    is_image=True handles a still-image source (the topical AI stills from
    premium/visuals.py): ffmpeg reads it with `-loop 1` and we lanczos-upscale
    the first scale step so the 1024x576 Pollinations output stays sharp when
    blown up to 1920x1080. Video sources (Mixkit 1080p) keep the default
    bicubic + `-stream_loop -1` path.
    """
    n_frames = max(int(seg_dur * S.FPS), 1)
    W, H = S.VIDEO_W, S.VIDEO_H
    sw, sh = int(W * 1.18), int(H * 1.18)   # headroom for pan + zoom
    z, x, y = _motion_expr(motion, n_frames)
    # lanczos on the upscale for image sources (sharp); default for video
    scale_flags = ":flags=lanczos" if is_image else ""
    vf = (
        f"scale={sw}:{sh}:force_original_aspect_ratio=increase{scale_flags},"
        f"crop={sw}:{sh},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={S.FPS},"
        f"eq=contrast=1.10:saturation=1.14:brightness=-0.02,"
        f"colorbalance=rs=-0.05:gs=0.0:bs=0.10:rm=0.02:gm=0.0:bm=-0.02:rh=0.06:gh=0.02:bh=-0.06,"
        f"vignette,"
        + ("fade=t=in:st=0:d=0.25," if fade_in else "")
        + "setsar=1,format=yuv420p"
    )
    out = os.path.join(scenes_dir, f"seg_{seg_idx:03d}.mp4")
    if is_image:
        in_args = ["-loop", "1", "-i", clip_path]
    else:
        in_args = ["-stream_loop", "-1", "-i", clip_path]
    cmd = ["ffmpeg", "-y", *in_args,
           "-t", f"{seg_dur:.3f}", "-an", "-vf", vf, "-r", str(S.FPS),
           "-c:v", "libx264", "-preset", "fast", "-crf", "20", out]
    _run(cmd, f"  seg {seg_idx} ({motion}, {seg_dur:.1f}s"
              + (", still" if is_image else "") + ")")
    return out


def _xfade_concat_segs(seg_paths: list[str], seg_durs: list[float], out_path: str) -> str:
    """Stitch segments with 0.12s fade xfades (quick energy cuts).

    CRITICAL: each xfade shortens the chain by `xf` (the transition overlap).
    So the offset for the k-th xfade must be measured against the ACTUAL running
    output end (cumulative segment durations MINUS k prior overlaps), not
    against the raw sum of segment durations. The earlier version used the raw
    sum, which made every offset after the 2nd segment land PAST the chain end —
    ffmpeg then truncated the output to the first ~2 segments, producing ~5s
    scenes instead of ~38s (the broken ~30s YouTube video on run #30).
    """
    if len(seg_paths) == 1:
        _run(["ffmpeg", "-y", "-i", seg_paths[0], "-c", "copy",
              "-pix_fmt", "yuv420p", out_path], "  single-segment scene")
        return out_path
    xf = 0.12
    parts, prev = [], "[0:v]"
    end_prev = seg_durs[0]                      # actual duration of the chain so far
    for i in range(1, len(seg_paths)):
        off = max(0.0, end_prev - xf)           # transition starts xf before chain end
        nv = f"[v{i}]"
        parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xf}:offset={off:.3f}{nv}")
        prev = nv
        end_prev = end_prev + seg_durs[i] - xf  # new chain end (lost xf to overlap)
    args = ["ffmpeg", "-y"]
    for p in seg_paths:
        args += ["-i", p]
    args += ["-filter_complex", ";".join(parts), "-map", prev,
             "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-r", str(S.FPS),                  # pin CFR 30fps so concat_scenes -c copy is clean
             "-pix_fmt", "yuv420p", out_path]
    _run(args, f"  xfade concat {len(seg_paths)} segments")
    return out_path


def _valid_image(path: str, min_size: int = 3000) -> bool:
    """True if path is a readable still image (the topical AI stills)."""
    if not os.path.exists(path) or os.path.getsize(path) < min_size:
        return False
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def render_scene_montage(clips: list[str], duration: float, timings: list[dict],
                         out_path: str, scene_idx: int,
                         is_image: bool = False) -> str:
    """Render one scene as a rapid-cut montage cycling through the scene's
    sources with rotating motion. Sources are either Mixkit video clips
    (is_image=False, the legacy path) or topical AI stills (is_image=True,
    from premium/visuals.py — `-loop 1` + lanczos upscale per segment).

    With stills, the scene's `per_scene` variants are alternated across the
    segment cuts so no two consecutive cuts share the same frame. If no still
    validates, raises so compose_premium's try/except falls back to Mixkit.
    """
    scenes_dir = os.path.dirname(out_path)
    checker = _valid_image if is_image else _valid_video
    valid_clips = [c for c in clips if checker(c)]
    if not valid_clips:
        if is_image:
            raise RuntimeError(f"scene {scene_idx}: no valid stills -> Mixkit fallback")
        fallback = os.path.join(scenes_dir, f"fallback_{scene_idx}.mp4")
        _run(["ffmpeg", "-y", "-f", "lavfi",
              "-i", "color=c=0x0e0e12:s=1920x1080:r=30:d=2",
              "-c:v", "libx264", "-preset", "fast", "-crf", "20", fallback],
             f"  scene {scene_idx} color-fallback source")
        valid_clips = [fallback]

    segs = _segment_plan(duration, timings)
    n_seg = len(segs)
    # Each xfade transition consumes `xf` seconds of overlap, so a naive concat
    # comes up short by (n_seg-1)*xf — the visual would end before the audio
    # and burn_final's -shortest would clip the tail of the narration. Inflate
    # each segment by the per-segment share of that loss so the concatenated
    # scene is EXACTLY `duration` long (audio/video sync, verified end-to-end).
    xf = 0.12
    inflate = ((n_seg - 1) * xf / n_seg) if n_seg > 1 else 0.0
    seg_paths, seg_durs = [], []
    for k, (s, e) in enumerate(segs):
        sd = max(e - s, 0.5) + inflate
        clip = valid_clips[k % len(valid_clips)]
        motion = MOTIONS[k % len(MOTIONS)]
        try:
            p = _render_segment(clip, sd, motion, k, scenes_dir,
                                fade_in=(k == 0), is_image=is_image)
        except Exception as ex:
            print(f"[compose] scene {scene_idx} seg {k} failed ({str(ex)[:80]}) -> retry src[0]/in")
            p = _render_segment(valid_clips[0], sd, "in", k, scenes_dir,
                                fade_in=(k == 0), is_image=is_image)
        seg_paths.append(p)
        seg_durs.append(sd)

    _xfade_concat_segs(seg_paths, seg_durs, out_path)
    for p in seg_paths:
        try:
            os.remove(p)
        except OSError:
            pass
    fb = os.path.join(scenes_dir, f"fallback_{scene_idx}.mp4")
    if os.path.exists(fb):
        try:
            os.remove(fb)
        except OSError:
            pass
    kind = "stills" if is_image else "clips"
    print(f"[compose] scene {scene_idx}: {len(segs)} cuts over {duration:.1f}s "
          f"(avg {duration / max(len(segs), 1):.1f}s/cut, {len(valid_clips)} {kind})")
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
                    music_path: str, ass_path: str, work: str,
                    stills_map: dict = None) -> str:
    """Run all stages. scenes must have 'duration' and 'audio_path'.
    clips_map = {scene_index: [clip_path,...]} (Mixkit, the per-scene fallback).
    stills_map = {scene_index: [still_path,...]} (topical AI stills, PRIMARY).
    Returns final.mp4 path.

    Per scene: topical AI stills are rendered first (is_image=True). If a scene
    has no stills or the still montage fails, it falls back to Mixkit video
    clips for that scene, then to a single-clip slow-zoom render — so one bad
    image or source clip never crashes the whole run.
    """
    scenes_dir = os.path.join(work, "scenes")
    os.makedirs(scenes_dir, exist_ok=True)
    stills_map = stills_map or {}

    scene_paths = []
    for i, scene in enumerate(scenes):
        sp = os.path.join(scenes_dir, f"scene_{i:03d}.mp4")
        timings = scene.get("sentence_timings") or []
        stills = stills_map.get(i, [])
        clips = clips_map.get(i, [])
        rendered = False
        # 1. PRIMARY: topical AI stills
        if stills:
            try:
                render_scene_montage(stills, scene["duration"], timings, sp, i,
                                     is_image=True)
                if _valid_video(sp):
                    rendered = True
                else:
                    raise RuntimeError("still-montage produced invalid output")
            except Exception as e:
                print(f"[compose] scene {i} still montage failed ({str(e)[:130]}) -> Mixkit fallback")
        # 2. FALLBACK: Mixkit video clips
        if not rendered and clips:
            try:
                render_scene_montage(clips, scene["duration"], timings, sp, i)
                if _valid_video(sp):
                    rendered = True
                else:
                    raise RuntimeError("clip-montage produced invalid output")
            except Exception as e:
                print(f"[compose] scene {i} clip montage failed ({str(e)[:150]}) -> single-clip fallback")
                clip0 = next((c for c in clips if _valid_video(c)), clips[0])
                render_scene(clip0, scene["duration"], sp, i)
                rendered = True
        if not rendered:
            raise RuntimeError(f"scene {i} has no usable footage (no stills, no clips)")
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
