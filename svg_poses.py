"""Deterministic stick-figure SVG generator.

Why: AI image generators (Pollinations, Flux, etc.) can't keep a character
consistent across 25+ frames. Each frame gets a different-looking figure,
which makes the video look like AI slop.

Solution: hand-craft ONE stick figure character with ~30 pose templates.
Every video uses the same character, just different poses. The result is
clean, minimal, consistent — and FREE (no API calls, no rate limits).

Style: black line on cream background, slightly thicker stroke for that
"hand-drawn discipline" feel. Single character, sparse composition,
lots of negative space.

Poses are defined as functions that return SVG path data for the character's
body, arms, and legs in different positions. Each pose takes a center point
(x, y) and returns SVG markup.
"""
import os
import random
import textwrap
from PIL import Image
import config


# === Style constants ===
BG_COLOR = "#F5F1E8"          # warm cream/off-white
LINE_COLOR = "#1A1A1A"        # near-black
LINE_WIDTH = 4                # thicker = more "drawn" feel
CANVAS_W = 1280
CANVAS_H = 720
CHAR_HEIGHT = 280             # character is ~280px tall
HEAD_RADIUS = 32


def _wrap(func):
    """Decorator to give each pose function a name + description."""
    func._pose_name = func.__name__.replace("pose_", "")
    return func


# ============================================================
# POSE LIBRARY — each function returns SVG body parts for one pose
# Coordinate system: (0, 0) = top-left. Character is centered at (cx, cy)
# where cy is the HEAD center. Body extends downward from there.
# All poses designed for a 1280x720 canvas with character roughly centered.
# ============================================================

def _head(cx, cy, r=HEAD_RADIUS):
    """Head circle + subtle face direction indicator (small dot for eyes)."""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}"/>'


def _line(x1, y1, x2, y2, width=LINE_WIDTH):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE_COLOR}" stroke-width="{width}" stroke-linecap="round"/>'


def _path(d, width=LINE_WIDTH):
    return f'<path d="{d}" fill="none" stroke="{LINE_COLOR}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


@_wrap
def pose_standing_tall(cx, cy):
    """Standing upright, arms at sides, facing forward."""
    head = _head(cx, cy)
    # spine: from below head to pelvis
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # arms hang straight down
    l_arm = _line(cx - 4, cy + 70, cx - 40, cy + 160)
    r_arm = _line(cx + 4, cy + 70, cx + 40, cy + 160)
    # legs straight down, slightly apart
    l_leg = _line(cx, cy + 180, cx - 30, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 30, cy + 280)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_walking(cx, cy):
    """Mid-stride walking pose, leaning slightly forward."""
    head = _head(cx, cy)
    spine = _path(f"M {cx} {cy + HEAD_RADIUS} Q {cx + 8} {cy + 100} {cx + 5} {cy + 180}")
    # back arm swinging forward
    l_arm = _line(cx - 4, cy + 75, cx + 25, cy + 130)
    # front arm swinging back
    r_arm = _line(cx + 4, cy + 75, cx - 30, cy + 140)
    # back leg bent
    l_leg = _path(f"M {cx + 5} {cy + 180} L {cx - 20} {cy + 230} L {cx - 50} {cy + 250}")
    # front leg extended forward
    r_leg = _path(f"M {cx + 5} {cy + 180} L {cx + 30} {cy + 240} L {cx + 50} {cy + 270}")
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_running(cx, cy):
    """Running hard, body tilted forward, limbs extended."""
    head = _head(cx, cy)
    spine = _path(f"M {cx} {cy + HEAD_RADIUS} Q {cx + 15} {cy + 100} {cx + 20} {cy + 175}")
    # arms pumping
    l_arm = _line(cx - 4, cy + 75, cx - 35, cy + 110)
    r_arm = _line(cx + 4, cy + 75, cx + 45, cy + 130)
    # legs in sprint positions
    l_leg = _path(f"M {cx + 20} {cy + 175} L {cx - 25} {cy + 215} L {cx - 60} {cy + 200}")
    r_leg = _path(f"M {cx + 20} {cy + 175} L {cx + 40} {cy + 240} L {cx + 65} {cy + 270}")
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_sitting_ground(cx, cy):
    """Sitting on ground, knees up, head down — defeated or thinking."""
    head = _head(cx, cy + 40)  # head lower than standing
    spine = _path(f"M {cx} {cy + 40 + HEAD_RADIUS} Q {cx + 5} {cy + 100} {cx + 8} {cy + 160}")
    # arms wrapped around knees
    l_arm = _path(f"M {cx - 4} {cy + 80} Q {cx - 30} {cy + 130} {cx - 50} {cy + 180}")
    r_arm = _path(f"M {cx + 4} {cy + 80} Q {cx + 30} {cy + 130} {cx + 50} {cy + 180}")
    # legs bent up to chest
    l_leg = _path(f"M {cx + 8} {cy + 160} L {cx - 30} {cy + 220} L {cx - 50} {cy + 180}")
    r_leg = _path(f"M {cx + 8} {cy + 160} L {cx + 40} {cy + 220} L {cx + 50} {cy + 180}")
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_kneeling(cx, cy):
    """One knee on ground, head bowed — prayer or reflection."""
    head = _head(cx, cy + 30)
    spine = _path(f"M {cx} {cy + 30 + HEAD_RADIUS} Q {cx + 3} {cy + 90} {cx + 5} {cy + 170}")
    # both arms reaching forward/down
    l_arm = _line(cx - 4, cy + 80, cx - 30, cy + 170)
    r_arm = _line(cx + 4, cy + 80, cx + 30, cy + 170)
    # one leg kneeling, one leg forward
    l_leg = _path(f"M {cx + 5} {cy + 170} L {cx - 25} {cy + 250} L {cx - 25} {cy + 280}")
    r_leg = _path(f"M {cx + 5} {cy + 170} L {cx + 40} {cy + 230} L {cx + 70} {cy + 240}")
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_looking_up(cx, cy):
    """Standing, head tilted back, looking at sky — aspiration."""
    head = _head(cx, cy - 10)  # head slightly up
    spine = _line(cx, cy - 10 + HEAD_RADIUS, cx, cy + 175)
    # arms relaxed at sides
    l_arm = _line(cx - 4, cy + 70, cx - 30, cy + 160)
    r_arm = _line(cx + 4, cy + 70, cx + 30, cy + 160)
    l_leg = _line(cx, cy + 175, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 175, cx + 25, cy + 280)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_climbing(cx, cy):
    """Reaching up, one arm extended — climbing."""
    head = _head(cx, cy)
    spine = _path(f"M {cx} {cy + HEAD_RADIUS} Q {cx + 5} {cy + 100} {cx} {cy + 180}")
    # one arm reaching up
    l_arm = _line(cx - 4, cy + 60, cx - 30, cy + 10)
    # other arm pulling down
    r_arm = _line(cx + 4, cy + 75, cx + 25, cy + 130)
    # legs in climbing stance
    l_leg = _path(f"M {cx} {cy + 180} L {cx - 30} {cy + 240} L {cx - 50} {cy + 250}")
    r_leg = _path(f"M {cx} {cy + 180} L {cx + 20} {cy + 230} L {cx + 45} {cy + 270}")
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_pointing_forward(cx, cy):
    """Standing, one arm extended forward — direction, purpose."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # back arm at side
    l_arm = _line(cx - 4, cy + 75, cx - 30, cy + 160)
    # front arm pointing forward (horizontal)
    r_arm = _line(cx + 4, cy + 75, cx + 80, cy + 90)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_pushing_boulder(cx, cy):
    """Leaning forward, both hands pushing an invisible boulder."""
    head = _head(cx, cy)
    spine = _path(f"M {cx} {cy + HEAD_RADIUS} Q {cx + 20} {cy + 100} {cx + 25} {cy + 175}")
    # both arms forward, pushing
    l_arm = _path(f"M {cx - 4} {cy + 75} L {cx + 50} {cy + 100} L {cx + 80} {cy + 105}")
    r_arm = _path(f"M {cx + 4} {cy + 75} L {cx + 55} {cy + 115} L {cx + 85} {cy + 120}")
    # legs in pushing stance, bent
    l_leg = _path(f"M {cx + 25} {cy + 175} L {cx - 10} {cy + 230} L {cx - 30} {cy + 270}")
    r_leg = _path(f"M {cx + 25} {cy + 175} L {cx + 30} {cy + 235} L {cx + 20} {cy + 280}")
    # the boulder itself
    boulder = f'<circle cx="{cx + 130}" cy="{cy + 130}" r="55" fill="none" stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}"/>'
    return head + spine + l_arm + r_arm + l_leg + r_leg + boulder


@_wrap
def pose_carrying_load(cx, cy):
    """Walking with a heavy load on back — burden."""
    head = _head(cx, cy)
    spine = _path(f"M {cx} {cy + HEAD_RADIUS} Q {cx + 10} {cy + 100} {cx + 8} {cy + 180}")
    l_arm = _line(cx - 4, cy + 75, cx - 20, cy + 130)
    r_arm = _line(cx + 4, cy + 75, cx + 20, cy + 130)
    l_leg = _path(f"M {cx + 8} {cy + 180} L {cx - 20} {cy + 240} L {cx - 35} {cy + 280}")
    r_leg = _path(f"M {cx + 8} {cy + 180} L {cx + 25} {cy + 235} L {cx + 40} {cy + 270}")
    # the load — a heavy box shape on the back/shoulders
    load = f'<rect x="{cx - 50}" y="{cy - 30}" width="60" height="60" fill="none" stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}"/>'
    return head + spine + l_arm + r_arm + l_leg + r_leg + load


@_wrap
def pose_standing_alone_hill(cx, cy):
    """Standing on top of a hill, looking out."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    l_arm = _line(cx - 4, cy + 75, cx - 35, cy + 160)
    r_arm = _line(cx + 4, cy + 75, cx + 35, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # hill — gentle curve
    hill = _path(f"M 100 {CANVAS_H - 50} Q {cx} {CANVAS_H - 200} {CANVAS_W - 100} {CANVAS_H - 50}", width=3)
    return head + spine + l_arm + r_arm + l_leg + r_leg + hill


@_wrap
def pose_facing_wall(cx, cy):
    """Standing facing a wall — obstacle."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # both hands touching wall
    l_arm = _line(cx - 4, cy + 80, cx - 50, cy + 90)
    r_arm = _line(cx + 4, cy + 80, cx - 50, cy + 100)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # the wall — vertical line on left
    wall = _line(cx - 70, cy - 80, cx - 70, cy + 280, width=5)
    return head + spine + l_arm + r_arm + l_leg + r_leg + wall


@_wrap
def pose_arms_crossed(cx, cy):
    """Standing, arms crossed — defiance or self-containment."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # arms crossed over chest
    l_arm = _line(cx - 4, cy + 80, cx + 30, cy + 110)
    r_arm = _line(cx + 4, cy + 80, cx - 30, cy + 110)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_falling(cx, cy):
    """Mid-fall, body horizontal — failure, collapse."""
    head = _head(cx + 80, cy + 100)  # head to the right, body horizontal
    spine = _line(cx + 80 - HEAD_RADIUS, cy + 100, cx - 50, cy + 90)
    # arms splayed
    l_arm = _line(cx + 30, cy + 95, cx + 30, cy + 50)
    r_arm = _line(cx + 10, cy + 95, cx + 10, cy + 145)
    # legs splayed
    l_leg = _line(cx - 30, cy + 90, cx - 30, cy + 50)
    r_leg = _line(cx - 50, cy + 90, cx - 50, cy + 140)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_rising_up(cx, cy):
    """Halfway up from ground, one hand on floor — getting back up."""
    head = _head(cx, cy + 60)
    spine = _path(f"M {cx} {cy + 60 + HEAD_RADIUS} Q {cx + 10} {cy + 120} {cx + 15} {cy + 175}")
    # one hand on ground for support
    l_arm = _line(cx - 4, cy + 100, cx - 50, cy + 200)
    # other arm reaching forward
    r_arm = _line(cx + 4, cy + 100, cx + 40, cy + 130)
    # one knee down, one foot planted
    l_leg = _path(f"M {cx + 15} {cy + 175} L {cx - 20} {cy + 250} L {cx - 20} {cy + 280}")
    r_leg = _path(f"M {cx + 15} {cy + 175} L {cx + 50} {cy + 230} L {cx + 70} {cy + 280}")
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_fist_clenched(cx, cy):
    """Standing, fists clenched at sides — resolve."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # arms bent slightly, fists at hip level
    l_arm = _path(f"M {cx - 4} {cy + 75} L {cx - 35} {cy + 130} L {cx - 30} {cy + 165}")
    r_arm = _path(f"M {cx + 4} {cy + 75} L {cx + 35} {cy + 130} L {cx + 30} {cy + 165}")
    l_leg = _line(cx, cy + 180, cx - 30, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 30, cy + 280)
    # small fist circles
    l_fist = f'<circle cx="{cx - 30}" cy="{cy + 170}" r="8" fill="none" stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}"/>'
    r_fist = f'<circle cx="{cx + 30}" cy="{cy + 170}" r="8" fill="none" stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}"/>'
    return head + spine + l_arm + r_arm + l_leg + r_leg + l_fist + r_fist


@_wrap
def pose_meditating(cx, cy):
    """Cross-legged sitting, hands on knees — meditation."""
    head = _head(cx, cy + 20)
    spine = _path(f"M {cx} {cy + 20 + HEAD_RADIUS} Q {cx + 3} {cy + 90} {cx + 5} {cy + 150}")
    # arms down to knees
    l_arm = _line(cx - 4, cy + 80, cx - 50, cy + 175)
    r_arm = _line(cx + 4, cy + 80, cx + 50, cy + 175)
    # crossed legs
    l_leg = _path(f"M {cx + 5} {cy + 150} L {cx - 50} {cy + 200} L {cx + 10} {cy + 220}")
    r_leg = _path(f"M {cx + 5} {cy + 150} L {cx + 50} {cy + 200} L {cx - 10} {cy + 220}")
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_writing(cx, cy):
    """Sitting, hunched forward, writing in book — discipline, journaling."""
    head = _head(cx, cy + 40)
    spine = _path(f"M {cx} {cy + 40 + HEAD_RADIUS} Q {cx + 8} {cy + 100} {cx + 10} {cy + 150}")
    # both arms forward toward book
    l_arm = _line(cx - 4, cy + 80, cx - 30, cy + 170)
    r_arm = _line(cx + 4, cy + 80, cx + 30, cy + 170)
    # legs crossed under
    l_leg = _path(f"M {cx + 10} {cy + 150} L {cx - 40} {cy + 210} L {cx} {cy + 230}")
    r_leg = _path(f"M {cx + 10} {cy + 150} L {cx + 40} {cy + 210} L {cx} {cy + 230}")
    # book on lap
    book = f'<rect x="{cx - 40}" y="{cy + 165}" width="80" height="20" fill="none" stroke="{LINE_COLOR}" stroke-width="3"/>'
    return head + spine + l_arm + r_arm + l_leg + r_leg + book


@_wrap
def pose_standing_window(cx, cy):
    """Standing by a window, looking out — contemplation."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # one arm up near head (touching window frame)
    l_arm = _line(cx - 4, cy + 75, cx - 40, cy + 50)
    r_arm = _line(cx + 4, cy + 75, cx + 30, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # window frame on left
    window = f'<rect x="{cx - 120}" y="{cy - 80}" width="100" height="180" fill="none" stroke="{LINE_COLOR}" stroke-width="3"/>'
    window_div = _line(cx - 70, cy - 80, cx - 70, cy + 100, width=2)
    return head + spine + l_arm + r_arm + l_leg + r_leg + window + window_div


@_wrap
def pose_staring_mirror(cx, cy):
    """Standing facing a mirror — self-reflection."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # both arms raised slightly, hands near face
    l_arm = _path(f"M {cx - 4} {cy + 75} L {cx - 30} {cy + 60} L {cx - 25} {cy + 30}"
)
    r_arm = _path(f"M {cx + 4} {cy + 75} L {cx + 30} {cy + 60} L {cx + 25} {cy + 30}")
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # mirror — rectangle on right
    mirror = f'<rect x="{cx + 80}" y="{cy - 60}" width="80" height="220" fill="none" stroke="{LINE_COLOR}" stroke-width="3"/>'
    return head + spine + l_arm + r_arm + l_leg + r_leg + mirror


@_wrap
def pose_walking_alone_path(cx, cy):
    """Walking alone on a long path — journey."""
    head = _head(cx, cy)
    spine = _path(f"M {cx} {cy + HEAD_RADIUS} Q {cx + 8} {cy + 100} {cx + 5} {cy + 180}")
    l_arm = _line(cx - 4, cy + 75, cx + 25, cy + 130)
    r_arm = _line(cx + 4, cy + 75, cx - 30, cy + 140)
    l_leg = _path(f"M {cx + 5} {cy + 180} L {cx - 20} {cy + 230} L {cx - 50} {cy + 250}")
    r_leg = _path(f"M {cx + 5} {cy + 180} L {cx + 30} {cy + 240} L {cx + 50} {cy + 270}")
    # path stretching forward
    path_lines = _path(f"M {cx - 200} {CANVAS_H - 30} Q {cx} {CANVAS_H - 100} {cx + 400} {CANVAS_H - 200}", width=2)
    return head + spine + l_arm + r_arm + l_leg + r_leg + path_lines


@_wrap
def pose_bowing_head(cx, cy):
    """Standing, head bowed — humility, grief, respect."""
    head = _head(cx, cy + 30)  # head lower
    spine = _path(f"M {cx} {cy + 30 + HEAD_RADIUS} Q {cx + 5} {cy + 100} {cx} {cy + 180}")
    l_arm = _line(cx - 4, cy + 75, cx - 30, cy + 160)
    r_arm = _line(cx + 4, cy + 75, cx + 30, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_sun_rising(cx, cy):
    """Standing, facing a rising sun — new beginning."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    l_arm = _line(cx - 4, cy + 75, cx - 30, cy + 160)
    r_arm = _line(cx + 4, cy + 75, cx + 30, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # sun on horizon
    sun = f'<circle cx="{cx + 250}" cy="{CANVAS_H - 100}" r="50" fill="none" stroke="{LINE_COLOR}" stroke-width="3"/>'
    horizon = _line(cx - 200, CANVAS_H - 100, CANVAS_W - 50, CANVAS_H - 100, width=2)
    return head + spine + l_arm + r_arm + l_leg + r_leg + sun + horizon


@_wrap
def pose_empty_chair(cx, cy):
    """An empty chair — absence, reflection on what was."""
    # No character in this frame — just the chair
    # Chair seat
    seat = f'<rect x="{cx - 50}" y="{cy + 130}" width="100" height="15" fill="none" stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}"/>'
    # Chair back
    back = _line(cx - 50, cy + 130, cx - 50, cy + 20)
    # Front legs
    fl = _line(cx + 50, cy + 145, cx + 50, cy + 250)
    # Back legs
    bl = _line(cx - 50, cy + 145, cx - 50, cy + 250)
    return seat + back + fl + bl


@_wrap
def pose_clock_waiting(cx, cy):
    """Standing, looking at a clock — time, urgency."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    l_arm = _line(cx - 4, cy + 75, cx - 50, cy + 80)  # arm raised toward clock
    r_arm = _line(cx + 4, cy + 75, cx + 30, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # clock on upper left
    clock_face = f'<circle cx="{cx - 130}" cy="{cy - 40}" r="45" fill="none" stroke="{LINE_COLOR}" stroke-width="3"/>'
    clock_hand1 = _line(cx - 130, cy - 40, cx - 130, cy - 70, width=3)
    clock_hand2 = _line(cx - 130, cy - 40, cx - 105, cy - 40, width=3)
    return head + spine + l_arm + r_arm + l_leg + r_leg + clock_face + clock_hand1 + clock_hand2


@_wrap
def pose_holding_light(cx, cy):
    """Standing, holding up a small light/candle — hope, guidance."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # one arm raised holding light
    l_arm = _line(cx - 4, cy + 70, cx - 20, cy + 20)
    r_arm = _line(cx + 4, cy + 75, cx + 30, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # small light/candle above hand
    light = f'<circle cx="{cx - 20}" cy="{cy - 5}" r="15" fill="none" stroke="{LINE_COLOR}" stroke-width="3"/>'
    return head + spine + l_arm + r_arm + l_leg + r_leg + light


@_wrap
def pose_standing_mountain_top(cx, cy):
    """On a mountain peak, looking down at the world — achievement."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    l_arm = _line(cx - 4, cy + 75, cx - 35, cy + 160)
    r_arm = _line(cx + 4, cy + 75, cx + 35, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # mountain peak silhouette
    peak = _path(f"M 50 {CANVAS_H - 30} L {cx} {CANVAS_H - 100} L {CANVAS_W - 50} {CANVAS_H - 30}", width=3)
    return head + spine + l_arm + r_arm + l_leg + r_leg + peak


@_wrap
def pose_face_down(cx, cy):
    """Lying face down on the ground — defeat, exhaustion."""
    # horizontal body on ground
    head = _head(cx - 100, cy + 180)
    spine = _line(cx - 100 + HEAD_RADIUS, cy + 180, cx + 80, cy + 185)
    # arms limp
    l_arm = _line(cx - 60, cy + 185, cx - 60, cy + 220)
    r_arm = _line(cx - 30, cy + 185, cx - 30, cy + 215)
    # legs limp
    l_leg = _line(cx + 40, cy + 185, cx + 40, cy + 220)
    r_leg = _line(cx + 70, cy + 185, cx + 70, cy + 215)
    # ground line
    ground = _line(50, cy + 230, CANVAS_W - 50, cy + 230, width=3)
    return head + spine + l_arm + r_arm + l_leg + r_leg + ground


@_wrap
def pose_two_paths(cx, cy):
    """Standing at a fork in the road — choice."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    l_arm = _line(cx - 4, cy + 75, cx - 50, cy + 90)  # arm gesturing left
    r_arm = _line(cx + 4, cy + 75, cx + 50, cy + 90)  # arm gesturing right
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # two paths diverging
    path1 = _path(f"M {cx} {CANVAS_H - 30} L {cx - 250} {CANVAS_H - 200}", width=2)
    path2 = _path(f"M {cx} {CANVAS_H - 30} L {cx + 250} {CANVAS_H - 200}", width=2)
    return head + spine + l_arm + r_arm + l_leg + r_leg + path1 + path2


@_wrap
def pose_arms_raised(cx, cy):
    """Both arms raised up — triumph, surrender, or reaching."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    l_arm = _line(cx - 4, cy + 70, cx - 30, cy + 10)
    r_arm = _line(cx + 4, cy + 70, cx + 30, cy + 10)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_dark_room_alone(cx, cy):
    """Sitting alone in a dark room — solitude, isolation."""
    # sitting figure
    head = _head(cx, cy + 60)
    spine = _path(f"M {cx} {cy + 60 + HEAD_RADIUS} Q {cx + 5} {cy + 130} {cx + 8} {cy + 180}")
    l_arm = _line(cx - 4, cy + 100, cx - 30, cy + 175)
    r_arm = _line(cx + 4, cy + 100, cx + 30, cy + 175)
    l_leg = _path(f"M {cx + 8} {cy + 180} L {cx - 35} {cy + 230} L {cx - 35} {cy + 270}")
    r_leg = _path(f"M {cx + 8} {cy + 180} L {cx + 35} {cy + 230} L {cx + 35} {cy + 270}")
    # window letting in a sliver of light
    window = f'<rect x="{cx + 200}" y="{cy - 50}" width="80" height="150" fill="none" stroke="{LINE_COLOR}" stroke-width="3"/>'
    light = _path(f"M {cx + 240} {cy + 100} L {cx + 100} {cy + 200}", width=2)
    return head + spine + l_arm + r_arm + l_leg + r_leg + window + light


@_wrap
def pose_handshake_self(cx, cy):
    """Both hands clasped together in front — commitment to self."""
    head = _head(cx, cy)
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    # both arms meeting in front of chest
    l_arm = _path(f"M {cx - 4} {cy + 75} L {cx + 5} {cy + 110}"
)
    r_arm = _path(f"M {cx + 4} {cy + 75} L {cx - 5} {cy + 110}")
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    return head + spine + l_arm + r_arm + l_leg + r_leg


@_wrap
def pose_looking_back(cx, cy):
    """Standing, head turned to look behind — regret or reflection."""
    head = _head(cx - 15, cy)  # head turned
    spine = _line(cx, cy + HEAD_RADIUS, cx, cy + 180)
    l_arm = _line(cx - 4, cy + 75, cx - 30, cy + 160)
    r_arm = _line(cx + 4, cy + 75, cx + 30, cy + 160)
    l_leg = _line(cx, cy + 180, cx - 25, cy + 280)
    r_leg = _line(cx, cy + 180, cx + 25, cy + 280)
    # faint footprints trailing behind
    fp1 = f'<circle cx="{cx - 120}" cy="{CANVAS_H - 60}" r="6" fill="none" stroke="{LINE_COLOR}" stroke-width="2"/>'
    fp2 = f'<circle cx="{cx - 160}" cy="{CANVAS_H - 40}" r="6" fill="none" stroke="{LINE_COLOR}" stroke-width="2"/>'
    fp3 = f'<circle cx="{cx - 200}" cy="{CANVAS_H - 70}" r="6" fill="none" stroke="{LINE_COLOR}" stroke-width="2"/>'
    return head + spine + l_arm + r_arm + l_leg + r_leg + fp1 + fp2 + fp3


# ============================================================
# POSE REGISTRY — used by script_gen.py to pick a pose per scene
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


def render_svg(pose_name: str, scene_text: str = "") -> str:
    """Render a complete SVG for the given pose + optional scene text overlay."""
    pose_func = POSE_REGISTRY[pose_name]
    # Center the character roughly in the lower-middle of the canvas
    cx, cy = CANVAS_W // 2, 220
    body_svg = pose_func(cx, cy)

    # Optional scene text — small caption at the bottom
    text_overlay = ""
    if scene_text:
        # Truncate to ~80 chars and wrap
        snippet = scene_text[:120].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text_overlay = f'<text x="{CANVAS_W // 2}" y="{CANVAS_H - 40}" text-anchor="middle" font-family="Georgia, serif" font-size="22" font-style="italic" fill="#666">{snippet}</text>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">
  <rect width="{CANVAS_W}" height="{CANVAS_H}" fill="{BG_COLOR}"/>
  {body_svg}
  {text_overlay}
</svg>'''


def svg_to_png(svg_path: str, png_path: str, width: int = None, height: int = None):
    """Convert SVG to PNG using rsvg-convert (preferred) or cairosvg."""
    w = width or config.IMAGE_WIDTH
    h = height or config.IMAGE_HEIGHT

    # Try rsvg-convert (fastest, system package)
    import subprocess
    try:
        subprocess.run(
            ["rsvg-convert", "-w", str(w), "-h", str(h), "-o", png_path, svg_path],
            check=True, capture_output=True,
        )
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Try cairosvg (pure Python)
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=w, output_height=h)
        return
    except ImportError:
        pass

    # Try Inkscape
    try:
        subprocess.run(
            ["inkscape", "--export-type=png", "--export-width", str(w), "--export-height", str(h),
             "--export-filename", png_path, svg_path],
            check=True, capture_output=True,
        )
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    raise RuntimeError(
        "no SVG-to-PNG converter available. Install one of: librsvg2-bin (rsvg-convert), "
        "cairosvg (pip), or inkscape."
    )


if __name__ == "__main__":
    # Render all poses to /tmp for visual inspection
    os.makedirs("/tmp/poses", exist_ok=True)
    for name in POSE_NAMES:
        svg = render_svg(name, scene_text="")
        svg_path = f"/tmp/poses/{name}.svg"
        png_path = f"/tmp/poses/{name}.png"
        with open(svg_path, "w") as f:
            f.write(svg)
        try:
            svg_to_png(svg_path, png_path)
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    print(f"\n{len(POSE_NAMES)} poses rendered to /tmp/poses/")
