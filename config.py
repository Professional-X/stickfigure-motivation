"""Central config — change models, voice, themes here.

Provider swap (v3): OpenRouter (free Nemotron Ultra 550B) for LLM +
Pollinations.ai (free, no auth) for images. Total cost: $0/video.

Pollinations rate-limits to ~1 image / 45s on free tier. With 25 scenes that's
~20 min of waiting — annoying but free. Set CLOUDFLARE_API_TOKEN +
CLOUDFLARE_ACCOUNT_ID env vars and IMAGE_PROVIDER=cloudflare to switch to
Cloudflare Workers AI (10k free neurons/day, much faster, no rate limit).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# LLM PROVIDER — defaults to OpenRouter (free Nemotron Ultra)
# ============================================================
LLM_PROVIDER = os.environ.get("LLM_PROVIDER") or "openrouter"

# --- OpenRouter (https://openrouter.ai/keys) ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or ""
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Free models on OpenRouter right now (verified working):
#   nvidia/nemotron-3-ultra-550b-a55b:free  ← default, best quality
#   nvidia/nemotron-3.5-lightning:free       ← faster, lower quality
# Swap freely — both have 1M context.
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL") or "nvidia/nemotron-3-ultra-550b-a55b:free"

# --- NVIDIA Build (legacy, kept for reference) ---
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY") or ""
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL") or "nvidia/nemotron-3-ultra-550b-a55b"

# Convenience: which key + base URL + model to actually use
if LLM_PROVIDER == "nvidia":
    LLM_API_KEY = NVIDIA_API_KEY
    LLM_BASE_URL = NVIDIA_BASE_URL
    LLM_MODEL = NVIDIA_MODEL
else:  # openrouter (default)
    LLM_API_KEY = OPENROUTER_API_KEY
    LLM_BASE_URL = OPENROUTER_BASE_URL
    LLM_MODEL = OPENROUTER_MODEL


# ============================================================
# IMAGE PROVIDER — defaults to Pollinations.ai (free, no auth)
# ============================================================
IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER") or "pollinations"

# --- Pollinations.ai (free, no API key, ~1 req / 45s rate limit) ---
POLLINATIONS_URL = "https://image.pollinations.ai/prompt"
POLLINATIONS_MODEL = os.environ.get("POLLINATIONS_MODEL") or "flux"  # 'flux' | 'turbo'
POLLINATIONS_DELAY = 50  # seconds between calls — proven safe under their rate limiter

# --- Cloudflare Workers AI (free 10k neurons/day, much faster, needs signup) ---
# Get account ID: https://dash.cloudflare.com → right sidebar
# Get API token: https://dash.cloudflare.com/profile/api-tokens → "Workers AI" template
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or ""
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or ""
CLOUDFLARE_FLUX_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
)

# --- HuggingFace (legacy, kept for reference — free tier dropped Flux) ---
HF_API_TOKEN = os.environ.get("HF_API_TOKEN") or ""
HF_MODEL_ID = "black-forest-labs/FLUX.1-dev"
HF_ENDPOINT = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL_ID}"

# --- NVIDIA Flux (legacy, kept for reference) ---
NVIDIA_IMAGE_API_KEY = os.environ.get("NVIDIA_API_KEY") or ""
NVIDIA_IMAGE_ENDPOINT = "https://ai.api.nvidia.org/v1/genai/black-forest-labs/flux.1-dev"

# Image specs (used by both providers)
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
IMAGE_SEED = 42  # fixed base seed for visual consistency across scenes


# ============================================================
# TTS — Edge-TTS (free, no API key)
# ============================================================
TTS_VOICE = "en-US-AndrewMultilingualNeural"  # warm, natural, softer male (was en-US-GuyNeural — too hard/robotic for the "softer + human" brief)
TTS_RATE = "-8%"  # slightly slower for gravitas

# Narration playback speed. 1.0 = as-synthesized; 1.4 = the "sounds real and
# good" cadence the user picked after A/B-listening (matches YouTube's 1.4x
# playback). Applied as an atempo time-stretch on each scene's assembled audio
# BEFORE durations/timings are measured, so the visual cuts, Whisper subtitles
# and ducked music all stay perfectly aligned with the faster voice. atempo
# preserves pitch (WSOLA), so the voice stays natural — no chipmunk effect.
NARRATION_SPEED = 1.4

# Topical AI scene frames (v2): ONE unique generated still PER CUT. The
# rapid-cut montage breaks each scene into 1.6-4.0s segments (~60 cuts per
# video) and every single cut gets its own unique, never-reused frame — no
# cycling a small pool. Free providers only, generated in parallel with a
# fallback chain so a cut never repeats even when some generations fail:
#   Pollinations flux -> Pollinations turbo -> Openverse CC photo ->
#   procedural unique gradient (guaranteed floor, zero repeats).
VISUALS_PER_CUT = True           # v2 mode: one unique image per cut
VISUALS_WORKERS = 4              # parallel image-generation workers
VISUALS_MAX_PER_VIDEO = 96       # hard cap on generated images per video
POLLINATIONS_REFERRER = "stickverse-motivation"  # anonymous tier w/ referrer

# Rapid-cut windows (seconds). The segment plan drives BOTH the editor's cuts
# and the AI frame generation (one unique frame per cut), so changing these
# changes the number of images per video. 2.2-4.4s keeps TV-drama pacing while
# keeping the per-cut frame count (~45-60) within the free image providers' reach.
CUT_MIN_SEG = 2.2
CUT_MAX_SEG = 4.4


# ============================================================
# Video specs
# ============================================================
SCENES_PER_VIDEO = 25        # ~30 sec per scene -> ~12-13 min total
                            # (was 35; reduced to fit Pollinations rate-limit comfortably)
KEN_BURNS_ZOOM = 1.15        # 15% zoom-in over each scene
KEN_BURNS_ZOOM_STEP = 0.0005 # zoompan increment per frame


# ============================================================
# Audio mix
# ============================================================
BG_MUSIC_VOLUME_DB = -22     # background music level (negative = quieter)
NARRATION_VOLUME_DB = 0      # narration at full


# ============================================================
# Paths
# ============================================================
OUTPUT_DIR = os.environ.get("VIDEO_OUTPUT_DIR") or "./output"
MUSIC_DIR = "./music"


# ============================================================
# Composio (YouTube upload)
# ============================================================
COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY") or ""
COMPOSIO_ENTITY_ID = os.environ.get("COMPOSIO_ENTITY_ID") or ""


# ============================================================
# YouTube defaults
# ============================================================
YOUTUBE_TAGS = [
    "motivation", "discipline", "stoicism", "mindset", "self improvement",
    "stick figure", "philosophy", "men", "focus", "hard work",
]
YOUTUBE_CATEGORY_ID = "22"  # People & Blogs
YOUTUBE_PRIVACY = "public"  # public | unlisted | private
