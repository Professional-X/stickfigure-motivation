"""Render stick-figure scene images.

v4 architecture: instead of generating AI images (which can't keep a character
consistent across 25 frames), we use a hand-crafted SVG pose library. Each scene
picks a pose from svg_poses.py, and we render it deterministically.

This means:
- No API calls, no rate limits, no flaky providers
- Same character every frame, every video
- True minimalist line art (not AI's interpretation of minimalist)
- ~2 seconds to render all 25 scenes (vs 20+ minutes with Pollinations)
- $0 cost, fully offline-capable

The image_prompt field from script_gen.py is now used to PICK a pose from the
library — the LLM is told to choose a pose name from a known list.
"""
import os
import re
import svg_poses
import config


def generate_image(pose_or_prompt: str, out_path: str, seed: int | None = None) -> str:
    """Generate one image and save to out_path. Returns out_path.

    The first argument can be:
    - A pose name from svg_poses.POSE_REGISTRY (e.g. "standing_tall")
    - A longer prompt containing a pose name (we extract it)
    - Any other string — we fall back to a default pose
    """
    pose_name = _extract_pose_name(pose_or_prompt)

    # Render SVG
    svg = svg_poses.render_svg(pose_name, scene_text="")
    # Save SVG alongside PNG (useful for debugging)
    svg_path = out_path.replace(".png", ".svg")
    with open(svg_path, "w") as f:
        f.write(svg)

    # Convert to PNG
    svg_poses.svg_to_png(svg_path, out_path, width=config.IMAGE_WIDTH, height=config.IMAGE_HEIGHT)

    # Cleanup SVG (optional — keep for debugging by removing this line)
    # os.remove(svg_path)

    print(f"[image_gen] rendered pose '{pose_name}' -> {out_path} ({os.path.getsize(out_path) // 1024} KB)")
    return out_path


def _extract_pose_name(text: str) -> str:
    """Extract a pose name from the LLM's image_prompt field.

    The LLM is told to use a pose name verbatim from svg_poses.POSE_REGISTRY.
    If it follows instructions, the text will contain the pose name. We search
    for any known pose name in the text and use the first match.

    If no match, return a default ('standing_tall').
    """
    if not text:
        return "standing_tall"

    text_lower = text.lower()
    for name in svg_poses.POSE_NAMES:
        if name in text_lower:
            return name

    # No match — return default
    print(f"[image_gen] WARNING: no pose name found in prompt: '{text[:80]}...'. Using 'standing_tall'.")
    return "standing_tall"


if __name__ == "__main__":
    os.makedirs("./output", exist_ok=True)
    # Test rendering each pose
    for name in svg_poses.POSE_NAMES[:5]:
        generate_image(name, f"./output/test_{name}.png")
    print("OK")
