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


def pick_topic(output_dir: str) -> dict:
    """Return the next topic to publish (first unpublished, in TOPICS order)."""
    published = published_topic_ids(output_dir)
    for topic in S.TOPICS:
        if topic["id"] not in published:
            return topic
    # all published — loop back to the first
    print(f"[queue] all {len(S.TOPICS)} topics published; looping back to #1")
    return S.TOPICS[0]
