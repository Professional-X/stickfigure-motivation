"""Deterministic stick-figure renderer — v7 "IKEA instruction" style.

DESIGN PHILOSOPHY (changed from v6):
  * ONE character, drawn the same way in every frame
  * Clean minimalist line art — IKEA instruction manual aesthetic
  * Single thin black line (3px), no fills, no hand/foot dots
  * Simple circle head, straight limbs, minimal joints
  * Background: free CC-licensed texture from Openverse (paper, concrete, etc.)
  * NO zoom, NO pan — static frames only

The stick figure is drawn with consistent proportions:
  * Head: circle, radius 30px
  * Body: 180px tall (head center to hip)
  * Arms: attach at shoulder (40px below head center), 90px long
  * Legs: attach at hip, 110px long
  * Total height: ~330px (head top to feet)

Pose variations only change limb angles, never proportions or stroke style.
This makes the character feel like the SAME person in different positions.
"""
import os
import math
import textwrap
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import config


# ============================================================
# Design tokens — IKEA instruction style
# ============================================================
CANVAS = (1280, 720)

# Colors
BG_FALLBACK = (250, 248, 244)  # warm off-white if no texture
INK = (15, 15, 20)             # near-black for stick figure + text
MUTED = (107, 111, 118)
ACCENT = (200, 16, 46)         # deep red accent
ACCENT_TINT = (255, 235, 238)
WHITE = (255, 255, 255)
WHITE_OVERLAY = (255, 255, 255, 200)  # semi-transparent white to fade backgrounds

# Stick figure stroke — thin, clean, single line
STROKE_COLOR = (15, 15, 20)
STROKE_WIDTH = 4               # thin = elegant
HEAD_RADIUS = 32

# Layout
MARGIN = 80
CONTENT_W = CANVAS[0] - 2 * MARGIN

# Fonts (lazy-loaded)
_FONT_CACHE = {}
def _font(size: int, bold: bool = False, mono: bool = False):
    key = (size, bold, mono)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    paths = []
    if mono:
        paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"]
    elif bold:
        paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
    else:
        paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    for p in paths:
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            _FONT_CACHE[key] = f
            return f
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


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
# Stick figure drawing — ONE character, pose variations only
# ============================================================
# All poses share these proportions:
#   head_cy = top of figure
#   shoulder_y = head_cy + HEAD_RADIUS + 8
#   hip_y = shoulder_y + 110
#   feet_y = hip_y + 110
# Total figure height: ~330px
#
# Pose functions take (draw, cx, head_cy) and draw the character.
# cx = horizontal center of figure
# head_cy = vertical center of head circle

FIGURE_HEAD_CY = 180  # default head center Y

def _draw_head(draw, cx, cy):
    """Circle head — clean stroke, no fill."""
    bbox = [cx - HEAD_RADIUS, cy - HEAD_RADIUS, cx + HEAD_RADIUS, cy + HEAD_RADIUS]
    draw.ellipse(bbox, outline=STROKE_COLOR, width=STROKE_WIDTH)


def _draw_spine(draw, cx, head_cy, lean=0):
    """Spine: straight line from below head to hip. Optional lean."""
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _line(draw, cx + lean * 0.3, shoulder_y, cx + lean, hip_y)


def _draw_limb(draw, x1, y1, x2, y2):
    """Draw one limb segment — straight line, no joint dot."""
    _line(draw, x1, y1, x2, y2)


def _line(draw, x1, y1, x2, y2, width=STROKE_WIDTH):
    """Straight line with rounded caps."""
    draw.line([(x1, y1), (x2, y2)], fill=STROKE_COLOR, width=width)
    # Rounded end caps via small circles — keeps joints smooth
    r = width / 2
    draw.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=STROKE_COLOR)
    draw.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=STROKE_COLOR)


# --- Pose functions ---
# Each draws: head + spine + 2 arms + 2 legs
# Arms attach at shoulder (cx, head_cy + HEAD_RADIUS + 8)
# Legs attach at hip (cx + lean, head_cy + HEAD_RADIUS + 8 + 110)

def pose_standing_tall(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # arms hang straight down
    _draw_limb(draw, cx, shoulder_y, cx - 35, shoulder_y + 95)
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 95)
    # legs straight
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)


def pose_walking(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=8)
    # arms swinging
    _draw_limb(draw, cx + 8, shoulder_y, cx + 35, shoulder_y + 90)
    _draw_limb(draw, cx + 8, shoulder_y, cx - 30, shoulder_y + 95)
    # legs mid-stride
    _draw_limb(draw, cx + 8, hip_y, cx - 30, hip_y + 110)
    _draw_limb(draw, cx + 8, hip_y, cx + 35, hip_y + 105)


def pose_running(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=15)
    # arms pumping hard
    _draw_limb(draw, cx + 15, shoulder_y, cx - 25, shoulder_y + 70)
    _draw_limb(draw, cx + 15, shoulder_y, cx + 45, shoulder_y + 80)
    # legs sprint
    _draw_limb(draw, cx + 15, hip_y, cx - 40, hip_y + 80)
    _draw_limb(draw, cx + 15, hip_y, cx + 50, hip_y + 105)


def pose_sitting_ground(draw, cx, head_cy):
    # Sitting on ground — figure is lower
    head_cy = head_cy + 60
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 90
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=5)
    # arms forward around knees
    _draw_limb(draw, cx + 5, shoulder_y, cx - 40, shoulder_y + 100)
    _draw_limb(draw, cx + 5, shoulder_y, cx + 40, shoulder_y + 100)
    # legs bent up
    _draw_limb(draw, cx + 5, hip_y, cx - 45, hip_y + 70)
    _draw_limb(draw, cx + 5, hip_y, cx + 45, hip_y + 70)


def pose_kneeling(draw, cx, head_cy):
    head_cy = head_cy + 30
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 100
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=4)
    # arms reaching down
    _draw_limb(draw, cx + 4, shoulder_y, cx - 30, shoulder_y + 110)
    _draw_limb(draw, cx + 4, shoulder_y, cx + 30, shoulder_y + 110)
    # one knee down, one forward
    _draw_limb(draw, cx + 4, hip_y, cx - 25, hip_y + 130)
    _draw_limb(draw, cx + 4, hip_y, cx + 50, hip_y + 90)


def pose_looking_up(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy - 10)
    _draw_spine(draw, cx, head_cy)
    _draw_limb(draw, cx, shoulder_y, cx - 35, shoulder_y + 95)
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 95)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)


def pose_climbing(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=6)
    # one arm reaching up
    _draw_limb(draw, cx + 6, shoulder_y, cx - 25, shoulder_y - 50)
    _draw_limb(draw, cx + 6, shoulder_y, cx + 30, shoulder_y + 60)
    # legs climbing
    _draw_limb(draw, cx + 6, hip_y, cx - 30, hip_y + 90)
    _draw_limb(draw, cx + 6, hip_y, cx + 35, hip_y + 105)


def pose_pointing_forward(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # one arm pointing forward (horizontal)
    _draw_limb(draw, cx, shoulder_y, cx - 35, shoulder_y + 95)
    _draw_limb(draw, cx, shoulder_y, cx + 90, shoulder_y)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)


def pose_pushing_boulder(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=20)
    # both arms forward pushing
    _draw_limb(draw, cx + 20, shoulder_y, cx + 80, shoulder_y + 20)
    _draw_limb(draw, cx + 20, shoulder_y, cx + 85, shoulder_y + 40)
    # legs braced
    _draw_limb(draw, cx + 20, hip_y, cx - 20, hip_y + 110)
    _draw_limb(draw, cx + 20, hip_y, cx + 40, hip_y + 115)
    # boulder
    draw.ellipse([cx + 110, shoulder_y - 20, cx + 220, shoulder_y + 90],
                 outline=STROKE_COLOR, width=STROKE_WIDTH)


def pose_carrying_load(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=10)
    # arms up to load
    _draw_limb(draw, cx + 10, shoulder_y, cx - 30, shoulder_y - 30)
    _draw_limb(draw, cx + 10, shoulder_y, cx + 30, shoulder_y - 30)
    # walking legs
    _draw_limb(draw, cx + 10, hip_y, cx - 25, hip_y + 110)
    _draw_limb(draw, cx + 10, hip_y, cx + 35, hip_y + 105)
    # load on back
    draw.rectangle([cx - 50, head_cy - 50, cx + 30, head_cy + 10],
                   outline=STROKE_COLOR, width=STROKE_WIDTH)


def pose_standing_alone_hill(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    _draw_limb(draw, cx, shoulder_y, cx - 35, shoulder_y + 95)
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 95)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)
    # hill — gentle curve
    draw.line([(60, 690), (cx, 580), (1220, 690)], fill=MUTED, width=3, joint="curve")


def pose_facing_wall(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # hands on wall
    _draw_limb(draw, cx, shoulder_y, cx - 50, shoulder_y + 10)
    _draw_limb(draw, cx, shoulder_y, cx - 50, shoulder_y + 30)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)
    # wall on left
    draw.line([(cx - 75, head_cy - 80), (cx - 75, hip_y + 130)],
              fill=STROKE_COLOR, width=8)


def pose_arms_crossed(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # arms crossed over chest
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 50)
    _draw_limb(draw, cx, shoulder_y, cx - 35, shoulder_y + 50)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)


def pose_falling(draw, cx, head_cy):
    # Horizontal figure — falling
    head_cy = head_cy + 80
    _draw_head(draw, cx + 90, head_cy)
    # spine horizontal
    _line(draw, cx + 90 - HEAD_RADIUS, head_cy, cx - 60, head_cy + 5)
    # arms splayed
    _draw_limb(draw, cx + 30, head_cy, cx + 30, head_cy - 50)
    _draw_limb(draw, cx, head_cy, cx, head_cy + 50)
    # legs splayed
    _draw_limb(draw, cx - 30, head_cy + 5, cx - 30, head_cy - 45)
    _draw_limb(draw, cx - 60, head_cy + 5, cx - 60, head_cy + 50)


def pose_rising_up(draw, cx, head_cy):
    head_cy = head_cy + 50
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 100
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=8)
    # one hand on ground
    _draw_limb(draw, cx + 8, shoulder_y, cx - 45, shoulder_y + 110)
    _draw_limb(draw, cx + 8, shoulder_y, cx + 40, shoulder_y + 50)
    # one knee down, one up
    _draw_limb(draw, cx + 8, hip_y, cx - 25, hip_y + 130)
    _draw_limb(draw, cx + 8, hip_y, cx + 45, hip_y + 80)


def pose_fist_clenched(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # arms bent, fists at hips
    _draw_limb(draw, cx, shoulder_y, cx - 35, shoulder_y + 70)
    _draw_limb(draw, cx - 35, shoulder_y + 70, cx - 25, shoulder_y + 110)
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 70)
    _draw_limb(draw, cx + 35, shoulder_y + 70, cx + 25, shoulder_y + 110)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)


def pose_meditating(draw, cx, head_cy):
    head_cy = head_cy + 30
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 90
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # arms to knees
    _draw_limb(draw, cx, shoulder_y, cx - 50, shoulder_y + 90)
    _draw_limb(draw, cx, shoulder_y, cx + 50, shoulder_y + 90)
    # crossed legs
    _draw_limb(draw, cx, hip_y, cx - 50, shoulder_y + 110)
    _draw_limb(draw, cx, hip_y, cx + 50, shoulder_y + 110)


def pose_writing(draw, cx, head_cy):
    head_cy = head_cy + 40
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 90
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=8)
    # arms forward to book
    _draw_limb(draw, cx + 8, shoulder_y, cx - 30, shoulder_y + 90)
    _draw_limb(draw, cx + 8, shoulder_y, cx + 30, shoulder_y + 90)
    # crossed legs
    _draw_limb(draw, cx + 8, hip_y, cx - 45, hip_y + 70)
    _draw_limb(draw, cx + 8, hip_y, cx + 45, hip_y + 70)
    # book on lap
    draw.rectangle([cx - 45, shoulder_y + 85, cx + 45, shoulder_y + 100],
                   outline=STROKE_COLOR, width=3)


def pose_standing_window(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    _draw_limb(draw, cx, shoulder_y, cx - 40, shoulder_y - 20)
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 95)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)
    # window on left
    draw.rectangle([cx - 130, head_cy - 80, cx - 30, head_cy + 120],
                   outline=STROKE_COLOR, width=3)


def pose_staring_mirror(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # hands near face
    _draw_limb(draw, cx, shoulder_y, cx - 30, shoulder_y - 20)
    _draw_limb(draw, cx, shoulder_y, cx + 30, shoulder_y - 20)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)
    # mirror on right
    draw.rectangle([cx + 80, head_cy - 60, cx + 170, head_cy + 200],
                   outline=STROKE_COLOR, width=3)


def pose_walking_alone_path(draw, cx, head_cy):
    pose_walking(draw, cx, head_cy)
    # path
    draw.line([(60, 700), (cx, 580), (1220, 510)], fill=MUTED, width=3, joint="curve")


def pose_bowing_head(draw, cx, head_cy):
    head_cy = head_cy + 25
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy, lean=4)
    _draw_limb(draw, cx + 4, shoulder_y, cx - 35, shoulder_y + 95)
    _draw_limb(draw, cx + 4, shoulder_y, cx + 35, shoulder_y + 95)
    _draw_limb(draw, cx + 4, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx + 4, hip_y, cx + 30, hip_y + 115)


def pose_sun_rising(draw, cx, head_cy):
    pose_standing_tall(draw, cx, head_cy)
    # sun on right
    draw.ellipse([cx + 230, head_cy + 50, cx + 340, head_cy + 160],
                 outline=STROKE_COLOR, width=4)
    draw.line([(60, head_cy + 200), (1220, head_cy + 200)], fill=MUTED, width=3)


def pose_empty_chair(draw, cx, head_cy):
    # No character — just an empty chair
    chair_y = head_cy + 100
    draw.rectangle([cx - 50, chair_y, cx + 50, chair_y + 20],
                   outline=STROKE_COLOR, width=STROKE_WIDTH)
    draw.line([(cx - 50, chair_y), (cx - 50, chair_y - 120)],
              fill=STROKE_COLOR, width=STROKE_WIDTH)
    draw.line([(cx + 50, chair_y + 20), (cx + 50, chair_y + 140)],
              fill=STROKE_COLOR, width=STROKE_WIDTH)
    draw.line([(cx - 50, chair_y + 20), (cx - 50, chair_y + 140)],
              fill=STROKE_COLOR, width=STROKE_WIDTH)


def pose_clock_waiting(draw, cx, head_cy):
    pose_standing_tall(draw, cx, head_cy)
    # clock on upper left
    draw.ellipse([cx - 150, head_cy - 60, cx - 50, head_cy + 40],
                 outline=STROKE_COLOR, width=4)
    # hands
    _line(draw, cx - 100, head_cy - 10, cx - 100, head_cy - 40, width=3)
    _line(draw, cx - 100, head_cy - 10, cx - 75, head_cy - 10, width=3)


def pose_holding_light(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # one arm raised holding light
    _draw_limb(draw, cx, shoulder_y, cx - 25, shoulder_y - 60)
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 95)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)
    # light
    draw.ellipse([cx - 45, head_cy - 90, cx - 5, head_cy - 50],
                 outline=STROKE_COLOR, width=4)


def pose_standing_mountain_top(draw, cx, head_cy):
    pose_standing_tall(draw, cx, head_cy)
    # mountain peak
    draw.line([(40, 700), (cx, 540), (1240, 700)], fill=MUTED, width=4, joint="curve")


def pose_face_down(draw, cx, head_cy):
    # Lying down
    head_cy = head_cy + 130
    _draw_head(draw, cx - 110, head_cy)
    _line(draw, cx - 110 + HEAD_RADIUS, head_cy, cx + 90, head_cy + 5)
    # arms limp
    _draw_limb(draw, cx - 60, head_cy, cx - 60, head_cy + 45)
    _draw_limb(draw, cx - 20, head_cy, cx - 20, head_cy + 40)
    # legs limp
    _draw_limb(draw, cx + 40, head_cy + 5, cx + 40, head_cy + 45)
    _draw_limb(draw, cx + 80, head_cy + 5, cx + 80, head_cy + 40)
    # ground
    draw.line([(40, head_cy + 50), (1240, head_cy + 50)], fill=STROKE_COLOR, width=4)


def pose_two_paths(draw, cx, head_cy):
    pose_standing_tall(draw, cx, head_cy)
    # two diverging paths
    draw.line([(cx, 700), (cx - 280, 530)], fill=MUTED, width=3)
    draw.line([(cx, 700), (cx + 280, 530)], fill=MUTED, width=3)


def pose_arms_raised(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # both arms up
    _draw_limb(draw, cx, shoulder_y, cx - 30, shoulder_y - 60)
    _draw_limb(draw, cx, shoulder_y, cx + 30, shoulder_y - 60)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)


def pose_dark_room_alone(draw, cx, head_cy):
    pose_sitting_ground(draw, cx, head_cy)
    # window with light beam
    draw.rectangle([cx + 200, head_cy - 80, cx + 290, head_cy + 80],
                   outline=STROKE_COLOR, width=3)


def pose_handshake_self(draw, cx, head_cy):
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_head(draw, cx, head_cy)
    _draw_spine(draw, cx, head_cy)
    # hands clasped in front
    _draw_limb(draw, cx, shoulder_y, cx + 15, shoulder_y + 60)
    _draw_limb(draw, cx, shoulder_y, cx - 15, shoulder_y + 60)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)


def pose_looking_back(draw, cx, head_cy):
    # Head turned
    _draw_head(draw, cx - 15, head_cy)
    shoulder_y = head_cy + HEAD_RADIUS + 8
    hip_y = shoulder_y + 110
    _draw_spine(draw, cx, head_cy)
    _draw_limb(draw, cx, shoulder_y, cx - 35, shoulder_y + 95)
    _draw_limb(draw, cx, shoulder_y, cx + 35, shoulder_y + 95)
    _draw_limb(draw, cx, hip_y, cx - 30, hip_y + 115)
    _draw_limb(draw, cx, hip_y, cx + 30, hip_y + 115)
    # footprints behind
    for fx, fy in [(cx - 130, 670), (cx - 175, 685), (cx - 220, 660)]:
        draw.ellipse([fx - 7, fy - 7, fx + 7, fy + 7], outline=STROKE_COLOR, width=3)


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


# ============================================================
# Openverse background texture fetcher — free CC images, no API key
# ============================================================

# Curated search terms for backgrounds that fit the motivation aesthetic
BG_SEARCH_TERMS = [
    "concrete wall texture",
    "old paper texture",
    "minimalist wall",
    "dark stone wall",
    "foggy mountain",
    "empty room minimal",
    "cloudy sky minimal",
    "wood texture minimal",
    "blackboard texture",
    "desert landscape minimal",
    "winter forest",
    "empty road",
    "lonely tree",
    "minimalist architecture",
    "stone wall old",
]

_bg_cache = {}  # cache URLs per search term to avoid re-fetching

def _fetch_bg_image(search_term: str, cache_dir: str) -> str | None:
    """Fetch a free CC-licensed background image from Openverse.
    Returns local path, or None on failure.
    """
    if search_term in _bg_cache:
        cached = _bg_cache[search_term]
        if os.path.exists(cached):
            return cached

    try:
        r = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": search_term, "page_size": 5, "license_type": "all-cc"},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        results = r.json().get("results", [])
        if not results:
            return None
        # Try each result until one downloads successfully
        for item in results[:3]:
            url = item.get("url")
            if not url:
                continue
            try:
                img_r = requests.get(url, timeout=30)
                if img_r.status_code == 200 and len(img_r.content) > 5000:
                    out_path = os.path.join(cache_dir, f"bg_{hash(search_term) & 0xFFFFFFFF}.jpg")
                    with open(out_path, "wb") as f:
                        f.write(img_r.content)
                    _bg_cache[search_term] = out_path
                    return out_path
            except Exception:
                continue
    except Exception as e:
        print(f"[bg] Openverse fetch failed for '{search_term}': {e}")
    return None


def _prepare_background(bg_path: str | None, out_size: tuple[int, int]) -> Image.Image:
    """Load and process background image. Returns a PIL Image.
    If bg_path is None, returns a solid color fallback.
    """
    if bg_path and os.path.exists(bg_path):
        try:
            bg = Image.open(bg_path).convert("RGB")
            # Resize to cover canvas
            bg = bg.resize(out_size, Image.LANCZOS)
            # Darken slightly so white text + stick figure pop
            bg = ImageEnhance.Brightness(bg).enhance(0.85)
            # Add white overlay for readability
            overlay = Image.new("RGBA", out_size, (255, 255, 255, 90))
            bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
            return bg
        except Exception as e:
            print(f"[bg] failed to load bg image: {e}")

    # Fallback: solid color
    return Image.new("RGB", out_size, BG_FALLBACK)


# ============================================================
# Frame renderer — stick figure on background texture
# ============================================================

def render_pose_to_png(
    pose_name: str,
    out_path: str,
    caption: str = "",
    brand_pill: str = "DAILY DISCIPLINE",
    scene_num: int = 0,
    scene_total: int = 25,
    bg_search_term: str | None = None,
    bg_cache_dir: str | None = None,
) -> str:
    """Render one frame to PNG. Returns out_path.

    Layout (1280x720):
      - Background: free CC texture from Openverse (or solid color fallback)
      - Stick figure on left third (same character every frame)
      - Caption text on right two-thirds
      - Brand pill top-left, scene counter top-right
    """
    if pose_name not in POSE_REGISTRY:
        pose_name = "standing_tall"

    # 1. Get background
    bg_path = None
    if bg_search_term and bg_cache_dir:
        bg_path = _fetch_bg_image(bg_search_term, bg_cache_dir)
    bg_img = _prepare_background(bg_path, CANVAS)

    # 2. Create drawing context
    img = bg_img.copy()
    draw = ImageDraw.Draw(img)

    # 3. Brand pill top-left
    pill_font = _font(22, bold=True, mono=True)
    pill_w = int(draw.textlength(brand_pill, font=pill_font)) + 32
    pill_h = 22 + 18
    draw.rounded_rectangle(
        [MARGIN, 50, MARGIN + pill_w, 50 + pill_h],
        radius=pill_h // 2, fill=ACCENT_TINT,
    )
    draw.text((MARGIN + 16, 53), brand_pill, font=pill_font, fill=ACCENT)

    # 4. Scene counter top-right
    counter = f"{scene_num:02d} / {scene_total:02d}"
    c_font = _font(22, bold=True, mono=True)
    cw = int(draw.textlength(counter, font=c_font))
    draw.text((CANVAS[0] - MARGIN - cw, 53), counter, font=c_font, fill=MUTED)

    # 5. Stick figure on left third
    pose_func = POSE_REGISTRY[pose_name]
    fig_cx = CANVAS[0] // 4 + 20
    pose_func(draw, fig_cx, FIGURE_HEAD_CY)

    # 6. Caption on right two-thirds
    if caption:
        snippet = caption[:140]
        cap_font = _font(42, bold=True)
        max_w = CANVAS[0] // 2 - MARGIN
        lines = _wrap_text(snippet, cap_font, draw, max_w)
        line_h = int(42 * 1.18)
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
    os.makedirs("/tmp/poses_v7", exist_ok=True)
    test_captions = [
        "Discipline is choosing what you want most over what you want now.",
        "The body screams stop. The mind agrees. You ignore both.",
        "Walk alone. The path narrows. Most fall off.",
        "Get back up.",
        "The morning is cold. The work is hard. Begin anyway.",
        "Years pass. You are unrecognizable.",
    ]
    for i, name in enumerate(POSE_NAMES[:6]):
        out = f"/tmp/poses_v7/{name}.png"
        render_pose_to_png(
            name, out,
            caption=test_captions[i % len(test_captions)],
            scene_num=i + 1, scene_total=25,
            bg_search_term=BG_SEARCH_TERMS[i % len(BG_SEARCH_TERMS)],
            bg_cache_dir="/tmp/poses_v7",
        )
        print(f"  OK {name} ({os.path.getsize(out) // 1024} KB)")
    print(f"\nRendered 6 test poses to /tmp/poses_v7/")
