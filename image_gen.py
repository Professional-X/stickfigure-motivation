"""Render stick-figure scene images — v5 clean-minimal design.

Each frame is a 1280x720 PNG with:
  - Pure white background
  - Stick figure (same character) on left, in a pose picked by the LLM
  - Caption text (the narration snippet) on the right in large bold type
  - Brand pill top-left, scene counter top-right
  - One accent color (deep red) for emphasis

This is the instagram-auto-poster design language applied to the stick-figure
motivation channel. No AI image gen = same character every frame.
"""
import os
import svg_poses
import config


def generate_image(pose_or_prompt: str, out_path: str, seed: int | None = None,
                   caption: str = "", scene_num: int = 0, scene_total: int = 0) -> str:
    """Render one frame to PNG. Returns out_path.

    Args:
        pose_or_prompt: pose name (e.g. "standing_tall") or string containing one
        out_path: where to save the PNG
        seed: ignored (kept for backwards compat)
        caption: short text shown on the right side of the frame
        scene_num: 1-indexed scene number (for counter display)
        scene_total: total scene count (for counter display)
    """
    pose_name = _extract_pose_name(pose_or_prompt)
    svg_poses.render_pose_to_png(
        pose_name=pose_name,
        out_path=out_path,
        caption=caption,
        brand_pill="DAILY DISCIPLINE",
        scene_num=scene_num,
        scene_total=scene_total or config.SCENES_PER_VIDEO,
    )
    print(f"[image_gen] rendered '{pose_name}' -> {os.path.basename(out_path)} ({os.path.getsize(out_path) // 1024} KB)")
    return out_path


def _extract_pose_name(text: str) -> str:
    """Find a pose name in the input string."""
    if not text:
        return "standing_tall"
    text_lower = text.lower() if isinstance(text, str) else str(text).lower()
    for name in svg_poses.POSE_NAMES:
        if name in text_lower:
            return name
    return "standing_tall"


if __name__ == "__main__":
    os.makedirs("./output", exist_ok=True)
    generate_image("standing_tall", "./output/test.png", caption="Discipline is choosing what you want most.")
    print("OK")
