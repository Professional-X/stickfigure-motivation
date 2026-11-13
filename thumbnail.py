"""Viral thumbnail generator — split-screen BEFORE/AFTER style.

Layout (1280x720, YouTube standard):
  - Left half: dark background (#0d0d0d), defeated stick figure, "BEFORE" label
  - Right half: bright cream background (#f4ede0), triumphant stick figure, "AFTER" label
  - Center overlay: the thumbnail_text in HUGE bold sans-serif (white fill +
    thick black outline so it's readable on both halves)
  - Bottom-right: channel handle (from CHANNEL_HANDLE env var)
  - Vertical divider line + arrow between the two halves

High-contrast, clickbait energy. Same minimalist stick-figure character as the
video (IKEA instruction style) so the thumbnail matches the content.

Renders SVG → PNG via rsvg-convert (already installed in the publish workflow).
"""
import os
import subprocess
import textwrap


# --- Layout constants (1280x720) ---
W, H = 1280, 720
HALF = W // 2  # 640
BG_LEFT = "#0d0d0d"   # near-black for BEFORE
BG_RIGHT = "#f4ede0"  # warm cream for AFTER
ACCENT_RED = "#d32f2f"
ACCENT_YELLOW = "#f5c518"
TEXT_OUTLINE = "#000000"
TEXT_FILL = "#ffffff"


def _stick_figure_svg(pose: str, cx: float, cy: float, scale: float,
                      stroke: str, stroke_width: float = 6) -> str:
    """Render a minimalist stick figure at (cx, cy) with given scale.

    pose is one of: defeated, triumphant, standing, meditating.
    The figure is drawn relative to (cx, cy) which is the HIP point.
    Head is above hip, legs below.

    scale=1.0 => head radius 22, body 120, arms 90, legs 110 (matches video).
    """
    s = scale
    # proportions (same as svg_poses for consistency)
    head_r = 22 * s
    body_len = 120 * s
    arm_len = 90 * s
    leg_len = 110 * s
    sw = stroke_width

    # key points (cx, cy = hip)
    hip_x, hip_y = cx, cy
    neck_x, neck_y = cx, cy - body_len
    head_cx, head_cy = neck_x, neck_y - head_r - 2
    shoulder_x, shoulder_y = neck_x, neck_y + 8 * s  # slight offset down from neck

    parts = []

    if pose == "defeated":
        # face down / collapsed: body horizontal, head down, arms limp
        # Draw as a slumped figure: spine curves forward, head dropped
        parts.append(f'<circle cx="{hip_x - 20*s}" cy="{hip_y - 10*s}" r="{head_r}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
        # curved spine (slumped)
        parts.append(f'<path d="M {hip_x - 20*s} {hip_y - 10*s + head_r} Q {hip_x} {hip_y + 20*s} {hip_x + 40*s} {hip_y}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        # limp arms hanging down
        parts.append(f'<line x1="{hip_x + 10*s}" y1="{hip_y - 30*s}" x2="{hip_x + 5*s}" y2="{hip_y + 50*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{hip_x + 30*s}" y1="{hip_y - 20*s}" x2="{hip_x + 35*s}" y2="{hip_y + 55*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        # bent legs (kneeling/sitting)
        parts.append(f'<line x1="{hip_x + 40*s}" y1="{hip_y}" x2="{hip_x + 70*s}" y2="{hip_y + 40*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{hip_x + 70*s}" y1="{hip_y + 40*s}" x2="{hip_x + 30*s}" y2="{hip_y + 50*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')

    elif pose == "triumphant":
        # arms raised overhead, standing tall, head up
        parts.append(f'<circle cx="{head_cx}" cy="{head_cy}" r="{head_r}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
        # spine
        parts.append(f'<line x1="{neck_x}" y1="{neck_y}" x2="{hip_x}" y2="{hip_y}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        # arms raised up in V
        parts.append(f'<line x1="{shoulder_x}" y1="{shoulder_y}" x2="{shoulder_x - arm_len*0.8}" y2="{shoulder_y - arm_len*0.9}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{shoulder_x}" y1="{shoulder_y}" x2="{shoulder_x + arm_len*0.8}" y2="{shoulder_y - arm_len*0.9}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        # legs apart (strong stance)
        parts.append(f'<line x1="{hip_x}" y1="{hip_y}" x2="{hip_x - leg_len*0.5}" y2="{hip_y + leg_len}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{hip_x}" y1="{hip_y}" x2="{hip_x + leg_len*0.5}" y2="{hip_y + leg_len}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')

    elif pose == "standing":
        # arms at sides, standing straight
        parts.append(f'<circle cx="{head_cx}" cy="{head_cy}" r="{head_r}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(f'<line x1="{neck_x}" y1="{neck_y}" x2="{hip_x}" y2="{hip_y}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{shoulder_x}" y1="{shoulder_y}" x2="{shoulder_x - arm_len}" y2="{shoulder_y + 20*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{shoulder_x}" y1="{shoulder_y}" x2="{shoulder_x + arm_len}" y2="{shoulder_y + 20*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{hip_x}" y1="{hip_y}" x2="{hip_x - leg_len*0.3}" y2="{hip_y + leg_len}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{hip_x}" y1="{hip_y}" x2="{hip_x + leg_len*0.3}" y2="{hip_y + leg_len}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')

    elif pose == "meditating":
        # sitting cross-legged, hands on knees
        parts.append(f'<circle cx="{head_cx}" cy="{head_cy}" r="{head_r}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(f'<line x1="{neck_x}" y1="{neck_y}" x2="{hip_x}" y2="{hip_y}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        # arms to knees
        parts.append(f'<line x1="{shoulder_x}" y1="{shoulder_y}" x2="{hip_x - arm_len*0.7}" y2="{hip_y + 10*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{shoulder_x}" y1="{shoulder_y}" x2="{hip_x + arm_len*0.7}" y2="{hip_y + 10*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        # crossed legs
        parts.append(f'<line x1="{hip_x}" y1="{hip_y}" x2="{hip_x - leg_len*0.6}" y2="{hip_y + 25*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{hip_x - leg_len*0.6}" y1="{hip_y + 25*s}" x2="{hip_x + leg_len*0.6}" y2="{hip_y + 25*s}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')
        parts.append(f'<line x1="{hip_x + leg_len*0.6}" y1="{hip_y + 25*s}" x2="{hip_x}" y2="{hip_y}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')

    return "\n".join(parts)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Wrap ALL-CAPS text into up to 2 lines for the thumbnail overlay."""
    words = text.upper().split()
    if not words:
        return [""]
    # greedy wrap into at most 2 lines
    lines = []
    current = words[0]
    for w in words[1:]:
        if len(current) + 1 + len(w) <= max_chars:
            current += " " + w
        else:
            lines.append(current)
            current = w
            if len(lines) == 1:
                # second line gets whatever remains
                pass
    lines.append(current)
    return lines[:2]  # max 2 lines


def build_thumbnail_svg(thumbnail_text: str, channel_handle: str = "",
                        before_pose: str = "defeated",
                        after_pose: str = "triumphant") -> str:
    """Build the full 1280x720 thumbnail SVG."""
    # Split background
    svg_parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']

    # left half (dark)
    svg_parts.append(f'<rect x="0" y="0" width="{HALF}" height="{H}" fill="{BG_LEFT}"/>')
    # right half (cream)
    svg_parts.append(f'<rect x="{HALF}" y="0" width="{HALF}" height="{H}" fill="{BG_RIGHT}"/>')

    # subtle red tint band on left for "danger/before"
    svg_parts.append(f'<rect x="0" y="0" width="{HALF}" height="{H}" fill="{ACCENT_RED}" opacity="0.15"/>')

    # vertical divider
    svg_parts.append(f'<rect x="{HALF-3}" y="0" width="6" height="{H}" fill="{ACCENT_YELLOW}"/>')

    # BEFORE label (top-left)
    svg_parts.append(f'<text x="40" y="70" font-family="DejaVu Sans, Arial, sans-serif" font-size="38" font-weight="bold" fill="{ACCENT_RED}" letter-spacing="4">BEFORE</text>')
    # AFTER label (top-right)
    svg_parts.append(f'<text x="{HALF+40}" y="70" font-family="DejaVu Sans, Arial, sans-serif" font-size="38" font-weight="bold" fill="#1a1a1a" letter-spacing="4">AFTER</text>')

    # defeated stick figure on left (muted red, smaller, lower)
    svg_parts.append(_stick_figure_svg(before_pose, cx=HALF//2, cy=H//2 + 60, scale=1.0,
                                       stroke=ACCENT_RED, stroke_width=7))
    # triumphant stick figure on right (bold black, bigger, higher)
    svg_parts.append(_stick_figure_svg(after_pose, cx=HALF + HALF//2, cy=H//2 + 40, scale=1.3,
                                       stroke="#0d0d0d", stroke_width=8))

    # arrow from left to right (yellow, pointing right) at center vertically
    arrow_y = H // 2
    svg_parts.append(f'<path d="M {HALF-60} {arrow_y} L {HALF+50} {arrow_y} L {HALF+30} {arrow_y-15} M {HALF+50} {arrow_y} L {HALF+30} {arrow_y+15}" fill="none" stroke="{ACCENT_YELLOW}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')

    # HUGE thumbnail text overlay (centered, white fill + black outline)
    # Wrap into up to 2 lines, ~10 chars per line for max readability
    lines = _wrap_text(thumbnail_text, max_chars=11)
    n_lines = len(lines)
    # font size: bigger if 1 line, smaller if 2 lines
    font_size = 110 if n_lines == 1 else 82
    # vertical centering
    total_h = n_lines * font_size * 1.05
    start_y = (H - total_h) // 2 + font_size
    for i, line in enumerate(lines):
        y = start_y + i * font_size * 1.05
        # paint-order: stroke fill => outline drawn first, fill on top
        svg_parts.append(
            f'<text x="{W//2}" y="{y}" font-family="DejaVu Sans, Arial, sans-serif" '
            f'font-size="{font_size}" font-weight="bold" text-anchor="middle" '
            f'fill="{TEXT_FILL}" stroke="{TEXT_OUTLINE}" stroke-width="{font_size//14}" '
            f'paint-order="stroke fill" letter-spacing="2">{line}</text>'
        )

    # channel handle bottom-right
    if channel_handle:
        handle = channel_handle if channel_handle.startswith("@") else "@" + channel_handle
        svg_parts.append(
            f'<text x="{W-20}" y="{H-25}" font-family="DejaVu Sans, Arial, sans-serif" '
            f'font-size="26" font-weight="bold" text-anchor="end" fill="#0d0d0d" '
            f'stroke="{TEXT_FILL}" stroke-width="3" paint-order="stroke fill" '
            f'letter-spacing="1">{handle}</text>'
        )

    # subtle red corner accent top-left for clickbait energy
    svg_parts.append(f'<rect x="0" y="0" width="180" height="8" fill="{ACCENT_RED}"/>')
    svg_parts.append(f'<rect x="0" y="0" width="8" height="180" fill="{ACCENT_RED}"/>')

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def render_thumbnail(thumbnail_text: str, out_path: str,
                     channel_handle: str = "",
                     before_pose: str = "defeated",
                     after_pose: str = "triumphant") -> str:
    """Build SVG + render to PNG. Returns out_path.

    Tries rsvg-convert first (installed in the publish workflow via librsvg2-bin,
    sharp text). Falls back to cairosvg (pure Python, available everywhere).
    """
    svg = build_thumbnail_svg(thumbnail_text, channel_handle, before_pose, after_pose)
    svg_path = out_path + ".svg"
    with open(svg_path, "w") as f:
        f.write(svg)

    # Try rsvg-convert first (sharper output, already in CI)
    try:
        result = subprocess.run(
            ["rsvg-convert", "-w", str(W), "-h", str(H), "-o", out_path, svg_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and os.path.exists(out_path):
            os.remove(svg_path)
            print(f"[thumbnail] rendered (rsvg-convert): {out_path} ({os.path.getsize(out_path) // 1024} KB)")
            return out_path
    except FileNotFoundError:
        pass  # fall through to cairosvg

    # Fallback: cairosvg (pure Python, works anywhere)
    try:
        import cairosvg
        cairosvg.svg2png(
            url=svg_path,
            write_to=out_path,
            output_width=W,
            output_height=H,
        )
        os.remove(svg_path)
        print(f"[thumbnail] rendered (cairosvg): {out_path} ({os.path.getsize(out_path) // 1024} KB)")
        return out_path
    except Exception as e:
        raise RuntimeError(f"thumbnail render failed (no rsvg-convert, no cairosvg): {e}")


if __name__ == "__main__":
    # smoke test — render a sample thumbnail
    import tempfile
    out = os.path.join(tempfile.gettempdir(), "thumb_test.png")
    render_thumbnail(
        thumbnail_text="5AM IS A LIE",
        channel_handle="DisciplineDaily",
        out_path=out,
    )
    print(f"saved: {out}")
