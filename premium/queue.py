"""Topic queue — pick the next unpublished video.

publish.yml commits output/<run_id>/metadata.json + uploaded.txt after each
successful upload (output/ is gitignored but these markers are force-added).
So on the next workflow run, checkout includes prior markers and we can tell
which topic_ids have already been published.

pick_topic() returns the first TOPICS entry whose id is not yet marked
uploaded — so video 1 ('stop-asking-easier-life') publishes on the first run,
then video 2, 3, 4, then loops back to video 1.
"""
import os
import json
import glob

from . import scripts as S


def published_topic_ids(output_dir: str) -> set[str]:
    """ids of topics that have an uploaded.txt marker in output/<run>."""
    ids = set()
    for meta_path in glob.glob(os.path.join(output_dir, "*", "metadata.json")):
        run_dir = os.path.dirname(meta_path)
        if not os.path.exists(os.path.join(run_dir, "uploaded.txt")):
            continue  # generated but never uploaded — doesn't count
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            tid = meta.get("topic_id")
            if tid:
                ids.add(tid)
        except Exception:
            continue
    return ids


"""Topic queue — pick the next unpublished video.

publish.yml commits output/<run_id>/metadata.json + uploaded.txt after each
successful upload (output/ is gitignored but these markers are force-added).
So on the next workflow run, checkout includes prior markers and we can tell
which topic_ids have already been published.

pick_topic() returns the first unpublished topic in this order:
  1. curated TOPICS (premium/scripts.py) — in order
  2. generated library (premium/topics_library.json) — in library order
  3. last resort: TOPICS[0] (only if both are fully published)

The publish workflow's "Ensure >= 2 unpublished topics" generate step keeps
the library stocked via NVIDIA NIM (llama / nemotron), so once the curated
set is published the queue serves FRESH generated scripts — it never loops
back to re-upload a duplicate. The library grows indefinitely (no expiration).
"""
import os
import json
import glob

from . import scripts as S


def published_topic_ids(output_dir: str) -> set[str]:
    """ids of topics that have an uploaded.txt marker in output/<run>."""
    ids = set()
    for meta_path in glob.glob(os.path.join(output_dir, "*", "metadata.json")):
        run_dir = os.path.dirname(meta_path)
        if not os.path.exists(os.path.join(run_dir, "uploaded.txt")):
            continue  # generated but never uploaded — doesn't count
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            tid = meta.get("topic_id")
            if tid:
                ids.add(tid)
        except Exception:
            continue
    return ids


def pick_topic(output_dir: str) -> dict:
    """Return the next topic to publish (first unpublished, curated then library)."""
    published = published_topic_ids(output_dir)
    # 1. curated TOPICS (in order)
    for topic in S.TOPICS:
        if topic["id"] not in published:
            return topic
    # 2. generated library (lazy import so importing queue doesn't load openai)
    try:
        from premium import generate as GEN
        for topic in GEN.load_library():
            if topic.get("id") not in published:
                print(f"[queue] picked generated topic from library: {topic['id']} "
                      f"— {topic.get('title', '')[:50]}")
                return topic
    except Exception as e:
        print(f"[queue] library unavailable ({str(e)[:80]}); falling back to TOPICS[0]")
    # 3. last resort
    print(f"[queue] all curated + library topics published; looping back to TOPICS[0] "
          f"(run the generate step to refill the library)")
    return S.TOPICS[0]
