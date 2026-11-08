"""Main pipeline — orchestrates the full end-to-end generation.

Run:    python pipeline.py
Output: ./output/<run_id>/final.mp4 (+ plan.json, intermediate files)
"""
import os
import sys
import json
import random
import traceback
from datetime import datetime

import config
from themes import pick_theme
from script_gen import generate_video_plan
from image_gen import generate_image
from tts import synth_scene, get_audio_duration, concat_audio
from subtitles import transcribe, to_ass
from compose import compose_video
from upload import upload_to_youtube


def run():
    # 1. Workspace
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = os.path.abspath(os.path.join(config.OUTPUT_DIR, run_id))
    os.makedirs(work, exist_ok=True)
    print(f"\n=== pipeline run {run_id} ===")
    print(f"[pipeline] workspace: {work}")

    # 2. Theme
    category, theme = pick_theme()
    print(f"[pipeline] theme ({category}): {theme}\n")

    # 3. Script + scene breakdown
    plan = generate_video_plan(theme, category, config.SCENES_PER_VIDEO)
    with open(os.path.join(work, "plan.json"), "w") as f:
        json.dump(plan, f, indent=2)

    scenes = plan["scenes"]
    print(f"\n[pipeline] {len(scenes)} scenes generated\n")

    # 4. Per-scene: image + TTS
    for i, scene in enumerate(scenes):
        print(f"\n--- scene {i + 1}/{len(scenes)} ---")
        img_path = os.path.join(work, f"img_{i:03d}.png")
        audio_path = os.path.join(work, f"audio_{i:03d}.mp3")

        # Image — seed varies per scene for visual variety, but stays deterministic
        seed = config.IMAGE_SEED + i * 7
        generate_image(scene["image_prompt"], img_path, seed=seed)
        scene["image_path"] = img_path

        # Be polite to HuggingFace's free-tier rate limiter (1 req/sec sustained)
        import time as _time
        _time.sleep(1.0)

        # TTS
        synth_scene(scene["narration"], audio_path)
        scene["audio_path"] = audio_path
        scene["duration"] = get_audio_duration(audio_path)
        print(f"    duration: {scene['duration']:.1f}s")

    total_duration = sum(s["duration"] for s in scenes)
    print(f"\n[pipeline] total video duration: {total_duration / 60:.1f} min")

    # 5. Concat all narration for transcription
    full_audio = os.path.join(work, "full_narration.mp3")
    concat_audio([s["audio_path"] for s in scenes], full_audio)

    # 6. Whisper transcription -> ASS subtitles
    segments = transcribe(full_audio)
    sub_path = os.path.join(work, "subtitles.ass")
    to_ass(segments, sub_path)

    # 7. Pick background music (random from ./music)
    music_path = None
    if os.path.isdir(config.MUSIC_DIR):
        music_files = [
            f for f in os.listdir(config.MUSIC_DIR)
            if f.lower().endswith((".mp3", ".wav", ".m4a"))
        ]
        if music_files:
            music_path = os.path.abspath(os.path.join(config.MUSIC_DIR, random.choice(music_files)))
            print(f"[pipeline] background music: {os.path.basename(music_path)}")
        else:
            print("[pipeline] WARNING: ./music is empty — no background music will be added")
    else:
        print("[pipeline] WARNING: ./music dir not found — no background music will be added")

    # 8. Compose final video
    out_path = os.path.join(work, "final.mp4")
    print(f"\n[pipeline] composing video (this takes a while)...")
    compose_video(scenes, music_path, sub_path, out_path)

    # 9. Save metadata
    metadata = {
        "run_id": run_id,
        "title": plan.get("title"),
        "description": plan.get("description"),
        "tags": plan.get("tags", []),
        "theme": theme,
        "category": category,
        "duration_sec": total_duration,
        "scene_count": len(scenes),
        "video_path": out_path,
    }
    with open(os.path.join(work, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    # 10. Upload
    print(f"\n[pipeline] uploading to YouTube...")
    try:
        video_id = upload_to_youtube(
            video_path=out_path,
            title=plan["title"],
            description=plan["description"],
            tags=plan.get("tags", config.YOUTUBE_TAGS),
        )
        print(f"\n[pipeline] === uploaded: https://youtube.com/watch?v={video_id} ===")
        with open(os.path.join(work, "uploaded.txt"), "w") as f:
            f.write(f"https://youtube.com/watch?v={video_id}\n")
    except Exception as e:
        print(f"\n[pipeline] UPLOAD FAILED: {e}")
        print(f"[pipeline] video saved locally at: {out_path}")
        print(f"[pipeline] you can upload manually or fix the Composio setup and re-run.")
        # Don't sys.exit(1) — the artifact will still upload for debugging
        traceback.print_exc()

    print(f"\n[pipeline] run complete. workspace: {work}")
    return work


if __name__ == "__main__":
    run()
