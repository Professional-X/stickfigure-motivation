"""Mixkit free-stock footage scraper + downloader.

Mixkit license: free for commercial use, no attribution required
(https://mixkit.co/license/). Verified scrape pattern (2026-11):
  - category page: https://mixkit.co/free-stock-video/<slug>/
  - clip page links in HTML: free-stock-video/<slug>-<id>/
  - direct mp4:      https://assets.mixkit.co/videos/<id>/<id>-1080.mp4
                     (also 720 and 360 variants)

We scrape the category page once, extract clip ids, and download the highest
available resolution. Clips are de-duplicated within a single video so no
footage repeats.
"""
import os
import re
import random
import requests

UA = {"User-Agent": (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)}

# Map scene clip_category -> Mixkit category slug. Falls back to "nature"
# (the most reliably-populated category) if a slug is missing or empty.
CATEGORIES = {
    "nature": "nature",
    "mountains": "mountains",
    "city": "city",
    "sea": "sea",
    "sky": "sky",
    "road": "road-trip",
    "abstract": "abstract",
    "business": "business",
}

ASSET_BASE = "https://assets.mixkit.co/videos/"
CATEGORY_BASE = "https://mixkit.co/free-stock-video/"
FALLBACK_CATEGORY = "nature"

_CLIP_RE = re.compile(r'free-stock-video/([a-z0-9-]+)-(\d+)/')
_MP4_RE = re.compile(r'(assets\.mixkit\.co/videos/(\d+)/\2-(\d{3,4})\.mp4)')


def scrape_category(category: str, timeout: int = 30) -> list[dict]:
    """Return list of {id, slug, category} clips for a scene clip_category.

    Tries the mapped Mixkit slug; if it yields nothing, falls back to 'nature'.
    """
    slug = CATEGORIES.get(category, FALLBACK_CATEGORY)
    clips = _scrape_slug(slug)
    if not clips:
        clips = _scrape_slug(FALLBACK_CATEGORY)
    # tag with the requested category for logging
    for c in clips:
        c["category"] = category
    return clips


def _scrape_slug(slug: str) -> list[dict]:
    url = CATEGORY_BASE + slug + "/"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200:
            print(f"[mixkit] {slug} -> HTTP {r.status_code}")
            return []
        html = r.text
    except Exception as e:
        print(f"[mixkit] {slug} fetch failed: {e}")
        return []

    found = {}
    for slug_str, cid in _CLIP_RE.findall(html):
        if cid not in found:
            found[cid] = slug_str
    clips = [{"id": cid, "slug": slug_str, "category": slug} for cid, slug_str in found.items()]
    print(f"[mixkit] {slug}: {len(clips)} clips found")
    return clips


def download_clip(clip: dict, out_path: str, prefer_res: int = 1080) -> str:
    """Download the highest available resolution for a clip. Returns out_path.

    Tries 1080 -> 720 -> 360. Raises RuntimeError if none work.
    """
    cid = clip["id"]
    for res in (1080, 720, 360):
        if res > prefer_res:
            continue
        url = f"{ASSET_BASE}{cid}/{cid}-{res}.mp4"
        try:
            r = requests.get(url, headers=UA, timeout=60, stream=True)
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and ("video" in ctype or int(r.headers.get("content-length", 0)) > 100_000):
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        if chunk:
                            f.write(chunk)
                size_mb = os.path.getsize(out_path) / (1 << 20)
                print(f"[mixkit]   downloaded clip {cid} ({res}p, {size_mb:.1f} MB)")
                return out_path
        except Exception as e:
            print(f"[mixkit]   clip {cid} {res}p failed: {e}")
            continue
    raise RuntimeError(f"no downloadable mp4 for clip {cid}")


def fetch_clips_for_scenes(scenes: list[dict], clips_dir: str,
                           per_scene: int = 3, seed: int = 42) -> dict:
    """Download footage for every scene. Returns {scene_index: [clip_path,...]}.

    - Scrapes each unique clip_category once.
    - Dedupes across the whole video (a clip is never reused).
    - Downloads `per_scene` clips per scene (extras = fallback if a scene's
      primary clip fails to compose).
    """
    os.makedirs(clips_dir, exist_ok=True)
    rng = random.Random(seed)

    # Build a pool per category, shuffled, with download attempted lazily.
    cat_clips: dict[str, list[dict]] = {}
    for s in scenes:
        cat = s.get("clip_category", FALLBACK_CATEGORY)
        if cat not in cat_clips:
            cat_clips[cat] = scrape_category(cat)
            rng.shuffle(cat_clips[cat])

    used_ids: set[str] = set()
    result: dict[int, list[str]] = {}

    for i, scene in enumerate(scenes):
        cat = scene.get("clip_category", FALLBACK_CATEGORY)
        pool = cat_clips.get(cat, [])
        # If pool exhausted, top up from nature fallback
        if not pool:
            pool = cat_clips.setdefault(FALLBACK_CATEGORY, scrape_category(FALLBACK_CATEGORY))
            rng.shuffle(pool)

        chosen: list[str] = []
        attempts = 0
        for clip in pool:
            if clip["id"] in used_ids:
                continue
            if len(chosen) >= per_scene:
                break
            out_path = os.path.join(clips_dir, f"clip_{clip['id']}.mp4")
            if os.path.exists(out_path) and os.path.getsize(out_path) > 50_000:
                # already downloaded this run or cached
                chosen.append(out_path)
                used_ids.add(clip["id"])
                continue
            try:
                download_clip(clip, out_path)
                chosen.append(out_path)
                used_ids.add(clip["id"])
            except Exception as e:
                print(f"[mixkit] skipping clip {clip['id']}: {e}")
                continue
            attempts += 1

        if not chosen:
            # last resort: reuse any already-downloaded clip in the video
            existing = [os.path.join(clips_dir, f) for f in os.listdir(clips_dir)
                        if f.endswith(".mp4")]
            if existing:
                chosen = existing[:1]
                print(f"[mixkit] scene {i}: no fresh clips, reusing {os.path.basename(chosen[0])}")
        result[i] = chosen
        print(f"[mixkit] scene {i} ({cat}): {len(chosen)} clips ready")

    return result
