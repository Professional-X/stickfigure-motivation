"""Premium cinematic thumbnails.

Layout (1280x720, YouTube standard):
  - Background: a striking still extracted from one of the video's Mixkit clips
    (cover-cropped to 16:9, color-graded to match the video).
  - Bottom gradient (transparent -> dark) for title legibility.
  - Bold title text (white fill, thick dark outline) — large, high-contrast.
  - Channel handle bottom-right.
  - 3 variants (different still / text placement) so the best can be picked.

Renders with Pillow (font stroke for outline). Uses DejaVu Sans Bold, which is
present on the GitHub runner (fonts-dejavu ships with Ubuntu) and in this
sandbox. Falls back to Pillow's default font if absent.
"""
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720

# Search paths for a heavy sans font (first match wins).
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
]
ACCENT = (210, 47, 47)        # red accent bar
TEXT_FILL = (255, 255, 255)
TEXT_OUTLINE = (0, 0, 0)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def extract_still(clip_path: str, out_path: str, t_offset: float = 1.5) -> str:
    """Extract a 1280x720 cover-cropped still from a clip at t_offset seconds."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{t_offset:.2f}",
        "-i", clip_path,
        "-frames:v", "1",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
               "eq=contrast=1.08:saturation=1.10:brightness=-0.02,"
               "colorbalance=rs=-0.05:bs=0.10:rh=0.06:bh=-0.06,vignette",
        out_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out_path):
        # try at t=0 if the clip is shorter than the offset
        cmd[3] = "0.1"
        res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"still extraction failed: {res.stderr[-300:]}")
    return out_path


def grade_still(still_path: str, out_path: str) -> str:
    """Grade a still IMAGE (the topical AI stills from premium/visuals.py) into a
    1280x720 PNG with the same cinematic grade as extract_still. extract_still's
    `-ss` seek fails on single-frame image inputs, so this is the image-path
    equivalent (no seek, one frame)."""
    cmd = [
        "ffmpeg", "-y", "-i", still_path, "-frames:v", "1",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
               f"crop={W}:{H},"
               "eq=contrast=1.08:saturation=1.10:brightness=-0.02,"
               "colorbalance=rs=-0.05:bs=0.10:rh=0.06:bh=-0.06,vignette",
        out_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"grade_still failed: {res.stderr[-300:]}")
    return out_path


def _gradient_overlay(img: Image.Image, start_frac: float, alpha_max: int) -> Image.Image:
    """Return an RGBA gradient (transparent -> dark) composited onto img."""
    w, h = img.size
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gp = grad.load()
    start = int(h * start_frac)
    for y in range(start, h):
        t = (y - start) / max(h - start, 1)
        a = int(alpha_max * t)
        for x in range(w):
            gp[x, y] = (0, 0, 0, a)
    return Image.alpha_composite(img.convert("RGBA"), grad)


def _draw_text(draw: ImageDraw.ImageDraw, text: str, cx: int, cy: int,
               font: ImageFont.FreeTypeFont, fill, outline, stroke: int = 7):
    """Draw centered multi-line text with a thick outline."""
    lines = text.upper().split("\n")
    # measure
    line_h = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=stroke)
        line_h.append(bbox[3] - bbox[1])
    total_h = sum(line_h) + 6 * (len(lines) - 1)
    y = cy - total_h // 2
    for i, ln in enumerate(lines):
        bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=stroke)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y), ln, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=outline)
        y += line_h[i] + 6


def render_thumbnail(still_path: str, title_text: str, out_path: str,
                     channel_handle: str = "", variant: str = "A") -> str:
    """Render one thumbnail variant. title_text may contain \\n for 2 lines."""
    base = Image.open(still_path).convert("RGBA")
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)

    if variant == "A":
        # title bottom-center, large; bottom gradient for legibility
        base = _gradient_overlay(base, start_frac=0.55, alpha_max=170)
        font_size = 118
        cy = int(H * 0.78)
    elif variant == "B":
        # title center, even larger + red accent bar above
        base = _gradient_overlay(base, start_frac=0.30, alpha_max=120)
        base = _gradient_overlay(base, start_frac=0.62, alpha_max=140)
        font_size = 132
        cy = H // 2 + 10
    else:  # "C"
        # title upper-third + heavy bottom gradient
        base = _gradient_overlay(base, start_frac=0.50, alpha_max=185)
        font_size = 108
        cy = int(H * 0.30)

    draw = ImageDraw.Draw(base)
    font = _load_font(font_size)

    # red accent bar (variants B only) for click energy
    if variant == "B":
        draw.rectangle([W // 2 - 90, cy - 110, W // 2 + 90, cy - 96], fill=ACCENT)

    _draw_text(draw, title_text, W // 2, cy, font, TEXT_FILL, TEXT_OUTLINE,
               stroke=max(6, font_size // 16))

    # channel handle bottom-right
    if channel_handle:
        handle = channel_handle if channel_handle.startswith("@") else "@" + channel_handle
        hf = _load_font(34)
        hbbox = draw.textbbox((0, 0), handle, font=hf, stroke_width=4)
        hw = hbbox[2] - hbbox[0]
        draw.text((W - 22 - hw, H - 50), handle, font=hf, fill=TEXT_FILL,
                  stroke_width=4, stroke_fill=TEXT_OUTLINE)

    base.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"[thumbnail] variant {variant}: {out_path} ({os.path.getsize(out_path)//1024} KB)")
    return out_path


def render_variants(still_paths: list[str], title_text: str, out_dir: str,
                    channel_handle: str = "") -> list[str]:
    """Render 3 thumbnail variants using different stills. Returns [path A,B,C]."""
    os.makedirs(out_dir, exist_ok=True)
    # ensure we have up to 3 stills; reuse if fewer clips
    stills = list(still_paths)
    while len(stills) < 3:
        stills.append(still_paths[0])

    # 2-line wrap for the title if it has 2 words (more impactful)
    words = title_text.split()
    if len(words) >= 2 and len(title_text) <= 14:
        mid = len(words) // 2
        two_line = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
    else:
        two_line = title_text

    out = []
    for i, variant in enumerate("ABC"):
        sp = stills[i]
        out_path = os.path.join(out_dir, f"thumbnail_{variant}.png")
        text = two_line if variant in ("A", "C") else title_text
        render_thumbnail(sp, text, out_path, channel_handle, variant)
        out.append(out_path)
    return out
