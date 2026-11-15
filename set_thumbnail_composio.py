#!/usr/bin/env python3
"""Workflow step: set the custom thumbnail on the just-uploaded video via
Composio YOUTUBE_UPDATE_THUMBNAIL, using the raw.githubusercontent.com URL of
the thumbnail.png the workflow just committed to the repo.

Runs AFTER the 'Commit metadata + thumbnail' step, so thumbnail.png is already
on remote main. On success it removes the THUMBNAIL_MANUAL_NEEDED marker; on
failure it rewrites the marker with the specific reason (e.g. channel not
verified) and commits either way.
"""
import glob
import os
import re
import subprocess
import sys
import time
import requests

import config
import upload

FULL = os.environ.get("GITHUB_REPOSITORY", "Professional-X/stickfigure-motivation")
OWNER, REPO_NAME = FULL.split("/") if "/" in FULL else ("Professional-X", FULL)
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER}/{REPO_NAME}/main"


def latest_run_dir():
    dirs = sorted(d for d in glob.glob("output/*/")
                  if os.path.isfile(os.path.join(d, "uploaded.txt")))
    return dirs[-1] if dirs else None


def parse_video_id(d):
    with open(os.path.join(d, "uploaded.txt")) as f:
        m = re.search(r"v=([A-Za-z0-9_-]{11})", f.read())
    return m.group(1) if m else None


def wait_for_url(url, tries=12, delay=5):
    for i in range(tries):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200 and "image" in (r.headers.get("content-type") or ""):
                print(f"  raw URL live (try {i+1}, {len(r.content)} bytes)")
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def git_commit(message):
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email",
                    "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", "-A", "output/"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("  (no marker changes to commit)")
        return
    subprocess.run(["git", "commit", "-m", message + " [skip ci]"], check=True)
    subprocess.run(["git", "push"], check=True)
    print(f"  pushed: {message}")


def main():
    d = latest_run_dir()
    if not d:
        print("[set-thumb] no run dir with uploaded.txt — skip")
        return 0
    vid = parse_video_id(d)
    if not vid:
        print(f"[set-thumb] {d}: no video_id in uploaded.txt — skip")
        return 0
    raw_url = f"{RAW_BASE}/{d}thumbnail.png"
    print(f"[set-thumb] run={d.strip('/')} video={vid}")
    print(f"  thumbnail URL: {raw_url}")

    if not wait_for_url(raw_url):
        print("[set-thumb] raw URL not live after ~60s — thumbnail.png may not be committed yet; skip")
        return 0

    ok, msg = upload._set_thumbnail_via_composio(vid, raw_url)
    marker = os.path.join(d, "THUMBNAIL_MANUAL_NEEDED.txt")

    if ok:
        print(f"[set-thumb] SUCCESS — custom thumbnail set on {vid}")
        if os.path.exists(marker):
            os.remove(marker)
            git_commit(f"chore: thumbnail auto-set on {vid} via Composio, remove marker")
        return 0

    print(f"[set-thumb] FAILED — {msg}")
    with open(marker, "w") as f:
        f.write(f"video_url: https://youtube.com/watch?v={vid}\n")
        f.write(f"studio_edit: https://studio.youtube.com/video/{vid}/editing\n")
        f.write(f"primary_thumbnail (committed): {d}thumbnail.png\n")
        f.write(f"raw_url: {raw_url}\n")
        f.write(f"\nAuto-set via Composio YOUTUBE_UPDATE_THUMBNAIL FAILED:\n  {msg}\n")
        if "verify" in msg.lower():
            f.write("\n>> The @StickVerse YouTube channel is NOT phone-verified.\n")
            f.write("   Verify at https://www.youtube.com/verify (SMS, ~24h to activate),\n")
            f.write("   then re-run this workflow OR run scripts/backfill_thumbnails.py.\n")
        else:
            f.write("\nCheck the workflow logs (the 'Set custom thumbnail' step) for details.\n")
    git_commit(f"chore: thumbnail auto-set failed on {vid}, update marker")
    return 0


if __name__ == "__main__":
    sys.exit(main())
