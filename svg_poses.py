"""Deterministic stick-figure frame renderer — clean-minimal design system v6.

v6 fixes: stick figures completely redrawn for perfectionist-quality:
  * Smooth Bezier curves for spine (natural S-curve, not straight lines)
  * Rounded line joints (no sharp corners)
  * Small filled circles at hands and feet (clean termination, looks intentional)
  * Better proportions: head 1/8 of body height (was 1/10)
  * Thicker stroke (8px) for confident, bold lines
  * Smoothed arm/leg curves via quadratic Beziers

Inspired by the instagram-auto-poster design language:
  * Pure white canvas (1280x720 horizontal)
  * One accent color (deep red #C8102E — discipline/brutal vibe)
  * Big bold typography for short caption per scene
  * Generous whitespace, no gradients, no clutter
  * Brand pill in corner + scene counter
"""
import os
import textwrap
import math
from PIL import Image, ImageDraw, ImageFont
import config


# ============================================================
# Design tokens
# ============================================================
CANVAS = (1280, 720)

# Colors
BG = (255, 255, 255)
INK = (11, 11, 18)
MUTED = (107, 111, 118)
ACCENT = (200, 16, 46)         # deep red
ACCENT_TINT = (255, 235, 238)
LINE_COLOR = (11, 11, 18)
LINE_WIDTH = 8                 # thicker = bolder, cleaner
JOINT_RADIUS = 6              # small circles at hands/feet
HEAD_RADIUS = 42              # bigger head

# Layout
MARGIN = 80
CONTENT_W = CANVAS[0] - 2 * MARGIN

FONT_DISPLAY = None
FONT_BODY = None
FONT_MONO = None


def _load_fonts():
    global FONT_DISPLAY, FONT_BODY, FONT_MONO
    candidates = {
        "display": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
        "body": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
        "mono": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"],
    }
    loaded = {}
    for key, paths in candidates.items():
        for p in paths:
            if os.path.exists(p):
                loaded[key] = p
                break
    FONT_DISPLAY = loaded.get("display")
    FONT_BODY = loaded.get("body")
    FONT_MONO = loaded.get("mono")


def _font(size: int, bold: bool = False, mono: bool = False):
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
# Drawing primitives — smooth, professional
# ============================================================
def _line(draw, x1, y1, x2, y2, width=LINE_WIDTH):
    """Straight line with rounded end caps (drawn as filled circles)."""
    draw.line([(x1, y1), (x2, y2)], fill=LINE_COLOR, width=width, joint="curve")
    # Round end caps so joints look smooth
    draw.ellipse([x1 - width/2, y1 - width/2, x1 + width/2, y1 + width/2], fill=LINE_COLOR)
    draw.ellipse([x2 - width/2, y2 - width/2, x2 + width/2, y2 + width/2], fill=LINE_COLOR)


def _curve(draw, points, width=LINE_WIDTH):
    """Smooth curve through multiple points using quadratic Beziers."""
    if len(points) < 2:
        return
    # Draw as connected line segments with curve joint
    draw.line(points, fill=LINE_COLOR, width=width, joint="curve")
    # Round caps at endpoints
    p1, p2 = points[0], points[-1]
    draw.ellipse([p1[0] - width/2, p1[1] - width/2, p1[0] + width/2, p1[1] + width/2], fill=LINE_COLOR)
    draw.ellipse([p2[0] - width/2, p2[1] - width/2, p2[0] + width/2, p2[1] + width/2], fill=LINE_COLOR)


def _circle(draw, cx, cy, r, width=LINE_WIDTH):
    """Head circle — clean stroke."""
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, outline=LINE_COLOR, width=width)


def _dot(draw, cx, cy, r=JOINT_RADIUS):
    """Small filled circle for hands/feet — gives the figure clean termination."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=LINE_COLOR)


def _arc_line(draw, x1, y1, xc, yc, x2, y2, width=LINE_WIDTH):
    """Draw a bent line through (x1,y1) -> (xc,yc) -> (x2,y2) with smooth corner.
    The corner is rounded via the curve joint.
    """
    draw.line([(x1, y1), (xc, yc), (x2, y2)], fill=LINE_COLOR, width=width, joint="curve")
    # End caps
    draw.ellipse([x1 - width/2, y1 - width/2, x1 + width/2, y1 + width/2], fill=LINE_COLOR)
    draw.ellipse([x2 - width/2, y2 - width/2, x2 + width/2, y2 + width/2], fill=LINE_COLOR)


# ============================================================
# Pose functions — each draws the character in one position
# Coordinate system: (cx, cy) = head center. Body extends downward.
# Body height (head to feet): ~360px (was 280)
# ============================================================

def pose_standing_tall(draw, cx, cy):
    """Standing upright, arms at sides."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)  # spine
    # arms hang straight down
    _line(draw, cx - 4, cy + 90, cx - 50, cy + 200)
    _line(draw, cx + 4, cy + 90, cx + 50, cy + 200)
    _dot(draw, cx - 50, cy + 200)
    _dot(draw, cx + 50, cy + 200)
    # legs straight
    _line(draw, cx, cy + 240, cx - 38, cy + 360)
    _line(draw, cx, cy + 240, cx + 38, cy + 360)
    _dot(draw, cx - 38, cy + 360)
    _dot(draw, cx + 38, cy + 360)


def pose_walking(draw, cx, cy):
    """Mid-stride, leaning forward."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    # curved spine leaning forward
    _curve(draw, [(cx, cy + HEAD_RADIUS), (cx + 14, cy + 130), (cx + 8, cy + 240)])
    # back arm swinging forward
    _arc_line(draw, cx - 4, cy + 95, cx + 18, cy + 130, cx + 32, cy + 165)
    # front arm swinging back
    _arc_line(draw, cx + 4, cy + 95, cx - 18, cy + 140, cx - 38, cy + 175)
    _dot(draw, cx + 32, cy + 165)
    _dot(draw, cx - 38, cy + 175)
    # back leg bent at knee
    _arc_line(draw, cx + 8, cy + 240, cx - 22, cy + 300, cx - 60, cy + 320)
    # front leg extended forward
    _arc_line(draw, cx + 8, cy + 240, cx + 38, cy + 310, cx + 60, cy + 355)
    _dot(draw, cx - 60, cy + 320)
    _dot(draw, cx + 60, cy + 355)


def pose_running(draw, cx, cy):
    """Running hard, body tilted forward."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _curve(draw, [(cx, cy + HEAD_RADIUS), (cx + 22, cy + 130), (cx + 28, cy + 240)])
    # arms pumping hard
    _arc_line(draw, cx - 4, cy + 95, cx - 25, cy + 120, cx - 45, cy + 145)
    _arc_line(draw, cx + 4, cy + 95, cx + 30, cy + 130, cx + 55, cy + 160)
    _dot(draw, cx - 45, cy + 145)
    _dot(draw, cx + 55, cy + 160)
    # legs in sprint positions
    _arc_line(draw, cx + 28, cy + 240, cx - 20, cy + 280, cx - 70, cy + 260)
    _arc_line(draw, cx + 28, cy + 240, cx + 55, cy + 310, cx + 80, cy + 355)
    _dot(draw, cx - 70, cy + 260)
    _dot(draw, cx + 80, cy + 355)


def pose_sitting_ground(draw, cx, cy):
    """Sitting on ground, knees up, head down."""
    _circle(draw, cx, cy + 50, HEAD_RADIUS)
    _curve(draw, [(cx, cy + 50 + HEAD_RADIUS), (cx + 8, cy + 130), (cx + 12, cy + 200)])
    # arms wrapped around knees
    _arc_line(draw, cx - 4, cy + 100, cx - 38, cy + 160, cx - 60, cy + 220)
    _arc_line(draw, cx + 4, cy + 100, cx + 38, cy + 160, cx + 60, cy + 220)
    _dot(draw, cx - 60, cy + 220)
    _dot(draw, cx + 60, cy + 220)
    # legs bent up to chest
    _arc_line(draw, cx + 12, cy + 200, cx - 35, cy + 280, cx - 60, cy + 220)
    _arc_line(draw, cx + 12, cy + 200, cx + 48, cy + 280, cx + 60, cy + 220)


def pose_kneeling(draw, cx, cy):
    """One knee on ground, head bowed."""
    _circle(draw, cx, cy + 40, HEAD_RADIUS)
    _curve(draw, [(cx, cy + 40 + HEAD_RADIUS), (cx + 6, cy + 120), (cx + 8, cy + 220)])
    # both arms reaching forward/down
    _arc_line(draw, cx - 4, cy + 100, cx - 22, cy + 180, cx - 38, cy + 220)
    _arc_line(draw, cx + 4, cy + 100, cx + 22, cy + 180, cx + 38, cy + 220)
    _dot(draw, cx - 38, cy + 220)
    _dot(draw, cx + 38, cy + 220)
    # one leg kneeling, one forward
    _arc_line(draw, cx + 8, cy + 220, cx - 30, cy + 320, cx - 30, cy + 360)
    _arc_line(draw, cx + 8, cy + 220, cx + 48, cy + 290, cx + 85, cy + 305)
    _dot(draw, cx - 30, cy + 360)
    _dot(draw, cx + 85, cy + 305)


def pose_looking_up(draw, cx, cy):
    """Standing, head tilted back, looking at sky."""
    _circle(draw, cx, cy - 12, HEAD_RADIUS)
    _line(draw, cx, cy - 12 + HEAD_RADIUS, cx, cy + 240)
    _line(draw, cx - 4, cy + 90, cx - 38, cy + 200)
    _line(draw, cx + 4, cy + 90, cx + 38, cy + 200)
    _dot(draw, cx - 38, cy + 200)
    _dot(draw, cx + 38, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)


def pose_climbing(draw, cx, cy):
    """Reaching up, climbing."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _curve(draw, [(cx, cy + HEAD_RADIUS), (cx + 8, cy + 130), (cx, cy + 240)])
    # one arm reaching straight up
    _line(draw, cx - 4, cy + 80, cx - 38, cy + 10)
    # other arm pulling down
    _arc_line(draw, cx + 4, cy + 95, cx + 28, cy + 150, cx + 32, cy + 180)
    _dot(draw, cx - 38, cy + 10)
    _dot(draw, cx + 32, cy + 180)
    # legs in climbing stance
    _arc_line(draw, cx, cy + 240, cx - 32, cy + 305, cx - 60, cy + 320)
    _arc_line(draw, cx, cy + 240, cx + 25, cy + 290, cx + 55, cy + 350)
    _dot(draw, cx - 60, cy + 320)
    _dot(draw, cx + 55, cy + 350)


def pose_pointing_forward(draw, cx, cy):
    """One arm extended forward — direction, purpose."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    _line(draw, cx - 4, cy + 95, cx - 38, cy + 200)
    _dot(draw, cx - 38, cy + 200)
    # front arm pointing forward (horizontal)
    _line(draw, cx + 4, cy + 95, cx + 100, cy + 110)
    _dot(draw, cx + 100, cy + 110)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)


def pose_pushing_boulder(draw, cx, cy):
    """Leaning forward, both hands pushing an invisible boulder."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _curve(draw, [(cx, cy + HEAD_RADIUS), (cx + 28, cy + 130), (cx + 32, cy + 240)])
    # both arms forward, pushing
    _arc_line(draw, cx - 4, cy + 95, cx + 60, cy + 125, cx + 105, cy + 130)
    _arc_line(draw, cx + 4, cy + 95, cx + 65, cy + 145, cx + 110, cy + 150)
    _dot(draw, cx + 105, cy + 130)
    _dot(draw, cx + 110, cy + 150)
    # legs in pushing stance
    _arc_line(draw, cx + 32, cy + 240, cx - 10, cy + 310, cx - 35, cy + 355)
    _arc_line(draw, cx + 32, cy + 240, cx + 40, cy + 315, cx + 30, cy + 360)
    _dot(draw, cx - 35, cy + 355)
    _dot(draw, cx + 30, cy + 360)
    # boulder
    _circle(draw, cx + 170, cy + 160, 60)


def pose_carrying_load(draw, cx, cy):
    """Walking with a heavy load on back."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _curve(draw, [(cx, cy + HEAD_RADIUS), (cx + 14, cy + 130), (cx + 10, cy + 240)])
    _arc_line(draw, cx - 4, cy + 95, cx - 22, cy + 145, cx - 28, cy + 180)
    _arc_line(draw, cx + 4, cy + 95, cx + 22, cy + 145, cx + 28, cy + 180)
    _dot(draw, cx - 28, cy + 180)
    _dot(draw, cx + 28, cy + 180)
    _arc_line(draw, cx + 10, cy + 240, cx - 22, cy + 310, cx - 40, cy + 355)
    _arc_line(draw, cx + 10, cy + 240, cx + 30, cy + 305, cx + 50, cy + 350)
    _dot(draw, cx - 40, cy + 355)
    _dot(draw, cx + 50, cy + 350)
    # the load — square block on shoulders
    draw.rectangle([cx - 60, cy - 40, cx + 12, cy + 32], outline=LINE_COLOR, width=LINE_WIDTH)


def pose_standing_alone_hill(draw, cx, cy):
    """Standing on top of a hill."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    _line(draw, cx - 4, cy + 95, cx - 42, cy + 200)
    _line(draw, cx + 4, cy + 95, cx + 42, cy + 200)
    _dot(draw, cx - 42, cy + 200)
    _dot(draw, cx + 42, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # hill
    draw.line([(60, 690), (cx, 530), (1220, 690)], fill=MUTED, width=4, joint="curve")


def pose_facing_wall(draw, cx, cy):
    """Facing a wall."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # both hands touching wall
    _arc_line(draw, cx - 4, cy + 95, cx - 38, cy + 100, cx - 65, cy + 110)
    _arc_line(draw, cx + 4, cy + 95, cx - 30, cy + 120, cx - 65, cy + 130)
    _dot(draw, cx - 65, cy + 110)
    _dot(draw, cx - 65, cy + 130)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # wall on left
    draw.line([(cx - 90, cy - 100), (cx - 90, cy + 360)], fill=LINE_COLOR, width=10)


def pose_arms_crossed(draw, cx, cy):
    """Standing, arms crossed — defiance."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # arms crossed over chest
    _arc_line(draw, cx - 4, cy + 95, cx + 28, cy + 130, cx + 35, cy + 145)
    _arc_line(draw, cx + 4, cy + 95, cx - 28, cy + 130, cx - 35, cy + 145)
    _dot(draw, cx + 35, cy + 145)
    _dot(draw, cx - 35, cy + 145)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)


def pose_falling(draw, cx, cy):
    """Mid-fall, body horizontal."""
    _circle(draw, cx + 100, cy + 130, HEAD_RADIUS)
    _line(draw, cx + 100 - HEAD_RADIUS, cy + 130, cx - 60, cy + 120)
    # arms splayed upward
    _line(draw, cx + 40, cy + 125, cx + 40, cy + 60)
    _line(draw, cx + 10, cy + 125, cx + 10, cy + 65)
    _dot(draw, cx + 40, cy + 60)
    _dot(draw, cx + 10, cy + 65)
    # legs splayed
    _line(draw, cx - 35, cy + 120, cx - 35, cy + 60)
    _line(draw, cx - 60, cy + 120, cx - 60, cy + 65)
    _dot(draw, cx - 35, cy + 60)
    _dot(draw, cx - 60, cy + 65)


def pose_rising_up(draw, cx, cy):
    """Halfway up from ground, one hand on floor."""
    _circle(draw, cx, cy + 80, HEAD_RADIUS)
    _curve(draw, [(cx, cy + 80 + HEAD_RADIUS), (cx + 12, cy + 170), (cx + 18, cy + 230)])
    # one hand on ground for support
    _arc_line(draw, cx - 4, cy + 120, cx - 38, cy + 220, cx - 60, cy + 250)
    # other arm reaching forward
    _arc_line(draw, cx + 4, cy + 120, cx + 35, cy + 145, cx + 55, cy + 165)
    _dot(draw, cx - 60, cy + 250)
    _dot(draw, cx + 55, cy + 165)
    # one knee down, one foot planted
    _arc_line(draw, cx + 18, cy + 230, cx - 20, cy + 320, cx - 20, cy + 360)
    _arc_line(draw, cx + 18, cy + 230, cx + 55, cy + 290, cx + 80, cy + 350)
    _dot(draw, cx - 20, cy + 360)
    _dot(draw, cx + 80, cy + 350)


def pose_fist_clenched(draw, cx, cy):
    """Standing, fists clenched at sides — resolve."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # arms bent slightly, fists at hip level
    _arc_line(draw, cx - 4, cy + 95, cx - 42, cy + 160, cx - 38, cy + 200)
    _arc_line(draw, cx + 4, cy + 95, cx + 42, cy + 160, cx + 38, cy + 200)
    # fists as larger filled circles
    _dot(draw, cx - 38, cy + 200, r=12)
    _dot(draw, cx + 38, cy + 200, r=12)
    _line(draw, cx, cy + 240, cx - 36, cy + 360)
    _line(draw, cx, cy + 240, cx + 36, cy + 360)
    _dot(draw, cx - 36, cy + 360)
    _dot(draw, cx + 36, cy + 360)


def pose_meditating(draw, cx, cy):
    """Cross-legged sitting, hands on knees."""
    _circle(draw, cx, cy + 25, HEAD_RADIUS)
    _curve(draw, [(cx, cy + 25 + HEAD_RADIUS), (cx + 4, cy + 110), (cx + 6, cy + 180)])
    # arms down to knees
    _arc_line(draw, cx - 4, cy + 100, cx - 32, cy + 175, cx - 60, cy + 215)
    _arc_line(draw, cx + 4, cy + 100, cx + 32, cy + 175, cx + 60, cy + 215)
    _dot(draw, cx - 60, cy + 215)
    _dot(draw, cx + 60, cy + 215)
    # crossed legs
    _arc_line(draw, cx + 6, cy + 180, cx - 60, cy + 245, cx + 12, cy + 270)
    _arc_line(draw, cx + 6, cy + 180, cx + 60, cy + 245, cx - 12, cy + 270)


def pose_writing(draw, cx, cy):
    """Sitting, hunched forward, writing in book."""
    _circle(draw, cx, cy + 50, HEAD_RADIUS)
    _curve(draw, [(cx, cy + 50 + HEAD_RADIUS), (cx + 12, cy + 130), (cx + 14, cy + 180)])
    # both arms forward toward book
    _arc_line(draw, cx - 4, cy + 100, cx - 28, cy + 195, cx - 38, cy + 220)
    _arc_line(draw, cx + 4, cy + 100, cx + 28, cy + 195, cx + 38, cy + 220)
    _dot(draw, cx - 38, cy + 220)
    _dot(draw, cx + 38, cy + 220)
    # legs crossed under
    _arc_line(draw, cx + 14, cy + 180, cx - 48, cy + 245, cx + 8, cy + 265)
    _arc_line(draw, cx + 14, cy + 180, cx + 50, cy + 245, cx - 8, cy + 265)
    # book on lap
    draw.rectangle([cx - 50, cy + 215, cx + 50, cy + 245], outline=LINE_COLOR, width=4)


def pose_standing_window(draw, cx, cy):
    """Standing by a window."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # one arm up near head (touching window frame)
    _arc_line(draw, cx - 4, cy + 95, cx - 35, cy + 65, cx - 50, cy + 50)
    _line(draw, cx + 4, cy + 95, cx + 32, cy + 200)
    _dot(draw, cx - 50, cy + 50)
    _dot(draw, cx + 32, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # window frame on left
    draw.rectangle([cx - 150, cy - 100, cx - 30, cy + 130], outline=LINE_COLOR, width=4)
    draw.line([(cx - 90, cy - 100), (cx - 90, cy + 130)], fill=LINE_COLOR, width=3)


def pose_staring_mirror(draw, cx, cy):
    """Standing facing a mirror."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # both arms raised slightly, hands near face
    _arc_line(draw, cx - 4, cy + 95, cx - 30, cy + 65, cx - 25, cy + 35)
    _arc_line(draw, cx + 4, cy + 95, cx + 30, cy + 65, cx + 25, cy + 35)
    _dot(draw, cx - 25, cy + 35)
    _dot(draw, cx + 25, cy + 35)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # mirror on right
    draw.rectangle([cx + 90, cy - 70, cx + 180, cy + 200], outline=LINE_COLOR, width=4)


def pose_walking_alone_path(draw, cx, cy):
    """Walking alone on a long path."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _curve(draw, [(cx, cy + HEAD_RADIUS), (cx + 12, cy + 130), (cx + 6, cy + 240)])
    _arc_line(draw, cx - 4, cy + 95, cx + 18, cy + 145, cx + 32, cy + 175)
    _arc_line(draw, cx + 4, cy + 95, cx - 18, cy + 150, cx - 38, cy + 180)
    _dot(draw, cx + 32, cy + 175)
    _dot(draw, cx - 38, cy + 180)
    _arc_line(draw, cx + 6, cy + 240, cx - 22, cy + 305, cx - 55, cy + 320)
    _arc_line(draw, cx + 6, cy + 240, cx + 35, cy + 305, cx + 60, cy + 355)
    _dot(draw, cx - 55, cy + 320)
    _dot(draw, cx + 60, cy + 355)
    # path stretching forward
    draw.line([(60, 700), (cx, 580), (1220, 510)], fill=MUTED, width=4, joint="curve")


def pose_bowing_head(draw, cx, cy):
    """Standing, head bowed."""
    _circle(draw, cx, cy + 35, HEAD_RADIUS)
    _curve(draw, [(cx, cy + 35 + HEAD_RADIUS), (cx + 8, cy + 130), (cx, cy + 240)])
    _line(draw, cx - 4, cy + 95, cx - 38, cy + 200)
    _line(draw, cx + 4, cy + 95, cx + 38, cy + 200)
    _dot(draw, cx - 38, cy + 200)
    _dot(draw, cx + 38, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)


def pose_sun_rising(draw, cx, cy):
    """Standing, facing a rising sun."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    _line(draw, cx - 4, cy + 95, cx - 38, cy + 200)
    _line(draw, cx + 4, cy + 95, cx + 38, cy + 200)
    _dot(draw, cx - 38, cy + 200)
    _dot(draw, cx + 38, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # sun on right
    _circle(draw, cx + 290, cy + 110, 55, width=5)
    draw.line([(60, 620), (1220, 620)], fill=MUTED, width=4)


def pose_empty_chair(draw, cx, cy):
    """An empty chair — absence, reflection on what was."""
    # No character in this frame — just the chair
    # Chair seat
    draw.rectangle([cx - 60, cy + 160, cx + 60, cy + 180], outline=LINE_COLOR, width=LINE_WIDTH)
    # Chair back
    draw.line([(cx - 60, cy + 160), (cx - 60, cy + 20)], fill=LINE_COLOR, width=LINE_WIDTH)
    # Front legs
    draw.line([(cx + 60, cy + 180), (cx + 60, cy + 300)], fill=LINE_COLOR, width=LINE_WIDTH)
    draw.line([(cx + 50, cy + 180), (cx + 50, cy + 300)], fill=LINE_COLOR, width=LINE_WIDTH)
    # Back legs
    draw.line([(cx - 60, cy + 180), (cx - 60, cy + 300)], fill=LINE_COLOR, width=LINE_WIDTH)
    draw.line([(cx - 50, cy + 180), (cx - 50, cy + 300)], fill=LINE_COLOR, width=LINE_WIDTH)


def pose_clock_waiting(draw, cx, cy):
    """Standing, looking at a clock."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # one arm raised toward clock
    _arc_line(draw, cx - 4, cy + 95, cx - 35, cy + 90, cx - 60, cy + 85)
    _line(draw, cx + 4, cy + 95, cx + 32, cy + 200)
    _dot(draw, cx - 60, cy + 85)
    _dot(draw, cx + 32, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # clock on upper left
    _circle(draw, cx - 145, cy - 50, 50, width=5)
    # clock hands
    draw.line([(cx - 145, cy - 50), (cx - 145, cy - 85)], fill=LINE_COLOR, width=5)
    draw.line([(cx - 145, cy - 50), (cx - 115, cy - 50)], fill=LINE_COLOR, width=5)
    # center dot
    _dot(draw, cx - 145, cy - 50, r=4)


def pose_holding_light(draw, cx, cy):
    """Standing, holding up a small light/candle — hope."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # one arm raised holding light
    _arc_line(draw, cx - 4, cy + 90, cx - 18, cy + 35, cx - 25, cy + 5)
    _line(draw, cx + 4, cy + 95, cx + 32, cy + 200)
    _dot(draw, cx + 32, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # small light/candle above hand
    _circle(draw, cx - 25, cy - 20, 20, width=4)


def pose_standing_mountain_top(draw, cx, cy):
    """On a mountain peak, looking down at the world."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    _line(draw, cx - 4, cy + 95, cx - 42, cy + 200)
    _line(draw, cx + 4, cy + 95, cx + 42, cy + 200)
    _dot(draw, cx - 42, cy + 200)
    _dot(draw, cx + 42, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # mountain peak silhouette
    draw.line([(40, 700), (cx, 530), (1240, 700)], fill=MUTED, width=5, joint="curve")


def pose_face_down(draw, cx, cy):
    """Lying face down on the ground — defeat."""
    # horizontal body on ground
    _circle(draw, cx - 120, cy + 230, HEAD_RADIUS)
    _line(draw, cx - 120 + HEAD_RADIUS, cy + 230, cx + 90, cy + 235)
    # arms limp
    _line(draw, cx - 75, cy + 235, cx - 75, cy + 280)
    _line(draw, cx - 40, cy + 235, cx - 40, cy + 275)
    _dot(draw, cx - 75, cy + 280)
    _dot(draw, cx - 40, cy + 275)
    # legs limp
    _line(draw, cx + 45, cy + 235, cx + 45, cy + 280)
    _line(draw, cx + 80, cy + 235, cx + 80, cy + 275)
    _dot(draw, cx + 45, cy + 280)
    _dot(draw, cx + 80, cy + 275)
    # ground line
    draw.line([(40, cy + 290), (1240, cy + 290)], fill=LINE_COLOR, width=5)


def pose_two_paths(draw, cx, cy):
    """Standing at a fork in the road."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # arms gesturing left and right
    _arc_line(draw, cx - 4, cy + 95, cx - 38, cy + 90, cx - 65, cy + 100)
    _arc_line(draw, cx + 4, cy + 95, cx + 38, cy + 90, cx + 65, cy + 100)
    _dot(draw, cx - 65, cy + 100)
    _dot(draw, cx + 65, cy + 100)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # two paths diverging
    draw.line([(cx, 700), (cx - 280, 530)], fill=MUTED, width=4)
    draw.line([(cx, 700), (cx + 280, 530)], fill=MUTED, width=4)


def pose_arms_raised(draw, cx, cy):
    """Both arms raised up — triumph, surrender, or reaching."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    _arc_line(draw, cx - 4, cy + 90, cx - 25, cy + 25, cx - 35, cy - 5)
    _arc_line(draw, cx + 4, cy + 90, cx + 25, cy + 25, cx + 35, cy - 5)
    _dot(draw, cx - 35, cy - 5)
    _dot(draw, cx + 35, cy - 5)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)


def pose_dark_room_alone(draw, cx, cy):
    """Sitting alone in a dark room with a sliver of light."""
    _circle(draw, cx, cy + 80, HEAD_RADIUS)
    _curve(draw, [(cx, cy + 80 + HEAD_RADIUS), (cx + 8, cy + 170), (cx + 12, cy + 220)])
    _arc_line(draw, cx - 4, cy + 120, cx - 28, cy + 195, cx - 38, cy + 225)
    _arc_line(draw, cx + 4, cy + 120, cx + 28, cy + 195, cx + 38, cy + 225)
    _dot(draw, cx - 38, cy + 225)
    _dot(draw, cx + 38, cy + 225)
    _arc_line(draw, cx + 12, cy + 220, cx - 38, cy + 280, cx - 38, cy + 320)
    _arc_line(draw, cx + 12, cy + 220, cx + 38, cy + 280, cx + 38, cy + 320)
    _dot(draw, cx - 38, cy + 320)
    _dot(draw, cx + 38, cy + 320)
    # window letting in a sliver of light
    draw.rectangle([cx + 230, cy - 50, cx + 320, cy + 130], outline=LINE_COLOR, width=4)
    draw.line([(cx + 275, cy + 110), (cx + 100, cy + 240)], fill=MUTED, width=3)


def pose_handshake_self(draw, cx, cy):
    """Both hands clasped together in front — commitment to self."""
    _circle(draw, cx, cy, HEAD_RADIUS)
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    # both arms meeting in front of chest
    _arc_line(draw, cx - 4, cy + 95, cx + 8, cy + 130, cx + 5, cy + 155)
    _arc_line(draw, cx + 4, cy + 95, cx - 8, cy + 130, cx - 5, cy + 155)
    _dot(draw, cx + 5, cy + 155, r=10)  # clasped hands as bigger dot
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)


def pose_looking_back(draw, cx, cy):
    """Standing, head turned to look behind — regret or reflection."""
    _circle(draw, cx - 18, cy, HEAD_RADIUS)  # head turned
    _line(draw, cx, cy + HEAD_RADIUS, cx, cy + 240)
    _line(draw, cx - 4, cy + 95, cx - 38, cy + 200)
    _line(draw, cx + 4, cy + 95, cx + 38, cy + 200)
    _dot(draw, cx - 38, cy + 200)
    _dot(draw, cx + 38, cy + 200)
    _line(draw, cx, cy + 240, cx - 32, cy + 360)
    _line(draw, cx, cy + 240, cx + 32, cy + 360)
    _dot(draw, cx - 32, cy + 360)
    _dot(draw, cx + 32, cy + 360)
    # faint footprints trailing behind
    for fx, fy in [(cx - 150, 670), (cx - 195, 685), (cx - 240, 660)]:
        _dot(draw, fx, fy, r=8)


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
    fig_cx = CANVAS[0] // 4 + 30
    fig_cy = 180  # head center — moved up to fit longer body
    pose_func(draw, fig_cx, fig_cy)

    # --- Right half: caption text ---
    if caption:
        snippet = caption[:140]
        cap_font = _font(44, bold=True)
        max_w = CANVAS[0] // 2 - MARGIN - 20
        lines = _wrap_text(snippet, cap_font, draw, max_w)
        line_h = int(44 * 1.18)
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


# Backwards-compat shims
def render_svg(pose_name: str, scene_text: str = "") -> str:
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
    import base64, re
    with open(svg_path, "r") as f:
        svg = f.read()
    m = re.search(r'base64,([A-Za-z0-9+/=]+)', svg)
    if m:
        with open(png_path, "wb") as f:
            f.write(base64.b64decode(m.group(1)))
    else:
        render_pose_to_png("standing_tall", png_path)


if __name__ == "__main__":
    os.makedirs("/tmp/poses_v6", exist_ok=True)
    test_captions = [
        "Discipline is choosing what you want most over what you want now.",
        "The body screams stop. The mind agrees. You ignore both.",
        "Walk alone. The path narrows. Most fall off.",
        "Get back up.",
        "The morning is cold. The work is hard. Begin anyway.",
        "Years pass. You are unrecognizable.",
    ]
    for i, name in enumerate(POSE_NAMES[:6]):
        out = f"/tmp/poses_v6/{name}.png"
        render_pose_to_png(
            name, out,
            caption=test_captions[i % len(test_captions)],
            scene_num=i + 1, scene_total=25,
        )
        print(f"  OK {name}")
    print(f"\nRendered 6 test poses to /tmp/poses_v6/")
