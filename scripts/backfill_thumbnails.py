#!/usr/bin/env python3
"""Backfill custom thumbnails on already-uploaded StickVerse videos.

WHY: Each video's cinematic thumbnail is rendered + committed to the repo, and
the workflow now auto-sets it on YouTube via Composio's YOUTUBE_UPDATE_THUMBNAIL
action. Videos uploaded BEFORE that wiring existed (or while the channel was
not yet phone-verified) got YouTube's auto-generated thumbnail instead. This
script sets the rendered thumbnail on every such video, using the same Composio
path as the workflow (the committed thumbnail.png's raw GitHub URL).

PREREQ (one-time): the @StickVerse channel must be phone-verified at
  https://www.youtube.com/verify  (SMS, ~24h to activate). Until verified,
  YouTube rejects all custom-thumbnail uploads with 403.

USAGE (run from the repo root, with the Composio creds exported):
  export COMPOSIO_API_KEY=ak_...
  export COMPOSIO_ENTITY_ID=pg-test-...
  python scripts/backfill_thumbnails.py            # set on all videos flagged
  python scripts/backfill_thumbnails.py --force    # re-set on ALL (even if no marker)
  python scripts/backfill_thumbnails.py --dir output/20261115_033431
"""
import argparse
import glob
import os
import re
import subprocess
import sys

# allow `import upload` whether run from repo root or scripts/
ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip() or os.getcwd()
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import upload  # noqa: E402

OWNER, REPO_NAME = "Professional-X", "stickfigure-motivation"


def video_id_from_uploaded(path):
    with open(path) as f:
        m = re.search(r"v=([A-Za-z0-9_-]{11})", f.read())
    return m.group(1) if m else None


def git_owner_repo():
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"],
                             capture_output=True, text=True).stdout.strip()
        m = re.search(r"github[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", url)
        if m:
            return m.group(1), m.group(2)
    except Exception:
        pass
    return OWNER, REPO_NAME


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="specific output/<run> dir")
    ap.add_argument("--force", action="store_true", help="re-set even without a marker")
    args = ap.parse_args()

    owner, repo = git_owner_repo()
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/main"

    if not (os.environ.get("COMPOSIO_API_KEY") and os.environ.get("COMPOSIO_ENTITY_ID")):
        print("ERROR: COMPOSIO_API_KEY / COMPOSIO_ENTITY_ID not set.")
        print("Export them (same values as the repo secrets) + ensure the channel")
        print("is verified at https://www.youtube.com/verify first.")
        return

    dirs = [args.dir] if args.dir else sorted(glob.glob("output/*/"))
    dirs = [d if d.endswith("/") else d + "/" for d in dirs if os.path.isdir(d)]
    if not dirs:
        print("no output dirs found"); return

    done = 0
    for d in dirs:
        uploaded = os.path.join(d, "uploaded.txt")
        thumb = os.path.join(d, "thumbnail.png")
        marker = os.path.join(d, "THUMBNAIL_MANUAL_NEEDED.txt")
        if not (os.path.exists(uploaded) and os.path.exists(thumb)):
            continue
        if not args.force and not os.path.exists(marker):
            print(f"  {d.strip('/')}: already set (no marker) — use --force to re-set")
            continue
        vid = video_id_from_uploaded(uploaded)
        if not vid:
            print(f"  {d}: couldn't parse video_id — skip"); continue
        raw_url = f"{raw_base}/{d}thumbnail.png"
        print(f"  {d.strip('/')}: setting thumbnail on {vid} via Composio...")
        ok, msg = upload._set_thumbnail_via_composio(vid, raw_url)
        if ok:
            print(f"    OK — thumbnail set")
            if os.path.exists(marker):
                os.remove(marker)
            done += 1
        else:
            print(f"    FAILED — {msg}")
            if "verify" in msg.lower():
                print("    >> Channel not verified. Verify at https://www.youtube.com/verify (~24h).")
                return  # no point continuing — all will 403

    print(f"\nDone. Thumbnails set on {done} video(s).")
    if done:
        print("Commit the removed markers: git add output/ && "
              "git commit -m 'chore: thumbnails backfilled' && git push")


if __name__ == "__main__":
    main()
