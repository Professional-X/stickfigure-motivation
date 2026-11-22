"""Ensure the premium topic library has >= 2 unpublished topics.

Called by publish.yml BEFORE the main pipeline step. Generates fresh topics via
NVIDIA NIM (nvidia/nemotron-3-ultra-550b-a55b) if the library is low, appending
them to premium/topics_library.json. The next step commits the library; then
pipeline_premium.py's queue.pick_topic() serves the first unpublished generated
topic — so the channel always has fresh content and never loops back to
re-uploading a duplicate curated topic.

If NVIDIA_API_KEY is missing or generation fails, this is a no-op and the queue
falls back to the curated TOPICS (graceful degradation — the pipeline never
blocks on LLM availability).
"""
import sys
sys.path.insert(0, ".")
import config
from premium import queue as Q, generate as GEN

published = Q.published_topic_ids(config.OUTPUT_DIR)
n = GEN.ensure_unpublished(published, min_count=2)
pending = GEN.unpublished_library_topics(published)
print(f"[ensure_library] generated {n} new topic(s); "
      f"library now has {len(pending)} unpublished topic(s) ready")
if pending:
    print(f"[ensure_library] next topic the queue will serve: "
          f"{pending[0]['id']} — {pending[0].get('title', '')[:50]}")
