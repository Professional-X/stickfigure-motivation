"""Deterministic stick-figure frame renderer — clean-minimal design system.

Inspired by the instagram-auto-poster design language:
  * Pure white canvas (1080x1920 vertical OR 1280x720 horizontal)
  * One accent color (deep red #C8102E — discipline/brutal vibe)
  * Big bold typography for short caption per scene
  * Stick figure with thick clean lines, slightly hand-drawn
  * Generous whitespace, no gradients, no clutter
  * Brand pill in corner + scene counter

Two render modes:
  - 'vertical' (1080x1920) for YouTube Shorts / Reels
  - 'horizontal' (1280x720) for long-form YouTube

The stick figure remains the SAME character in every frame — only the pose
and the caption text change. This is the visual consistency fix.
"""
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
import config


# ============================================================
# Design tokens — clean-minimal system
# ============================================================
# Use vertical (1080x1920) for Shorts, horizontal (1280x720) for long-form
VERTICAL = (1080, 1920)
HORIZONTAL = (1280, 720)
CANVAS = HORIZONTAL  # default — long-form YouTube

# Colors — pure white background + one accent color
BG = (255, 255, 255)
INK = (11, 11, 18)            # near-black for primary text
MUTED = (107, 111, 118)       # secondary text
ACCENT = (200, 16, 46)        # deep red — #C8102E
ACCENT_TINT = (255, 235, 238) # very light red for pill backgrounds
LINE_COLOR = (11, 11, 18)     # stick figure stroke
LINE_WIDTH = 6                # thicker = cleaner, more "drawn"

# Typography
# We try common system fonts; fall back to default if not available
FONT_DISPLAY = None  # set at runtime
FONT_BODY = None
FONT_MONO = None

# Layout (horizontal 1280x720)
MARGIN = 80
CONTENT_W = CANVAS[0] - 2 * MARGIN


def _load_fonts():
    """Try to load nice fonts; fall back to PIL default if unavailable."""
    global FONT_DISPLAY, FONT_BODY, FONT_MONO
    font_candidates = {
        "display": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ],
        "body": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ],
        "mono": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        ],
    }
    loaded = {}
    for key, paths in font_candidates.items():
        for p in paths:
            if os.path.exists(p):
                loaded[key] = p
                break
    FONT_DISPLAY = loaded.get("display")
    FONT_BODY = loaded.get("body")
    FONT_MONO = loaded.get("mono")


def _font(size: int, bold: bool = False, mono: bool = False):
    """Get a font at the requested size."""
    if FONT_MONO is None:
        _load_fonts()
    if mono and FONT_MONO:
        return ImageFont.truetype(FONT_MONO, size)
    if bold and FONT_DISPLAY:
        return ImageFont.truetype(FONT_DISPLAY, size)
    if FONT_BODY:
        return ImageFont.truetype(FONT_BODY, size)
    return ImageFont.load_default()


def _wrap_text(text: str, font, draw: ImageDraw.ImageDraw, max_w: int) -> list[str]:
    """Greedy word wrap. Returns list of lines."""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


# ============================================================
# Stick-figure drawing primitives
# ============================================================
def _line(draw, x1, y1, x2, y2, width=LINE_WIDTH):
    draw.line([(x1, y1), (x2, y2)], fill=LINE_COLOR, width=width, joint="curve")


def _path(draw, points, width=LINE_WIDTH):
    """Draw a connected polyline through points."""
    if len(points) < 2:
        return
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=LINE_COLOR, width=width, joint="curve")


def _circle(draw, cx, cy, r, width=LINE_WIDTH):
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, outline=LINE_COLOR, width=width)


# ============================================================
# Pose functions — each draws the character in one position
# Coordinate system: (cx, cy) = head center. Body extends downward.
# ============================================================

def pose_standing_tall(draw, cx, cy):
    """Standing upright, arms at sides."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 80, cx - 50, cy + 180)
    _line(draw, cx + 4, cy + 80, cx + 50, cy + 180)
    _line(draw, cx, cy + 200, cx - 35, cy + 320)
    _line(draw, cx, cy + 200, cx + 35, cy + 320)


def pose_walking(draw, cx, cy):
    """Mid-stride, leaning forward."""
    _circle(draw, cx, cy, 36)
    _path(draw, [(cx, cy + 36), (cx + 10, cy + 120), (cx + 6, cy + 200)])
    _line(draw, cx - 4, cy + 85, cx + 30, cy + 150)
    _line(draw, cx + 4, cy + 85, cx - 35, cy + 160)
    _path(draw, [(cx + 6, cy + 200), (cx - 25, cy + 270), (cx - 60, cy + 280)])
    _path(draw, [(cx + 6, cy + 200), (cx + 35, cy + 275), (cx + 60, cy + 305)])


def pose_running(draw, cx, cy):
    """Running hard, body tilted."""
    _circle(draw, cx, cy, 36)
    _path(draw, [(cx, cy + 36), (cx + 18, cy + 115), (cx + 22, cy + 195)])
    _line(draw, cx - 4, cy + 85, cx - 40, cy + 125)
    _line(draw, cx + 4, cy + 85, cx + 50, cy + 145)
    _path(draw, [(cx + 22, cy + 195), (cx - 30, cy + 240), (cx - 70, cy + 225)])
    _path(draw, [(cx + 22, cy + 195), (cx + 45, cy + 270), (cx + 75, cy + 305)])


def pose_sitting_ground(draw, cx, cy):
    """Sitting on ground, knees up."""
    _circle(draw, cx, cy + 45, 36)
    _path(draw, [(cx, cy + 81), (cx + 6, cy + 120), (cx + 10, cy + 180)])
    _path(draw, [(cx - 4, cy + 90), (cx - 35, cy + 150), (cx - 60, cy + 200)])
    _path(draw, [(cx + 4, cy + 90), (cx + 35, cy + 150), (cx + 60, cy + 200)])
    _path(draw, [(cx + 10, cy + 180), (cx - 35, cy + 245), (cx - 60, cy + 200)])
    _path(draw, [(cx + 10, cy + 180), (cx + 45, cy + 245), (cx + 60, cy + 200)])


def pose_kneeling(draw, cx, cy):
    """One knee on ground, head bowed."""
    _circle(draw, cx, cy + 35, 36)
    _path(draw, [(cx, cy + 71), (cx + 4, cy + 110), (cx + 6, cy + 195)])
    _line(draw, cx - 4, cy + 90, cx - 35, cy + 195)
    _line(draw, cx + 4, cy + 90, cx + 35, cy + 195)
    _path(draw, [(cx + 6, cy + 195), (cx - 28, cy + 285), (cx - 28, cy + 320)])
    _path(draw, [(cx + 6, cy + 195), (cx + 45, cy + 260), (cx + 80, cy + 270)])


def pose_looking_up(draw, cx, cy):
    """Standing, head tilted back."""
    _circle(draw, cx, cy - 10, 36)
    _line(draw, cx, cy + 26, cx, cy + 200)
    _line(draw, cx - 4, cy + 80, cx - 38, cy + 180)
    _line(draw, cx + 4, cy + 80, cx + 38, cy + 180)
    _line(draw, cx, cy + 200, cx - 30, cy + 320)
    _line(draw, cx, cy + 200, cx + 30, cy + 320)


def pose_climbing(draw, cx, cy):
    """Reaching up, climbing."""
    _circle(draw, cx, cy, 36)
    _path(draw, [(cx, cy + 36), (cx + 6, cy + 115), (cx, cy + 200)])
    _line(draw, cx - 4, cy + 70, cx - 35, cy + 10)
    _line(draw, cx + 4, cy + 85, cx + 28, cy + 145)
    _path(draw, [(cx, cy + 200), (cx - 35, cy + 270), (cx - 55, cy + 280)])
    _path(draw, [(cx, cy + 200), (cx + 25, cy + 260), (cx + 50, cy + 305)])


def pose_pointing_forward(draw, cx, cy):
    """One arm extended forward — direction."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 35, cy + 180)
    _line(draw, cx + 4, cy + 85, cx + 90, cy + 100)
    _line(draw, cx, cy + 200, cx - 30, cy + 320)
    _line(draw, cx, cy + 200, cx + 30, cy + 320)


def pose_pushing_boulder(draw, cx, cy):
    """Leaning forward, pushing a boulder."""
    _circle(draw, cx, cy, 36)
    _path(draw, [(cx, cy + 36), (cx + 22, cy + 115), (cx + 28, cy + 195)])
    _path(draw, [(cx - 4, cy + 85), (cx + 55, cy + 110), (cx + 90, cy + 115)])
    _path(draw, [(cx + 4, cy + 85), (cx + 60, cy + 125), (cx + 95, cy + 130)])
    _path(draw, [(cx + 28, cy + 195), (cx - 12, cy + 260), (cx - 35, cy + 305)])
    _path(draw, [(cx + 28, cy + 195), (cx + 35, cy + 265), (cx + 25, cy + 315)])
    # boulder
    _circle(draw, cx + 150, cy + 145, 60)


def pose_carrying_load(draw, cx, cy):
    """Walking with a heavy load on back."""
    _circle(draw, cx, cy, 36)
    _path(draw, [(cx, cy + 36), (cx + 12, cy + 115), (cx + 10, cy + 200)])
    _line(draw, cx - 4, cy + 85, cx - 22, cy + 145)
    _line(draw, cx + 4, cy + 85, cx + 22, cy + 145)
    _path(draw, [(cx + 10, cy + 200), (cx - 22, cy + 270), (cx - 40, cy + 315)])
    _path(draw, [(cx + 10, cy + 200), (cx + 28, cy + 265), (cx + 45, cy + 305)])
    # the load — square block on shoulders
    draw.rectangle([cx - 55, cy - 35, cx + 10, cy + 30], outline=LINE_COLOR, width=LINE_WIDTH)


def pose_standing_alone_hill(draw, cx, cy):
    """Standing on a hill."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 40, cy + 180)
    _line(draw, cx + 4, cy + 85, cx + 40, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # hill — gentle curve
    draw.line([(60, 670), (cx, 540), (1220, 670)], fill=MUTED, width=3, joint="curve")


def pose_facing_wall(draw, cx, cy):
    """Facing a wall."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 90, cx - 55, cy + 100)
    _line(draw, cx + 4, cy + 90, cx - 55, cy + 115)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # wall on left
    draw.line([(cx - 80, cy - 90), (cx - 80, cy + 320)], fill=LINE_COLOR, width=8)


def pose_arms_crossed(draw, cx, cy):
    """Standing, arms crossed — defiance."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 90, cx + 35, cy + 125)
    _line(draw, cx + 4, cy + 90, cx - 35, cy + 125)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)


def pose_falling(draw, cx, cy):
    """Mid-fall, horizontal."""
    _circle(draw, cx + 90, cy + 115, 36)
    _line(draw, cx + 54, cy + 115, cx - 60, cy + 105)
    _line(draw, cx + 35, cy + 110, cx + 35, cy + 60)
    _line(draw, cx + 10, cy + 110, cx + 10, cy + 165)
    _line(draw, cx - 35, cy + 105, cx - 35, cy + 60)
    _line(draw, cx - 60, cy + 105, cx - 60, cy + 160)


def pose_rising_up(draw, cx, cy):
    """Halfway up from ground."""
    _circle(draw, cx, cy + 70, 36)
    _path(draw, [(cx, cy + 106), (cx + 12, cy + 170), (cx + 18, cy + 200)])
    _line(draw, cx - 4, cy + 115, cx - 55, cy + 225)
    _line(draw, cx + 4, cy + 115, cx + 45, cy + 145)
    _path(draw, [(cx + 18, cy + 200), (cx - 22, cy + 285), (cx - 22, cy + 320)])
    _path(draw, [(cx + 18, cy + 200), (cx + 55, cy + 260), (cx + 80, cy + 315)])


def pose_fist_clenched(draw, cx, cy):
    """Standing, fists clenched — resolve."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _path(draw, [(cx - 4, cy + 85), (cx - 40, cy + 145), (cx - 35, cy + 185)])
    _path(draw, [(cx + 4, cy + 85), (cx + 40, cy + 145), (cx + 35, cy + 185)])
    _line(draw, cx, cy + 200, cx - 35, cy + 320)
    _line(draw, cx, cy + 200, cx + 35, cy + 320)
    _circle(draw, cx - 35, cy + 195, 10)
    _circle(draw, cx + 35, cy + 195, 10)


def pose_meditating(draw, cx, cy):
    """Cross-legged sitting."""
    _circle(draw, cx, cy + 20, 36)
    _path(draw, [(cx, cy + 56), (cx + 4, cy + 100), (cx + 6, cy + 165)])
    _line(draw, cx - 4, cy + 90, cx - 55, cy + 195)
    _line(draw, cx + 4, cy + 90, cx + 55, cy + 195)
    _path(draw, [(cx + 6, cy + 165), (cx - 55, cy + 220), (cx + 12, cy + 245)])
    _path(draw, [(cx + 6, cy + 165), (cx + 55, cy + 220), (cx - 12, cy + 245)])


def pose_writing(draw, cx, cy):
    """Sitting, writing in book."""
    _circle(draw, cx, cy + 45, 36)
    _path(draw, [(cx, cy + 81), (cx + 10, cy + 115), (cx + 12, cy + 165)])
    _line(draw, cx - 4, cy + 90, cx - 35, cy + 195)
    _line(draw, cx + 4, cy + 90, cx + 35, cy + 195)
    _path(draw, [(cx + 12, cy + 165), (cx - 45, cy + 230), (cx + 5, cy + 250)])
    _path(draw, [(cx + 12, cy + 165), (cx + 45, cy + 230), (cx - 5, cy + 250)])
    # book on lap
    draw.rectangle([cx - 45, cy + 185, cx + 45, cy + 210], outline=LINE_COLOR, width=3)


def pose_standing_window(draw, cx, cy):
    """Standing by a window."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 45, cy + 55)
    _line(draw, cx + 4, cy + 85, cx + 35, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # window on left
    draw.rectangle([cx - 140, cy - 90, cx - 30, cy + 115], outline=LINE_COLOR, width=3)
    draw.line([(cx - 85, cy - 90), (cx - 85, cy + 115)], fill=LINE_COLOR, width=2)


def pose_staring_mirror(draw, cx, cy):
    """Facing a mirror."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _path(draw, [(cx - 4, cy + 85), (cx - 35, cy + 70), (cx - 28, cy + 35)])
    _path(draw, [(cx + 4, cy + 85), (cx + 35, cy + 70), (cx + 28, cy + 35)])
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # mirror on right
    draw.rectangle([cx + 90, cy - 70, cx + 180, cy + 175], outline=LINE_COLOR, width=3)


def pose_walking_alone_path(draw, cx, cy):
    """Walking on a path."""
    _circle(draw, cx, cy, 36)
    _path(draw, [(cx, cy + 36), (cx + 10, cy + 115), (cx + 6, cy + 200)])
    _line(draw, cx - 4, cy + 85, cx + 30, cy + 150)
    _line(draw, cx + 4, cy + 85, cx - 35, cy + 160)
    _path(draw, [(cx + 6, cy + 200), (cx - 25, cy + 270), (cx - 60, cy + 285)])
    _path(draw, [(cx + 6, cy + 200), (cx + 35, cy + 275), (cx + 60, cy + 305)])
    # path
    draw.line([(60, 690), (cx, 580), (1220, 510)], fill=MUTED, width=3, joint="curve")


def pose_bowing_head(draw, cx, cy):
    """Standing, head bowed."""
    _circle(draw, cx, cy + 35, 36)
    _path(draw, [(cx, cy + 71), (cx + 6, cy + 115), (cx, cy + 200)])
    _line(draw, cx - 4, cy + 85, cx - 35, cy + 180)
    _line(draw, cx + 4, cy + 85, cx + 35, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)


def pose_sun_rising(draw, cx, cy):
    """Standing, sun rising behind."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 35, cy + 180)
    _line(draw, cx + 4, cy + 85, cx + 35, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # sun on right
    _circle(draw, cx + 280, cy + 100, 55, width=4)
    draw.line([(60, 620), (1220, 620)], fill=MUTED, width=3)


def pose_empty_chair(draw, cx, cy):
    """Empty chair — absence."""
    # No character. Just the chair.
    draw.rectangle([cx - 55, cy + 145, cx + 55, cy + 165], outline=LINE_COLOR, width=LINE_WIDTH)
    draw.line([(cx - 55, cy + 145), (cx - 55, cy + 25)], fill=LINE_COLOR, width=LINE_WIDTH)
    draw.line([(cx + 55, cy + 165), (cx + 55, cy + 280)], fill=LINE_COLOR, width=LINE_WIDTH)
    draw.line([(cx - 55, cy + 165), (cx - 55, cy + 280)], fill=LINE_COLOR, width=LINE_WIDTH)


def pose_clock_waiting(draw, cx, cy):
    """Looking at a clock."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 55, cy + 90)
    _line(draw, cx + 4, cy + 85, cx + 35, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # clock on left
    _circle(draw, cx - 145, cy - 45, 50, width=4)
    draw.line([(cx - 145, cy - 45), (cx - 145, cy - 80)], fill=LINE_COLOR, width=4)
    draw.line([(cx - 145, cy - 45), (cx - 115, cy - 45)], fill=LINE_COLOR, width=4)


def pose_holding_light(draw, cx, cy):
    """Holding up a small light."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 80, cx - 22, cy + 20)
    _line(draw, cx + 4, cy + 85, cx + 35, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # light above hand
    _circle(draw, cx - 22, cy - 5, 18, width=4)


def pose_standing_mountain_top(draw, cx, cy):
    """On a mountain peak."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 40, cy + 180)
    _line(draw, cx + 4, cy + 85, cx + 40, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # mountain peak silhouette
    draw.line([(40, 690), (cx, 540), (1240, 690)], fill=MUTED, width=4, joint="curve")


def pose_face_down(draw, cx, cy):
    """Lying face down."""
    _circle(draw, cx - 110, cy + 205, 36)
    _line(draw, cx - 74, cy + 205, cx + 90, cy + 210)
    _line(draw, cx - 65, cy + 210, cx - 65, cy + 250)
    _line(draw, cx - 30, cy + 210, cx - 30, cy + 245)
    _line(draw, cx + 45, cy + 210, cx + 45, cy + 250)
    _line(draw, cx + 80, cy + 210, cx + 80, cy + 245)
    # ground line
    draw.line([(40, cy + 260), (1240, cy + 260)], fill=LINE_COLOR, width=4)


def pose_two_paths(draw, cx, cy):
    """At a fork in the road."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 55, cy + 95)
    _line(draw, cx + 4, cy + 85, cx + 55, cy + 95)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # two diverging paths
    draw.line([(cx, 690), (cx - 280, 530)], fill=MUTED, width=3)
    draw.line([(cx, 690), (cx + 280, 530)], fill=MUTED, width=3)


def pose_arms_raised(draw, cx, cy):
    """Both arms raised up."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 80, cx - 35, cy + 15)
    _line(draw, cx + 4, cy + 80, cx + 35, cy + 15)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)


def pose_dark_room_alone(draw, cx, cy):
    """Sitting alone in a dark room with a sliver of light."""
    _circle(draw, cx, cy + 70, 36)
    _path(draw, [(cx, cy + 106), (cx + 6, cy + 170), (cx + 10, cy + 200)])
    _line(draw, cx - 4, cy + 115, cx - 35, cy + 195)
    _line(draw, cx + 4, cy + 115, cx + 35, cy + 195)
    _path(draw, [(cx + 10, cy + 200), (cx - 40, cy + 255), (cx - 40, cy + 305)])
    _path(draw, [(cx + 10, cy + 200), (cx + 40, cy + 255), (cx + 40, cy + 305)])
    # window with light beam
    draw.rectangle([cx + 220, cy - 50, cx + 310, cy + 120], outline=LINE_COLOR, width=3)
    draw.line([(cx + 265, cy + 100), (cx + 100, cy + 220)], fill=MUTED, width=2)


def pose_handshake_self(draw, cx, cy):
    """Hands clasped together — commitment to self."""
    _circle(draw, cx, cy, 36)
    _line(draw, cx, cy + 36, cx, cy + 200)
    _path(draw, [(cx - 4, cy + 85), (cx + 6, cy + 125)])
    _path(draw, [(cx + 4, cy + 85), (cx - 6, cy + 125)])
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)


def pose_looking_back(draw, cx, cy):
    """Looking behind — regret."""
    _circle(draw, cx - 18, cy, 36)  # head turned
    _line(draw, cx, cy + 36, cx, cy + 200)
    _line(draw, cx - 4, cy + 85, cx - 35, cy + 180)
    _line(draw, cx + 4, cy + 85, cx + 35, cy + 180)
    _line(draw, cx, cy + 200, cx - 28, cy + 320)
    _line(draw, cx, cy + 200, cx + 28, cy + 320)
    # faint footprints trailing behind
    for fx, fy in [(cx - 140, 660), (cx - 180, 680), (cx - 220, 650)]:
        _circle(draw, fx, fy, 7, width=3)


# ============================================================
# Pose registry
# ============================================================

POSE_REGISTRY = {
    "standing_tall": pose_standing_tall,
    "walking": pose_walking,
    "running": pose_running,
    "sitting_ground": pose_sitting_ground,
    "kneeling": pose_kneeling,
    "looking_up": pose_looking_up,
    "climbing": pose_climbing,
    "pointing_forward": pose_pointing_forward,
    "pushing_boulder": pose_pushing_boulder,
    "carrying_load": pose_carrying_load,
    "standing_alone_hill": pose_standing_alone_hill,
    "facing_wall": pose_facing_wall,
    "arms_crossed": pose_arms_crossed,
    "falling": pose_falling,
    "rising_up": pose_rising_up,
    "fist_clenched": pose_fist_clenched,
    "meditating": pose_meditating,
    "writing": pose_writing,
    "standing_window": pose_standing_window,
    "staring_mirror": pose_staring_mirror,
    "walking_alone_path": pose_walking_alone_path,
    "bowing_head": pose_bowing_head,
    "sun_rising": pose_sun_rising,
    "empty_chair": pose_empty_chair,
    "clock_waiting": pose_clock_waiting,
    "holding_light": pose_holding_light,
    "standing_mountain_top": pose_standing_mountain_top,
    "face_down": pose_face_down,
    "two_paths": pose_two_paths,
    "arms_raised": pose_arms_raised,
    "dark_room_alone": pose_dark_room_alone,
    "handshake_self": pose_handshake_self,
    "looking_back": pose_looking_back,
}

POSE_NAMES = list(POSE_REGISTRY.keys())


def render_pose_to_png(
    pose_name: str,
    out_path: str,
    caption: str = "",
    brand_pill: str = "DAILY DISCIPLINE",
    scene_num: int = 0,
    scene_total: int = 25,
) -> str:
    """Render one frame to PNG. Returns out_path.

    Layout (horizontal 1280x720):
      - Brand pill top-left, scene counter top-right
      - Stick figure centered (left half)
      - Caption text on right half (wrapped, large bold)
      - Accent bar under pill
    """
    if pose_name not in POSE_REGISTRY:
        pose_name = "standing_tall"

    img = Image.new("RGB", CANVAS, BG)
    draw = ImageDraw.Draw(img)

    # --- Top: brand pill (left) ---
    pill_text = brand_pill
    pill_font = _font(22, bold=True, mono=True)
    pill_w = int(draw.textlength(pill_text, font=pill_font)) + 32
    pill_h = 22 + 18
    draw.rounded_rectangle(
        [MARGIN, 50, MARGIN + pill_w, 50 + pill_h],
        radius=pill_h // 2, fill=ACCENT_TINT,
    )
    draw.text((MARGIN + 16, 53), pill_text, font=pill_font, fill=ACCENT)

    # --- Top: scene counter (right) ---
    counter = f"{scene_num:02d} / {scene_total:02d}"
    c_font = _font(22, bold=True, mono=True)
    cw = int(draw.textlength(counter, font=c_font))
    draw.text((CANVAS[0] - MARGIN - cw, 53), counter, font=c_font, fill=MUTED)

    # --- Center: stick figure on left half ---
    pose_func = POSE_REGISTRY[pose_name]
    fig_cx = CANVAS[0] // 4 + 30  # left quarter
    fig_cy = 220  # head center
    # The pose functions draw directly on `draw`
    pose_func(draw, fig_cx, fig_cy)

    # --- Right half: caption text ---
    if caption:
        # Truncate to ~80 chars and wrap
        snippet = caption[:120]
        cap_font = _font(46, bold=True)
        max_w = CANVAS[0] // 2 - MARGIN - 40
        lines = _wrap_text(snippet, cap_font, draw, max_w)
        # Vertical center the text block
        line_h = int(46 * 1.18)
        block_h = line_h * len(lines)
        start_y = (CANVAS[1] - block_h) // 2
        right_x = CANVAS[0] // 2 + 20
        for i, line in enumerate(lines):
            draw.text((right_x, start_y + i * line_h), line, font=cap_font, fill=INK)

        # Accent bar under caption
        bar_y = start_y + block_h + 30
        draw.rounded_rectangle(
            [right_x, bar_y, right_x + 80, bar_y + 6],
            radius=3, fill=ACCENT,
        )

    img.save(out_path, "PNG", optimize=True)
    return out_path


def render_svg(pose_name: str, scene_text: str = "") -> str:
    """Backwards-compat: returns SVG markup (caller saves to file).

    NOTE: We now render directly to PNG via render_pose_to_png. This function
    exists only so image_gen.py's old code path doesn't break. New code should
    call render_pose_to_png instead.
    """
    # Render to a temp PNG and return its path wrapped in an SVG <image> tag.
    # This is a hack for backwards compat — most callers go through
    # render_pose_to_png directly now.
    import tempfile, base64
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    render_pose_to_png(pose_name, tmp.name, caption=scene_text)
    with open(tmp.name, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    os.remove(tmp.name)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS[0]}" height="{CANVAS[1]}">'
        f'<image href="data:image/png;base64,{b64}" width="{CANVAS[0]}" height="{CANVAS[1]}"/>'
        f'</svg>'
    )


def svg_to_png(svg_path: str, png_path: str, width: int = None, height: int = None):
    """Backwards-compat: convert SVG (containing embedded PNG) back to PNG.

    Just opens the embedded PNG and re-saves it.
    """
    # For backwards compat — the SVG contains a base64 PNG
    import base64, re
    with open(svg_path, "r") as f:
        svg = f.read()
    m = re.search(r'base64,([A-Za-z0-9+/=]+)', svg)
    if m:
        with open(png_path, "wb") as f:
            f.write(base64.b64decode(m.group(1)))
    else:
        # Fallback: render directly
        render_pose_to_png("standing_tall", png_path)


if __name__ == "__main__":
    os.makedirs("/tmp/poses_v2", exist_ok=True)
    test_captions = [
        "Discipline is choosing what you want most over what you want now.",
        "The body screams stop. The mind agrees. You ignore both.",
        "Walk alone. The path narrows. Most fall off.",
        "Get back up.",
        "The morning is cold. The work is hard. Begin anyway.",
        "Years pass. You are unrecognizable.",
    ]
    for i, name in enumerate(POSE_NAMES[:6]):
        out = f"/tmp/poses_v2/{name}.png"
        render_pose_to_png(
            name, out,
            caption=test_captions[i % len(test_captions)],
            scene_num=i + 1, scene_total=25,
        )
        print(f"  ✓ {name}")
    print(f"\nRendered 6 test poses to /tmp/poses_v2/")
