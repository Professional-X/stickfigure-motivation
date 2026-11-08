"""Central config — change models, voice, themes here.

Models: browse https://build.nvidia.com/models and copy the model ID.
The LLM_MODEL is swappable per-run by setting the LLM_MODEL env var
(or repo variable in GitHub Actions).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === LLM (NVIDIA Build — OpenAI-compatible) ===
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

# Pick any model from https://build.nvidia.com/models
# Examples:
#   meta/llama-3.3-70b-instruct        (best for motivational writing)
#   mistralai/mistral-large-2-instruct (slightly more poetic)
#   qwen/qwen2.5-72b-instruct          (best for structured JSON)
LLM_MODEL = os.environ.get("LLM_MODEL", "meta/llama-3.3-70b-instruct")

# === Image gen (Flux.1 dev on NVIDIA Build) ===
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "black-forest-labs/flux.1-dev")
IMAGE_ENDPOINT = "https://ai.api.nvidia.org/v1/genai/black-forest-labs/flux.1-dev"
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
IMAGE_SEED = 42  # fixed base seed for visual consistency across scenes

# === TTS (Edge-TTS — free, no API key needed) ===
TTS_VOICE = "en-US-GuyNeural"  # deep male motivation voice
TTS_RATE = "-8%"  # slightly slower for gravitas

# === Video specs ===
SCENES_PER_VIDEO = 35        # ~30 sec per scene -> ~17-18 min total
KEN_BURNS_ZOOM = 1.15        # 15% zoom-in over each scene
KEN_BURNS_ZOOM_STEP = 0.0005 # zoompan increment per frame

# === Audio mix ===
BG_MUSIC_VOLUME_DB = -22     # background music level (negative = quieter)
NARRATION_VOLUME_DB = 0      # narration at full

# === Paths ===
OUTPUT_DIR = os.environ.get("VIDEO_OUTPUT_DIR", "./output")
MUSIC_DIR = "./music"

# === Composio (YouTube upload) ===
COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY", "")
COMPOSIO_ENTITY_ID = os.environ.get("COMPOSIO_ENTITY_ID", "")

# === YouTube defaults ===
YOUTUBE_TAGS = [
    "motivation", "discipline", "stoicism", "mindset", "self improvement",
    "stick figure", "philosophy", "men", "focus", "hard work",
]
YOUTUBE_CATEGORY_ID = "22"  # People & Blogs
YOUTUBE_PRIVACY = "public"  # public | unlisted | private
