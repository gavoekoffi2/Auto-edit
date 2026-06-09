"""
Auto Edit — central configuration.

Every magic number from the "MOTEUR AUTO EDIT — SPEC v4" lives here so the
pipeline stays a single source of truth.  Modules import from this file rather
than re-declaring constants, which keeps the viral-montage recipe reproducible.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# FORMAT
# --------------------------------------------------------------------------- #
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Cover-crop any source to the mandated vertical 1080x1920 (no distortion).
VERTICAL_COVER = (
    "scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920"
)

# --------------------------------------------------------------------------- #
# STEP 1 — TRANSCRIPTION (ElevenLabs Scribe)
# --------------------------------------------------------------------------- #
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
SCRIBE_MODEL_ID = "scribe_v1"

# --------------------------------------------------------------------------- #
# STEP 2 — EDL (cut rules) — RÈGLE PRO #1 RYTHME
# --------------------------------------------------------------------------- #
GAP_CUT = 0.65          # seconds: any silence >= this between two words = a cut
PAD = 0.25              # seconds: kept margin before/after each retained segment
AUDIO_FADE = 0.03       # seconds: 30 ms afade in/out at every cut

# Segments containing ONLY these tokens are dropped (filler words FR/EN).
FILLERS = {
    "euh", "hm", "hmm", "ah", "eh", "bon", "bah", "ben", "hein", "voilà",
    "donc", "alors", "en fait", "genre", "quoi", "ouais", "ok",
}

# --------------------------------------------------------------------------- #
# STEP 3 — COLOR GRADE (warm_cinematic, applied per segment at encode time)
# --------------------------------------------------------------------------- #
GRADE_WARM_CINEMATIC = (
    "eq=contrast=1.12:brightness=-0.02:saturation=0.88,"
    "colorbalance=rs=0.02:gs=0.0:bs=-0.03:rm=0.04:gm=0.01:bm=-0.02:"
    "rh=0.08:gh=0.02:bh=-0.05,"
    "curves=master='0/0 0.25/0.22 0.75/0.78 1/1'"
)

# --------------------------------------------------------------------------- #
# STEP 4 — ZOOM DYNAMIQUE (Ken Burns + micro-punches) — RÈGLE PRO #3
# --------------------------------------------------------------------------- #
KB_ZOOM_MIN = 1.0
KB_ZOOM_MAX = 1.16
PUNCH_EVERY = 3.2       # seconds between gaussian micro-punches inside a segment
PUNCH_AMP = 0.08
PUNCH_SIGMA = 0.30 / 2.5  # = 0.12

# --------------------------------------------------------------------------- #
# STEP 5 — OVERLAYS (anti-collision safe zones, in px)
# --------------------------------------------------------------------------- #
ZONE_FACE_MAX_Y = 800          # y < 800 : keep free (face)
ZONE_OVERLAY_TOP = 800         # graphic overlays live higher, clear of captions
ZONE_OVERLAY_BOTTOM = 1340
ZONE_SUBS_Y = 1425             # TikTok-safe: higher than bottom UI, below overlays
ZONE_OVERLAY_SUBS_GAP = 50     # >= 50 px between overlay bottom and subtitles

OVERLAY_FADE_IN = 0.13         # seconds
OVERLAY_FADE_OUT = 0.20        # seconds
OVERLAY_MIN_DUR = 5.0          # an overlay lasts as long as the topic (5-17 s)
OVERLAY_MAX_DUR = 17.0

# ProRes 4444 RGBA output (alpha channel preserved)
PRORES_PIX_FMT = "yuva444p10le"
PRORES_PROFILE = "4444"

# --------------------------------------------------------------------------- #
# STEP 6 — B-ROLL IA
# --------------------------------------------------------------------------- #
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_IMAGE_MODEL = "google/gemini-2.5-flash-image"

# Cinematic prompt prefix injected before each B-roll idea.
BROLL_STYLE_PREFIX = (
    "Cinematic editorial photograph, dramatic rim lighting, shallow depth of "
    "field, rich teal-and-orange color grade, high detail, 35mm film look, "
    "vertical composition. Subject: "
)

# B-roll cadence. Shorts need a denser visual rhythm; longer videos stay more
# cost-aware because motion-design cards also illustrate key beats. Values can
# be overridden in production through environment variables without code edits.
SECONDS_PER_BROLL = float(os.getenv("SECONDS_PER_BROLL", "5.0"))
SECONDS_PER_BROLL_WITH_MOTION = float(os.getenv("SECONDS_PER_BROLL_WITH_MOTION", "7.0"))
SHORTS_MAX_DURATION_SECONDS = float(os.getenv("SHORTS_MAX_DURATION_SECONDS", "90.0"))
SHORTS_SECONDS_PER_BROLL = float(os.getenv("SHORTS_SECONDS_PER_BROLL", "3.5"))
SHORTS_SECONDS_PER_BROLL_WITH_MOTION = float(os.getenv("SHORTS_SECONDS_PER_BROLL_WITH_MOTION", "4.0"))

# Entrance animations cycled in this exact order (Étape 6).
BROLL_ENTRANCES = [
    "punch", "slide_r", "slide_l", "rise",
    "glitch", "flash", "transition", "swoosh_up",
]
BROLL_DURATION = 3.0           # standard clip length
BROLL_DURATION_WIDE = 3.2      # wide images get a touch longer
BROLL_KB = 0.10                # continuous Ken Burns amount over the whole clip
BROLL_BLUR_RADIUS = 40         # GaussianBlur radius for the background plate
BROLL_BLUR_BRIGHTNESS = 0.45   # background plate brightness multiplier
BROLL_BRACKET_COLOR = (0, 220, 255, 255)   # CYAN cinematic corner brackets
BROLL_CHIP_COLOR = (212, 175, 55, 255)     # gold chip
BROLL_CHIP_Y = 250

# --------------------------------------------------------------------------- #
# STEP 7 — KEYWORD POPUPS — RÈGLE PRO #2
# --------------------------------------------------------------------------- #
KEYWORD_TOP_N = 8
KEYWORD_MIN_GAP = 8.0          # seconds between two occurrences of the same word
KEYWORD_POPUP_DUR = 1.5
KEYWORD_POPUP_Y = 380          # above the face, TikTok style
KEYWORD_CHIP_COLOR = (212, 175, 55, 255)   # gold

# Stopwords filtered before counting keyword frequency (FR + EN).
STOPWORDS = {
    # French
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "mais",
    "donc", "or", "ni", "car", "que", "qui", "quoi", "dont", "où", "à", "au",
    "aux", "ce", "cet", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "notre", "votre", "leur", "leurs", "je", "tu", "il",
    "elle", "on", "nous", "vous", "ils", "elles", "se", "me", "te", "lui",
    "y", "en", "pas", "ne", "plus", "moins", "très", "trop", "pour", "par",
    "avec", "sans", "sur", "sous", "dans", "est", "sont", "été", "être",
    "avoir", "fait", "faire", "comme", "aussi", "alors", "bien", "tout",
    "tous", "toute", "toutes", "cela", "ça", "ce", "si", "non", "oui",
    # English
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "without", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "i", "you", "he", "she",
    "we", "they", "my", "your", "his", "her", "our", "their", "as", "so",
    "not", "no", "yes", "do", "does", "did", "have", "has", "had", "will",
    "would", "can", "could", "just", "very", "more", "than", "then", "there",
}

# --------------------------------------------------------------------------- #
# STEP 8 — PLAN TIMELINE & SFX cues
# --------------------------------------------------------------------------- #
GRAPHIC_LEAD = 0.2             # graphics placed -0.2 s before the topic starts
BROLL_MIN_GAP = 0.4            # >= 0.4 s gap between two B-roll clips
GAPFILL_THRESHOLD = 4.0        # gaps > 4 s without a visual get a filler SFX

# Graphic SFX (varied, alternated).
GRAPHIC_SFX = [
    "impact", "sub_drop", "boom", "bass_hit",
    "ding", "chime", "sparkle", "pop",
]

# B-roll SFX rotating pool — NEVER the same SFX twice in a row.
# camera_flash is the signature photo sound and recurs regularly.
BROLL_SFX_POOL = [
    "camera_flash", "swoosh_up", "shutter", "glitch",
    "camera_flash", "transition", "reverse_swell", "swoosh_down",
    "camera_flash", "digi_blip", "whoosh", "sparkle",
]

# Gap-fill SFX pool (Règle PRO #3).
GAPFILL_SFX_POOL = ["ding", "transition", "click", "swoosh_up", "chime"]

# --------------------------------------------------------------------------- #
# STEP 9 — COMPOSITE
# --------------------------------------------------------------------------- #
COMPOSITE_BATCH = 12           # max overlays per ffmpeg pass (OOM guard)

# --------------------------------------------------------------------------- #
# STEP 10 — SFX LIBRARY + MIX
# --------------------------------------------------------------------------- #
SFX_SAMPLE_RATE = 48000        # 48 kHz mono WAV
SFX_OFFSET = -0.060            # -60 ms : anticipate the attack
SFX_BUS_GAIN = 0.55           # SFX sit as accents under the voice

# The 19 sounds (numpy-generated). Names are the public SFX vocabulary.
SFX_NAMES = [
    "whoosh", "swoosh_up", "swoosh_down", "pop", "boom", "impact", "sub_drop",
    "ding", "sparkle", "shutter", "glitch", "riser", "transition", "click",
    "camera_flash", "chime", "digi_blip", "reverse_swell", "bass_hit",
]

# Per-SFX peak gain (approximate, from spec).
SFX_GAINS = {
    "impact": 0.95, "sub_drop": 0.92, "bass_hit": 0.90,
    "boom": 0.88, "riser": 0.85, "reverse_swell": 0.85,
    "shutter": 0.84, "swoosh_up": 0.83, "swoosh_down": 0.83,
    "whoosh": 0.82, "camera_flash": 0.82, "transition": 0.80,
    "glitch": 0.78, "pop": 0.75, "ding": 0.72,
    "chime": 0.72, "sparkle": 0.70, "digi_blip": 0.68, "click": 0.60,
}

# loudnorm target (broadcast-safe social loudness).
LOUDNORM = "loudnorm=I=-14:TP=-1:LRA=11"

# --------------------------------------------------------------------------- #
# STEP 11 — SUBTITLES (ASS / libass)
# --------------------------------------------------------------------------- #
SUBS_CHUNK_MIN = 2             # 2-3 words per chunk
SUBS_CHUNK_MAX = 3
SUBS_HL_SCALE = 145            # active-word zoom % (OBLIGATOIRE — was 115-125)
SUBS_POPIN_FROM = 40           # chunk pop-in scale start (%) -> 100

# 5 selectable subtitle templates.
ASS_TEMPLATES = {
    "tiktok_yellow": {
        "font": "Montserrat", "size": 86,
        "primary": "&H00FFFFFF", "highlight": "&H0000F0FF",  # white / yellow
        "outline": "&H00000000", "outline_w": 6, "shadow": 2,
        "hl_scale": SUBS_HL_SCALE, "bold": -1,
    },
    "neon_pop": {
        "font": "Anton", "size": 92,
        "primary": "&H00FFFFFF", "highlight": "&H00B469FF",   # white / neon pink
        "outline": "&H00400020", "outline_w": 5, "shadow": 2,
        "hl_scale": SUBS_HL_SCALE, "bold": 0,
    },
    "bold_box": {
        "font": "Montserrat", "size": 80,
        "primary": "&H00FFFFFF", "highlight": "&H0000F0FF",
        "outline": "&H00000000", "outline_w": 4, "shadow": 0,
        "hl_scale": SUBS_HL_SCALE, "bold": -1, "box": True,
    },
    "gold_lux": {
        "font": "Bebas Neue", "size": 96,
        "primary": "&H00FFFFFF", "highlight": "&H0037B8D4",   # white / gold
        "outline": "&H00101010", "outline_w": 5, "shadow": 2,
        "hl_scale": SUBS_HL_SCALE, "bold": 0,
    },
    "bangers_fun": {
        "font": "Bangers", "size": 94,
        "primary": "&H00FFFFFF", "highlight": "&H00FFFF00",   # white / cyan
        "outline": "&H00000000", "outline_w": 5, "shadow": 2,
        "hl_scale": SUBS_HL_SCALE, "bold": 0,
    },
}
DEFAULT_TEMPLATE = "tiktok_yellow"

# --------------------------------------------------------------------------- #
# FINAL RENDER
# --------------------------------------------------------------------------- #
FINAL_CRF = 26
FINAL_PRESET = "slow"
FINAL_AUDIO_BITRATE = "128k"

# Fonts (Linux system DejaVu fallback + Google Fonts in ~/.fonts).
FONT_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
