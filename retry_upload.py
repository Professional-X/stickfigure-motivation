"""Retry uploading unpublished videos.

Scans output/ for video directories that have metadata.json but no uploaded.txt.
Downloads the final.mp4 from the GitHub Release (created by publish.yml), then
uploads to YouTube via Composio. If upload fails (e.g. quota exceeded), exits
cleanly — the next scheduled retry run will pick it up again.

Designed to run on a hourly cron. Fast exit:
  - If nothing to retry: exit in <1 second
  - If upload fails: exit immediately, don't loop or wait
  - If upload succeeds: write uploaded.txt, move to next video

This keeps each workflow run SHORT (max ~5 minutes for one upload attempt)
so we never burn hours of Actions minutes waiting on quota resets.
"""
import os
import sys
import json
import glob
import subprocess
import traceback
from datetime import datetime

import config
from upload import upload_to_youtube


def _download_video_from_release(run_dir: str, metadata: dict) -> str | None:
    """Download final.mp4 from GitHub Release if not present locally.
    Returns path to the downloaded mp4, or None on failure.
    """
    final_mp4 = os.path.join(run_dir, "final.mp4")
    if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 10000:
        return final_mp4  # already there

    # Read release_info.json to find the release URL
    release_info_path = os.path.join(run_dir, "release_info.json")
    if not os.path.exists(release_info_path):
        return None
    try:
        with open(release_info_path) as f:
            release_info = json.load(f)
    except Exception:
        return None

    run_id = release_info.get("run_id")
    if not run_id:
        return None

    # Use gh CLI to download the asset
    print(f"[retry] downloading final.mp4 from release video-{run_id}...")
    try:
        result = subprocess.run(
            ["gh", "release", "download", f"video-{run_id}",
             "--pattern", "final.mp4",
             "--dir", run_dir,
             "--clobber"],
            check=True, capture_output=True, text=True, timeout=120,
        )
        if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 10000:
            return final_mp4
    except subprocess.CalledProcessError as e:
        print(f"[retry] gh release download failed: {e.stderr[:200]}")
    except Exception as e:
        print(f"[retry] download exception: {e}")
    return None


def find_unpublished_videos() -> list[dict]:
    """Find all video dirs with metadata.json but no uploaded.txt."""
    results = []
    output_root = os.path.abspath(config.OUTPUT_DIR)
    if not os.path.isdir(output_root):
        return results

    for entry in sorted(os.listdir(output_root)):
        run_dir = os.path.join(output_root, entry)
        if not os.path.isdir(run_dir):
            continue
        uploaded_marker = os.path.join(run_dir, "uploaded.txt")
        failed_marker = os.path.join(run_dir, "UPLOAD_FAILED_PERMANENT.txt")
        metadata_file = os.path.join(run_dir, "metadata.json")

        if not os.path.exists(metadata_file):
            continue
        if os.path.exists(uploaded_marker):
            continue
        if os.path.exists(failed_marker):
            continue

        try:
            with open(metadata_file) as f:
                metadata = json.load(f)
        except Exception:
            continue

        if not metadata.get("title"):
            continue

        results.append({
            "run_id": entry,
            "run_dir": run_dir,
            "video_path": os.path.join(run_dir, "final.mp4"),
            "thumbnail_path": os.path.join(run_dir, "thumbnail.png"),
            "title": metadata.get("title", "Untitled"),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", config.YOUTUBE_TAGS),
            "attempts_file": os.path.join(run_dir, "upload_attempts.txt"),
            "metadata": metadata,
        })

    return results


def get_attempt_count(attempts_file: str) -> int:
    if not os.path.exists(attempts_file):
        return 0
    try:
        with open(attempts_file) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def record_attempt(attempts_file: str, success: bool, error: str = ""):
    with open(attempts_file, "a") as f:
        status = "SUCCESS" if success else "FAILED"
        ts = datetime.utcnow().isoformat() + "Z"
        err_short = error[:200].replace("\n", " ") if error else ""
        f.write(f"{ts} {status} {err_short}\n")


def main():
    print(f"=== retry_upload run at {datetime.utcnow().isoformat()}Z ===")
    videos = find_unpublished_videos()
    print(f"[retry] found {len(videos)} unpublished video(s)")

    if not videos:
        print("[retry] nothing to do. exiting.")
        return 0

    uploaded_count = 0
    failed_count = 0

    for video in videos:
        run_id = video["run_id"]
        attempts = get_attempt_count(video["attempts_file"])
        print(f"\n[retry] --- {run_id} (attempt #{attempts + 1}) ---")
        print(f"[retry] title: {video['title'][:80]}")

        # Give up after 24 attempts (one per hour = 24 hours of retries)
        if attempts >= 24:
            print(f"[retry] giving up after {attempts} attempts. Marking permanent failure.")
            with open(os.path.join(video["run_dir"], "UPLOAD_FAILED_PERMANENT.txt"), "w") as f:
                f.write(f"Failed after {attempts} attempts over {attempts} hours.\n")
                f.write(f"Title: {video['title']}\n")
                f.write("Upload manually at https://www.youtube.com/upload\n")
            failed_count += 1
            continue

        # Get the video file (download from release if needed)
        video_path = _download_video_from_release(video["run_dir"], video["metadata"])
        if not video_path:
            print(f"[retry] could not obtain video file. Skipping.")
            record_attempt(video["attempts_file"], success=False, error="no video file")
            failed_count += 1
            continue

        print(f"[retry] video: {video_path} ({os.path.getsize(video_path) // 1024 // 1024} MB)")

        # Custom thumbnail (committed to repo by publish.yml — small, ~40 KB)
        thumb_path = video["thumbnail_path"]
        if os.path.exists(thumb_path):
            print(f"[retry] thumbnail: {thumb_path} ({os.path.getsize(thumb_path) // 1024} KB)")
        else:
            thumb_path = None
            print(f"[retry] no thumbnail found — will upload without custom thumbnail")

        try:
            video_id = upload_to_youtube(
                video_path=video_path,
                title=video["title"],
                description=video["description"],
                tags=video["tags"],
                thumbnail_path=thumb_path,
            )
            if video_id:
                with open(os.path.join(video["run_dir"], "uploaded.txt"), "w") as f:
                    f.write(f"https://youtube.com/watch?v={video_id}\n")
                    f.write(f"uploaded_at: {datetime.utcnow().isoformat()}Z\n")
                record_attempt(video["attempts_file"], success=True, error=f"video_id={video_id}")
                print(f"[retry] SUCCESS: https://youtube.com/watch?v={video_id}")
                uploaded_count += 1
            else:
                record_attempt(video["attempts_file"], success=False, error="skipped (no creds)")
                print(f"[retry] skipped (no upload credentials configured)")
                # Mark permanent if no creds at all
                if not os.environ.get("COMPOSIO_API_KEY") and not os.environ.get("YOUTUBE_REFRESH_TOKEN"):
                    print(f"[retry] no credentials configured — marking permanent failure")
                    with open(os.path.join(video["run_dir"], "UPLOAD_FAILED_PERMANENT.txt"), "w") as f:
                        f.write("No upload credentials configured (neither YouTube OAuth nor Composio).\n")
                failed_count += 1
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            print(f"[retry] FAILED: {err_msg[:200]}")
            record_attempt(video["attempts_file"], success=False, error=err_msg)
            # If quota exceeded (429), stop trying other videos this run
            if "429" in err_msg or "quota" in err_msg.lower():
                print(f"[retry] quota exceeded — stopping this run. Will retry next hour.")
                failed_count += 1
                break
            failed_count += 1

        # Clean up the downloaded mp4 to keep the repo small
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                print(f"[retry] cleaned up local mp4")
        except Exception:
            pass

    print(f"\n[retry] === run complete ===")
    print(f"[retry] uploaded: {uploaded_count}, failed: {failed_count}, total pending: {len(videos)}")
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[retry] FATAL: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
