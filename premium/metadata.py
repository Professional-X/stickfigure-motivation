"""Build YouTube-ready metadata for a premium video."""
from . import music as M


def build_metadata(topic: dict, scenes: list[dict], total_duration: float,
                   music_attr: dict) -> dict:
    """Assemble title/description/tags with SEO packaging + music credit.

    music_attr comes from premium.music.ensure_music() (CC-BY attribution
    appended to the description; empty dict if a synthesized pad was used).
    """
    description = topic["description"] + M.attribution_line(music_attr)

    # round duration for logging
    mins = int(total_duration // 60)
    secs = int(round(total_duration - mins * 60))

    return {
        "topic_id": topic["id"],
        "category": topic["category"],
        "title": topic["title"],
        "description": description,
        "tags": topic["tags"],
        "hashtags": topic["hashtags"],
        "hook_line": topic["hook_line"],
        "recurring_phrase": topic["recurring_phrase"],
        "thumbnail_text": topic["thumbnail_text"],
        "duration_sec": round(total_duration, 1),
        "duration_label": f"{mins}:{secs:02d}",
        "scene_count": len(scenes),
        "music_track": music_attr.get("track", "(synthesized ambient pad)"),
        "category_id": "22",        # People & Blogs
        "privacy": "public",
        "is_self_rating": False,    # no kids content self-rating
    }
