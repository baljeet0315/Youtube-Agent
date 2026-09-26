"""
config.py — Central configuration loader for YouTube Agent
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
# eleven_turbo_v2 is English-only. multilingual_v2 covers ~30 languages;
# eleven_v3 covers 70+ (incl. Punjabi) but is newer — try it if v2 sounds off.
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")

# ── Video Settings ────────────────────────────────────────
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", 720))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", 1280))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", 30))
TAIL_SECONDS = float(os.getenv("TAIL_SECONDS", 2.0))   # hold + fade after voice ends
MAX_VIDEO_DURATION = int(os.getenv("MAX_VIDEO_DURATION", 60))

# ── Phase 2: visuals / captions / music ───────────────────
# visual_mode default for new jobs: "ai_images" | "stock"
DEFAULT_VISUAL_MODE = os.getenv("DEFAULT_VISUAL_MODE", "ai_images")
FAL_KEY = os.getenv("FAL_KEY", "")
FAL_IMAGE_MODEL = os.getenv("FAL_IMAGE_MODEL", "fal-ai/flux/schnell")
# Generate a little larger than the frame so pan/zoom never shows edges (multiples of 32)
IMAGE_GEN_WIDTH = int(os.getenv("IMAGE_GEN_WIDTH", 832))
IMAGE_GEN_HEIGHT = int(os.getenv("IMAGE_GEN_HEIGHT", 1472))

CAPTIONS_ENABLED = os.getenv("CAPTIONS_ENABLED", "true").lower() in ("1", "true", "yes")
CAPTION_FONT = os.getenv("CAPTION_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
CAPTION_FONT_SIZE = int(os.getenv("CAPTION_FONT_SIZE", 64))
CAPTION_Y_RATIO = float(os.getenv("CAPTION_Y_RATIO", 0.62))   # vertical centre of caption band
CAPTION_HIGHLIGHT = os.getenv("CAPTION_HIGHLIGHT", "#FFD400")

MUSIC_ENABLED = os.getenv("MUSIC_ENABLED", "true").lower() in ("1", "true", "yes")
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", 0.12))
MUSIC_DIR = os.getenv("MUSIC_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "music"))
# Optional R2 source: music/<mood>/*.mp3 in the same bucket the backend uses
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")

# ── Paths ─────────────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "audio"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "footage"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "videos"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "music"), exist_ok=True)

# ── Validation ────────────────────────────────────────────
def validate_config():
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not ELEVENLABS_API_KEY:
        missing.append("ELEVENLABS_API_KEY")
    if not PEXELS_API_KEY:
        missing.append("PEXELS_API_KEY")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.template to .env and fill in your API keys."
        )
