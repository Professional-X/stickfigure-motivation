"""Premium long-form pipeline orchestrator for @StickVerse.

This is what publish.yml runs (replaces the stickfigure `python pipeline.py`).
Fully free, no LLM, no API keys beyond the existing YouTube/Composio upload
secrets:

  1. pick next unpublished topic (video 1 first)         premium.queue
  2. per-scene narration via Edge-TTS                     tts.py (reused)
  3. concat full narration + whisper transcribe -> ASS    subtitles.py (reused)
                                                            premium.subtitles
  4. ensure music bed (Incompetech CC-BY, cached)         premium.music
  5. scrape + download Mixkit footage per scene           premium.mixkit
  6. extract stills + render 3 cinematic thumbnails       premium.thumbnails
  7. compose: Ken Burns + grade + vignette + subs + ducked music
                                                          premium.compose
  8. build SEO metadata                                   premium.metadata
  9. upload to YouTube (custom thumbnail)                 upload.py (reused)

Run:    python pipeline_premium.py
Output: ./output/<run_id>/final.mp4 + thumbnail.png + metadata.json + uploaded.txt
"""
import os
import json
import traceback

import config
from tts import synth_scene_timed, get_audio_duration, concat_audio, process_narration
from upload import upload_to_youtube

from premium import queue as Q
from premium import mixkit as MX
from premium import music as MU
from premium import subtitles as SUB
from premium import thumbnails as TH
from premium import compose as CO
from premium import metadata as META
from premium import scripts as S
from premium import visuals as VS
from datetime import datetime


def run():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = os.path.abspath(os.path.join(config.OUTPUT_DIR, run_id))
    os.makedirs(work, exist_ok=True)
    print(f"\n=== premium pipeline run {run_id} ===")
    print(f"[pipeline] workspace: {work}")

    channel_handle = os.environ.get("CHANNEL_HANDLE", "")

    # 1. Topic
    topic = Q.pick_topic(config.OUTPUT_DIR)
    print(f"[pipeline] topic: {topic['id']} ({topic['category']}) — {topic['title']}")

    scenes = topic["scenes"]
    print(f"[pipeline] {len(scenes)} scenes, ~{sum(len(s['narration'].split()) for s in scenes)} words\n")

    # 2. Per-scene TTS (human-cadence engine: per-sentence prosody + breathing
    #    gaps; returns sentence timings used by compose for beat-synced cuts)
    for i, scene in enumerate(scenes):
        print(f"--- scene {i+1}/{len(scenes)} ---")
        audio_path = os.path.join(work, f"audio_{i:03d}.mp3")
        timings = synth_scene_timed(scene["narration"], audio_path)
        scene["audio_path"] = audio_path
        scene["duration"] = get_audio_duration(audio_path)
        scene["sentence_timings"] = timings
        print(f"    duration: {scene['duration']:.1f}s ({len(timings)} sentences)")

    total_duration = sum(s["duration"] for s in scenes)
    print(f"\n[pipeline] total duration: {total_duration/60:.2f} min ({total_duration:.1f}s)")

    # 3. Concat narration + transcribe -> ASS (resilient: skip subs on failure)
    full_narration = os.path.join(work, "full_narration.mp3")
    concat_audio([s["audio_path"] for s in scenes], full_narration)
    # softer + more human narration: gentle compression, de-ess, warmth, smooth
    # normalize (tames Edge-TTS metallic edge + shouty peaks). Applied BEFORE
    # transcription (cleaner audio -> better Whisper results) + before mix.
    processed = os.path.join(work, "narration_processed.mp3")
    process_narration(full_narration, processed)
    full_narration = processed
    sub_path = os.path.join(work, "subtitles.ass")
    ass_path = SUB.transcribe_and_ass(full_narration, sub_path)
    if ass_path is None:
        ass_path = ""   # burn_final tolerates empty -> no subs

    # 4. Music
    music_path, music_attr = MU.ensure_music(config.MUSIC_DIR)

    # 5. Topical AI stills (PRIMARY) — every frame now shows the THING the
    #    script is about, not generic stock. Mixkit is fetched lazily as a
    #    per-scene fallback only for scenes where image generation fell short.
    visuals_dir = os.path.join(work, "visuals")
    stills_map = VS.fetch_stills_for_scenes(topic, scenes, visuals_dir,
                                            per_scene=config.VISUALS_PER_SCENE)
    clips_dir = os.path.join(work, "clips")
    clips_map = {}
    missing = [i for i in range(len(scenes)) if not stills_map.get(i)]
    if missing:
        print(f"[pipeline] {len(missing)} scene(s) short on stills -> Mixkit fallback")
        clips_map = MX.fetch_clips_for_scenes(scenes, clips_dir, per_scene=3)

    # 6. Thumbnails (background = topical AI still from scenes 0-2; Mixkit
    #    still extraction as fallback)
    thumb_stills_dir = os.path.join(work, "thumb_stills")
    os.makedirs(thumb_stills_dir, exist_ok=True)
    still_paths = []
    for i in range(min(3, len(scenes))):
        sp = os.path.join(thumb_stills_dir, f"still_{i}.png")
        if stills_map.get(i):
            try:
                TH.grade_still(stills_map[i][0], sp)
                still_paths.append(sp)
                continue
            except Exception as e:
                print(f"[pipeline] grade_still {i} failed ({str(e)[:80]}) -> raw still")
                still_paths.append(stills_map[i][0])
                continue
        clips = clips_map.get(i, [])
        if clips:
            try:
                TH.extract_still(clips[0], sp, t_offset=1.5)
                still_paths.append(sp)
            except Exception as e:
                print(f"[pipeline] still {i} failed: {e}")
    if not still_paths:
        # last resort: a plain dark still
        from PIL import Image
        sp = os.path.join(thumb_stills_dir, "still_fallback.png")
        Image.new("RGB", (TH.W, TH.H), (12, 12, 14)).save(sp)
        still_paths.append(sp)

    thumb_dir = os.path.join(work, "thumbnails")
    thumb_variants = TH.render_variants(still_paths, topic["thumbnail_text"],
                                        thumb_dir, channel_handle)
    # pick variant B (centered + red accent) as the upload thumbnail; A/C as alternates
    primary_thumb = os.path.join(work, "thumbnail.png")
    chosen = thumb_variants[1] if len(thumb_variants) >= 2 else thumb_variants[0]
    import shutil
    shutil.copy(chosen, primary_thumb)
    print(f"[pipeline] primary thumbnail: {os.path.basename(chosen)}")

    # 7. Compose
    print(f"\n[pipeline] composing cinematic video (this takes a few minutes)...")
    final_path = CO.compose_premium(scenes, clips_map, full_narration,
                                    music_path, ass_path, work, stills_map=stills_map)
    print(f"[pipeline] final video: {final_path} ({os.path.getsize(final_path)//(1<<20)} MB)")

    # 8. Metadata
    metadata = META.build_metadata(topic, scenes, total_duration, music_attr)
    metadata["run_id"] = run_id
    metadata["video_path"] = final_path
    metadata["thumbnail_path"] = primary_thumb
    metadata["thumbnail_variants"] = thumb_variants
    metadata["channel_handle"] = channel_handle
    with open(os.path.join(work, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    # 9. Upload
    print(f"\n[pipeline] uploading to YouTube...")
    try:
        video_id = upload_to_youtube(
            video_path=final_path,
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"],
            thumbnail_path=primary_thumb,
        )
        if video_id:
            print(f"\n[pipeline] === uploaded: https://youtube.com/watch?v={video_id} ===")
            with open(os.path.join(work, "uploaded.txt"), "w") as f:
                f.write(f"https://youtube.com/watch?v={video_id}\n")
        else:
            with open(os.path.join(work, "MANUAL_UPLOAD_NEEDED.txt"), "w") as f:
                f.write(f"Video: {final_path}\n")
                f.write(f"Title: {metadata['title']}\n\n")
                f.write(f"Description:\n{metadata['description']}\n\n")
                f.write(f"Tags: {', '.join(metadata['tags'])}\n")
                f.write(f"Thumbnail: {primary_thumb}\n")
                f.write(f"Upload at: https://www.youtube.com/upload\n")
    except Exception as e:
        print(f"\n[pipeline] UPLOAD FAILED: {e}")
        print(f"[pipeline] video saved locally at: {final_path}")
        traceback.print_exc()

    print(f"\n[pipeline] run complete. workspace: {work}")
    return work


if __name__ == "__main__":
    run()
