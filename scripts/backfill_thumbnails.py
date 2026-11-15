#!/usr/bin/env python3
"""Backfill custom thumbnails on already-uploaded StickVerse videos.

WHY: Each video's cinematic thumbnail is rendered + committed to the repo, but
it only gets SET on YouTube automatically IF the YOUTUBE_* OAuth secrets are
configured. Videos uploaded before OAuth was added (or via the Composio path,
which can't set thumbnails) get YouTube's auto-generated thumbnail instead.

This script walks output/*/, finds every video with an uploaded.txt marker +
a thumbnail.png, and sets that thumbnail via the YouTube Data API. Safe to
re-run: it skips videos whose thumbnail is already the rendered one (you can
force re-set with --force).

PREREQ (one-time):
  1. Run:  python get_youtube_oauth.py    (opens a browser for consent)
  2. Add the 3 printed values as repo secrets (or export them here):
       YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN

USAGE:
  python backfill_thumbnails.py            # set thumbnails on all videos
  python backfill_thumbnails.py --force    # re-set even if already set
  python backfill_thumbnails.py --dir output/20261115_033431   # just one
"""
import argparse
import base64
import glob
import os
import re
import requests


def refresh_access_token() -> str:
    cid = os.environ["YOUTUBE_CLIENT_ID"]
    sec = os.environ["YOUTUBE_CLIENT_SECRET"]
    rt = os.environ["YOUTUBE_REFRESH_TOKEN"]
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": cid, "client_secret": sec,
        "refresh_token": rt, "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def set_thumbnail(video_id: str, thumb_path: str, access_token: str) -> tuple[bool, str]:
    with open(thumb_path, "rb") as f:
        img = f.read()
    r = requests.post(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "image/png"},
        data=img, timeout=120,
    )
    ok = r.status_code in (200, 201)
    return ok, f"HTTP {r.status_code} {r.text[:200]}"


def video_id_from_uploaded(path: str) -> str | None:
    with open(path) as f:
        txt = f.read()
    m = re.search(r"v=([A-Za-z0-9_-]{11})", txt)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="specific output/<run> dir")
    ap.add_argument("--force", action="store_true", help="re-set even if no marker")
    args = ap.parse_args()

    for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        if not os.environ.get(k):
            print(f"ERROR: {k} not set. Run get_youtube_oauth.py first, then export "
                  f"the 3 values (or add them as repo secrets).")
            return

    dirs = [args.dir] if args.dir else sorted(glob.glob("output/*/"))
    dirs = [d for d in dirs if os.path.isdir(d)]
    if not dirs:
        print("no output dirs found"); return

    print(f"Refreshing access token...")
    token = refresh_access_token()

    done = 0
    for d in dirs:
        uploaded = os.path.join(d, "uploaded.txt")
        thumb = os.path.join(d, "thumbnail.png")
        marker = os.path.join(d, "THUMBNAIL_MANUAL_NEEDED.txt")
        if not (os.path.exists(uploaded) and os.path.exists(thumb)):
            continue  # not uploaded, or no thumbnail rendered
        if not args.force and not os.path.exists(marker):
            print(f"  {d}: thumbnail already set (no marker) — skip (--force to re-set)")
            continue
        vid = video_id_from_uploaded(uploaded)
        if not vid:
            print(f"  {d}: couldn't parse video_id from uploaded.txt — skip"); continue
        print(f"  {d}: setting thumbnail on video {vid}...")
        ok, msg = set_thumbnail(vid, thumb, token)
        if ok:
            print(f"    OK — thumbnail set")
            if os.path.exists(marker):
                os.remove(marker)
                print(f"    removed {os.path.basename(marker)}")
            done += 1
        else:
            print(f"    FAILED — {msg}")
            if "verify" in msg.lower():
                print("    NOTE: custom thumbnails require a verified YouTube account")
                print("          (https://www.youtube.com/verify, ~24h to activate)")

    print(f"\nDone. Thumbnails set on {done} video(s).")
    if done and not args.dir:
        print("Commit the removed markers: git add output/ && git commit -m "
              "'chore: thumbnails backfilled' && git push")


if __name__ == "__main__":
    main()
