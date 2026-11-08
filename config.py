"""Central config — change models, voice, themes here.

Provider swap: now using OpenRouter (free Nemotron Ultra 550B) for LLM and
HuggingFace Inference API (free Flux.1-dev) for images. Total cost: $0/video.

To switch back to NVIDIA Build or add another provider, edit LLM_PROVIDER +
the matching section below.
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
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL") or "meta/llama-3.3-70b-instruct"

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
# IMAGE PROVIDER — defaults to HuggingFace Inference API (free)
# ============================================================
IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER") or "huggingface"

# --- HuggingFace Inference API (https://huggingface.co/settings/tokens) ---
HF_API_TOKEN = os.environ.get("HF_API_TOKEN") or ""
HF_MODEL_ID = "black-forest-labs/FLUX.1-dev"
HF_ENDPOINT = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"

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
TTS_VOICE = "en-US-GuyNeural"  # deep male motivation voice
TTS_RATE = "-8%"  # slightly slower for gravitas


# ============================================================
# Video specs
# ============================================================
SCENES_PER_VIDEO = 35        # ~30 sec per scene -> ~17-18 min total
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
