"""Render stick-figure scene images — v7 with Openverse backgrounds.

Each frame: clean minimalist stick figure (IKEA style) on a free CC-licensed
background texture from Openverse. No zoom. Same character every frame.
"""
import os
import svg_poses
import config


def generate_image(pose_or_prompt: str, out_path: str, seed: int | None = None,
                   caption: str = "", scene_num: int = 0, scene_total: int = 0,
                   bg_search_term: str | None = None) -> str:
    """Render one frame to PNG. Returns out_path.

    Args:
        pose_or_prompt: pose name (e.g. "standing_tall") or string containing one
        out_path: where to save the PNG
        seed: ignored (kept for backwards compat)
        caption: short text shown on the right side of the frame
        scene_num: 1-indexed scene number (for counter display)
        scene_total: total scene count (for counter display)
        bg_search_term: optional Openverse search term for background texture
    """
    pose_name = _extract_pose_name(pose_or_prompt)
    bg_cache_dir = os.path.join(os.path.dirname(os.path.dirname(out_path)) or ".", "bg_cache")
    os.makedirs(bg_cache_dir, exist_ok=True)

    svg_poses.render_pose_to_png(
        pose_name=pose_name,
        out_path=out_path,
        caption=caption,
        brand_pill="DAILY DISCIPLINE",
        scene_num=scene_num,
        scene_total=scene_total or config.SCENES_PER_VIDEO,
        bg_search_term=bg_search_term,
        bg_cache_dir=bg_cache_dir,
    )
    print(f"[image_gen] rendered '{pose_name}' -> {os.path.basename(out_path)} ({os.path.getsize(out_path) // 1024} KB)")
    return out_path


def _extract_pose_name(text: str) -> str:
    if not text:
        return "standing_tall"
    text_lower = text.lower() if isinstance(text, str) else str(text).lower()
    for name in svg_poses.POSE_NAMES:
        if name in text_lower:
            return name
    return "standing_tall"


if __name__ == "__main__":
    os.makedirs("./output", exist_ok=True)
    generate_image(
        "standing_tall", "./output/test.png",
        caption="Discipline is choosing what you want most.",
        bg_search_term="concrete wall texture",
    )
    print("OK")
