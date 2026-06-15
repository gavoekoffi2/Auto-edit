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
ENGINE_INTERMEDIATE_PRESET = os.getenv("ENGINE_INTERMEDIATE_PRESET", "veryfast")
ENGINE_INTERMEDIATE_CRF = int(os.getenv("ENGINE_INTERMEDIATE_CRF", "19"))
GAP_CUT = float(os.getenv("ENGINE_GAP_CUT", "0.4"))   # silence >= this between two words = a cut (tighter = punchier)
PAD = 0.10              # seconds: SMALL margin around a run — un pad large ré-ajoutait
                        # du silence à chaque coupe (0.18 -> 0.36 s gardés par coupe !)
MICRO_PAD = 0.04        # seconds: tight margin at retake/stutter cuts (word-safe)
MAX_SILENCE_KEPT = 0.18 # jamais garder plus que ça de silence entre deux passages
AUDIO_FADE = 0.03       # seconds: 30 ms afade in/out at every cut

# Smart cut — remove retakes / false starts / repeated sentences.
# A run is dropped when the NEXT run restarts it (the speaker corrected
# himself); the LAST take is always the one kept.
REMOVE_RETAKES = os.getenv("ENGINE_REMOVE_RETAKES", "1") not in {"0", "false", "no"}
RETAKE_SIMILARITY = 0.78        # SequenceMatcher ratio to call two runs "the same"
RETAKE_MAX_WORDS = 24           # only short-ish runs can be false starts
RETAKE_MIN_WORDS = 2            # 1-word runs are handled by the stutter pass
STUTTER_MIN_SPAN = 0.40         # repeated word/bigram shorter than this is left alone
                                # (cutting it would be eaten by the pads anyway)
# Repeated SENTENCES (not necessarily adjacent): when the speaker says nearly
# the same thing again (a botched take re-done later), keep only the LAST one.
# Plus agressif: attrape les quasi-doublons et reformulations proches.
REMOVE_REPEATED_SENTENCES = os.getenv("ENGINE_REMOVE_REPEATS", "1") not in {"0", "false", "no"}
REPEAT_SIMILARITY = 0.78        # how close two runs must be to count as a repeat
REPEAT_MIN_WORDS = 3            # ignore tiny runs (greetings, "ok", ...)
REPEAT_WINDOW = 14              # compare a run to the next N runs (large = catch distant repeats)

# Phrases speakers say when they flub a take — everything from the marker to
# the end of the run is trimmed (".. la méthode est, non je reprends" -> cut).
RETAKE_MARKERS = [
    "je reprends", "on reprend", "je recommence", "on recommence",
    "je répète", "non attends", "attends je reprends", "coupe ça",
    "c'est pas ça", "pardon je reprends", "let me start over", "scratch that",
]

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
#
# RÈGLE PRODUIT: les overlays graphiques (stat / lower-third / liste) ne doivent
# JAMAIS couvrir le visage. Ils sont LÉGERS, OCCASIONNELS et BREFS — ils vivent
# dans le bas du cadre (sous le visage, au-dessus des sous-titres), apparaissent
# quelques secondes puis repartent. Le plein écran "qui illustre" reste réservé
# aux scènes motion_design.
# --------------------------------------------------------------------------- #
ZONE_FACE_MAX_Y = 1000         # y < 1000 : visage — toujours libre
ZONE_OVERLAY_TOP = 1040        # overlays cantonnés au tiers bas
ZONE_OVERLAY_BOTTOM = 1380
ZONE_SUBS_Y = 1500             # sous-titres encore plus bas
ZONE_OVERLAY_SUBS_GAP = 40

OVERLAY_FADE_IN = 0.22         # entrée douce
OVERLAY_FADE_OUT = 0.30        # sortie douce
OVERLAY_MIN_DUR = 2.2          # bref — n'occupe pas l'écran en permanence
OVERLAY_MAX_DUR = 3.2
OVERLAY_PANEL_ALPHA = 165      # panneau plus discret (sur 255)

# Regroupement SÉMANTIQUE du transcript en "sujets" (un beat = une idée). Sépare
# du temps d'AFFICHAGE des overlays (court) : un sujet fait 5-14 s, ce qui donne
# aux scènes motion design un propos cohérent à illustrer.
TOPIC_MIN_DUR = 5.0
TOPIC_MAX_DUR = 14.0
OVERLAY_MAX_PER_VIDEO = int(os.getenv("OVERLAY_MAX_PER_VIDEO", "4"))  # occasionnels
OVERLAY_MIN_GAP = 9.0          # >= 9 s entre deux overlays graphiques

# ProRes 4444 RGBA output (alpha channel preserved)
PRORES_PIX_FMT = "yuva444p10le"
PRORES_PROFILE = "4444"

# --------------------------------------------------------------------------- #
# STEP 6 — B-ROLL IA
# --------------------------------------------------------------------------- #
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_IMAGE_MODEL = "google/gemini-2.5-flash-image"

# Cinematic prompt prefix injected before each B-roll idea. The image MUST
# literally depict what the speaker says at that moment (no off-topic stock).
BROLL_STYLE_PREFIX = (
    "Photoréalisme éditorial cinématographique, lumière naturelle douce, faible "
    "profondeur de champ, cadrage vertical 9:16 plein cadre. L'image doit "
    "montrer EXACTEMENT et LITTÉRALEMENT la scène décrite (objets, action et "
    "personnes réellement mentionnés), jamais une image générique hors-sujet. "
    "Scène à représenter : "
)

# B-roll cadence — COST-AWARE: motion-design scenes (cheap or free) carry a
# larger share of the visual rhythm, so generated images are reserved for the
# strongest beats. Values can be overridden through environment variables.
SECONDS_PER_BROLL = float(os.getenv("SECONDS_PER_BROLL", "7.0"))
SECONDS_PER_BROLL_WITH_MOTION = float(os.getenv("SECONDS_PER_BROLL_WITH_MOTION", "9.0"))
SHORTS_MAX_DURATION_SECONDS = float(os.getenv("SHORTS_MAX_DURATION_SECONDS", "90.0"))
SHORTS_SECONDS_PER_BROLL = float(os.getenv("SHORTS_SECONDS_PER_BROLL", "4.5"))
SHORTS_SECONDS_PER_BROLL_WITH_MOTION = float(os.getenv("SHORTS_SECONDS_PER_BROLL_WITH_MOTION", "5.0"))
MAX_BROLL_IMAGES = int(os.getenv("MAX_BROLL_IMAGES", "18"))   # hard API budget cap (scales with length up to this)

# Precise image prompts: a cheap text model rewrites each spoken excerpt into a
# literal visual scene before image generation (heuristic fallback if it fails).
PROMPT_REFINER_MODEL = os.getenv("PROMPT_REFINER_MODEL", "google/gemini-2.5-flash-lite")
PROMPT_REFINER_ENABLED = os.getenv("PROMPT_REFINER_ENABLED", "1") not in {"0", "false", "no"}

# Entrance animations — VOLONTAIREMENT SOBRES & COHÉRENTES (pas de glissements
# gauche/droite désordonnés). Une entrée se fait par un léger zoom + fondu
# (punch doux) ou une montée verticale ("ça glisse"), jamais en travers.
BROLL_ENTRANCES = [
    "rise", "punch", "rise", "punch",
]

# Exit animations — sortie douce et cohérente (descente verticale ou léger
# zoom), appariée à l'entrée. Plus de départs latéraux qui partent "n'importe
# comment".
BROLL_EXITS = {
    "punch": "scale_out",       # léger zoom + fondu
    "rise": "drop",             # redescend doucement (vertical)
}
BROLL_EXIT_DUR = 0.5            # seconds of exit motion before the cut
BROLL_DURATION = 3.0           # standard clip length
BROLL_DURATION_WIDE = 3.2      # wide images get a touch longer
BROLL_KB = 0.10                # continuous Ken Burns amount over the whole clip
BROLL_BLUR_RADIUS = 40         # GaussianBlur radius for the background plate
BROLL_BLUR_BRIGHTNESS = 0.45   # background plate brightness multiplier
BROLL_BRACKET_COLOR = (0, 220, 255, 255)   # CYAN cinematic corner brackets
BROLL_CHIP_COLOR = (212, 175, 55, 255)     # gold chip
BROLL_CHIP_Y = 250

# --------------------------------------------------------------------------- #
# STEP 6bis — MOTION DESIGN ILLUSTRÉ
# Full-frame animated illustration scenes that DRAW what the speaker is
# explaining (not just text).  Each scene = AI flat-design illustration (or a
# procedural line-art drawing when no API key) + hand-drawn arrows, circled
# keywords, numbered steps, counters — all animated, with entrance/exit
# transitions and per-element SFX cues.
# --------------------------------------------------------------------------- #
MOTION_STYLE_PREFIX = (
    "2D flat vector illustration in premium motion-design style, bold clean "
    "outlines, vibrant saturated colors (cyan, gold, coral accents), simple "
    "geometric shapes, friendly cartoon characters performing the action, "
    "isolated on a very dark navy background, infographic energy, centered "
    "composition, square format, ABSOLUTELY NO text, NO words, NO letters, "
    "NO numbers in the image. Scene to illustrate: "
)

# Densité du motion design — le NOMBRE de scènes grandit avec la durée:
# ~1 scène toutes les 11 s (court) / 16 s (long), rythme dense. Le plafond est
# ÉLEVÉ pour que les vidéos longues reçoivent BEAUCOUP plus de motion design.
MOTION_EVERY_SHORT = float(os.getenv("MOTION_EVERY_SHORT", "11.0"))
MOTION_EVERY_LONG = float(os.getenv("MOTION_EVERY_LONG", "16.0"))
MOTION_MAX_SCENES = int(os.getenv("MOTION_MAX_SCENES", "40"))
MOTION_MIN_SPACING = float(os.getenv("MOTION_MIN_SPACING", "7.0"))  # seconds between two scene starts
MOTION_MIN_START = 2.0          # never take over the very first seconds
# Une scène dure le TEMPS DU PROPOS qu'elle illustre (bornée), pas une durée
# fixe: elle glisse quand la personne commence à parler du point, et repart
# quand elle a fini. Ces bornes évitent les extrêmes.
MOTION_SCENE_DUR = 4.6          # défaut idée / chiffre (si pas de span fourni)
MOTION_SCENE_DUR_STEPS = 5.4    # défaut étapes
MOTION_SCENE_MIN_DUR = 3.2      # une scène ne reste jamais moins de ça
MOTION_SCENE_MAX_DUR = 6.0      # ni plus longtemps (le visage revient vite)
MOTION_LEAD = 0.15              # scene starts slightly before the spoken beat

# Créativité: par défaut, CHAQUE scène reçoit une illustration IA unique (quand
# la clé OpenRouter est là) — c'est ce qui évite "les mêmes dessins à chaque
# vidéo". Les dessins procéduraux ne servent que de repli (pas de clé / échec).
# Baisser cette valeur pour économiser l'API. 0 = jamais d'illustration IA.
MOTION_AI_ILLUSTRATIONS_MAX = int(os.getenv("MOTION_AI_ILLUSTRATIONS_MAX", "12"))

# Transition UNIQUE et COHÉRENTE pour toutes les scènes (demande produit: pas
# de mouvements désordonnés). La scène GLISSE vers le haut en entrant, redescend
# en sortant, avec un fondu — propre et professionnel, jamais en travers.
MOTION_ENTRANCES = ["slide_up"]
MOTION_EXITS = ["slide_down"]

# Palette (deep navy stage + cyan/gold ink, consistent with the brand).
MOTION_BG_TOP = (11, 14, 26)
MOTION_BG_BOTTOM = (26, 19, 46)
MOTION_ACCENT = (0, 220, 255, 255)      # cyan ink (arrows / doodles)
MOTION_GOLD = (255, 199, 64, 255)       # gold ink (highlights / counters)
MOTION_INK = (255, 255, 255, 255)

# CRÉATIVITÉ — palettes alternées d'une VIDÉO à l'autre (seed = hash du
# discours) pour que les scènes procédurales ne se ressemblent jamais. Chaque
# entrée = (bg_top, bg_bottom, accent RGBA, gold/second RGBA).
MOTION_PALETTES = [
    ((11, 14, 26), (26, 19, 46), (0, 220, 255, 255), (255, 199, 64, 255)),    # cyan / gold (signature)
    ((20, 12, 28), (40, 16, 40), (255, 96, 120, 255), (120, 230, 255, 255)),  # coral / ice
    ((10, 22, 24), (12, 40, 38), (60, 240, 180, 255), (255, 210, 90, 255)),   # mint / amber
    ((18, 14, 32), (34, 18, 54), (170, 130, 255, 255), (120, 255, 180, 255)), # violet / lime
    ((24, 16, 12), (44, 24, 14), (255, 170, 60, 255), (90, 220, 255, 255)),   # amber / sky
    ((12, 18, 30), (18, 30, 56), (90, 150, 255, 255), (255, 140, 90, 255)),   # blue / coral
]

# SFX vocabulary for motion scenes (rotating pools, mixed by plan_overlays).
MOTION_RISER_SFX = ["riser", "reverse_swell", "tape_stop"]   # anticipation, -0.45 s
MOTION_ENTRANCE_SFX = ["transition", "whoosh", "cinematic_hit", "swoosh_up"]
MOTION_ELEMENT_SFX = ["pop", "bubble", "snap", "data_tick", "ding", "sparkle"]
MOTION_DRAW_SFX = "pen_scribble"   # plays while a procedural drawing draws itself
MOTION_EXIT_SFX = ["swoosh_down", "whoosh", "tape_stop"]
MOTION_RISER_LEAD = 0.45
MOTION_MAX_ELEMENT_SFX = 4      # cap per scene so SFX stay accents, not noise

# --------------------------------------------------------------------------- #
# STEP 7 — KEYWORD POPUPS — RÈGLE PRO #2
# --------------------------------------------------------------------------- #
KEYWORD_TOP_N = 8
KEYWORD_POPUP_MAX_PER_VIDEO = int(os.getenv("KEYWORD_POPUP_MAX_PER_VIDEO", "8"))
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
    "son", "sa", "ses", "nos", "vos", "notre", "votre", "leur", "leurs",
    "je", "tu", "il",
    "elle", "on", "nous", "vous", "ils", "elles", "se", "me", "te", "lui",
    "y", "en", "pas", "ne", "plus", "moins", "très", "trop", "pour", "par",
    "avec", "sans", "sur", "sous", "dans", "est", "sont", "été", "être",
    "avoir", "fait", "faire", "comme", "aussi", "alors", "bien", "tout",
    "tous", "toute", "toutes", "cela", "ça", "ce", "si", "non", "oui",
    "va", "vais", "vas", "vont", "allez", "veux", "veut", "peux", "peut",
    "dire", "dit", "dis", "parler", "tellement", "probablement", "voir", "vu",
    "passer", "passe", "vient", "venir", "semaine", "derrière", "derriere",
    # contractions courantes (le tokenizer garde l'apostrophe)
    "c'est", "n'est", "s'est", "qu'il", "qu'elle", "qu'on", "j'ai", "t'as",
    "d'un", "d'une", "l'on", "jusqu'à", "aujourd'hui", "quelqu'un",
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
# Respiration entre deux visuels: on laisse le cadre "parlant" revenir un
# moment avant qu'un autre visuel passe (demande produit: "quand l'autre passe,
# ça attend un peu avant que le suivant vienne"). Vaut pour B-roll ET motion.
BROLL_MIN_GAP = 0.8            # respiration entre deux B-roll
VISUAL_MIN_GAP = 0.35         # le B-roll peut suivre une scène motion de près (pas de chevauchement)
GAPFILL_THRESHOLD = 4.0        # gaps > 4 s without a visual get a filler SFX

# Graphic SFX (varied, alternated).
GRAPHIC_SFX = [
    "impact", "sub_drop", "cinematic_hit", "bass_hit",
    "ding", "chime", "sparkle", "boom",
]

# B-roll SFX rotating pool — photo/camera-centric (the user hears a PHOTO being
# taken when an image appears). NEVER the same SFX twice in a row;
# camera_flash is the signature sound and recurs regularly.
BROLL_SFX_POOL = [
    "camera_flash", "shutter_burst", "swoosh_up", "shutter",
    "camera_flash", "camera_focus", "transition", "reverse_swell",
    "camera_flash", "shutter", "whoosh", "shutter_burst",
]

# Keyword popup chips get a tiny UI blip (they used to appear in silence).
POPUP_SFX_POOL = ["pop", "digi_blip", "snap", "bubble"]
POPUP_SFX_MAX = 12              # cap per video

# Gap-fill SFX pool (Règle PRO #3).
GAPFILL_SFX_POOL = ["ding", "transition", "click", "swoosh_up", "chime"]

# Per-cue humanisation: pitch/gain micro-variation cycled across cues so the
# same sample never plays back twice identically (kills the "static" feel).
SFX_PITCH_VARIANTS = [1.0, 0.94, 1.07, 0.97, 1.12, 0.90]
SFX_GAIN_VARIANTS = [1.0, 0.92, 1.06, 0.96, 1.02, 0.9]

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

# The 27 sounds (numpy-generated). Names are the public SFX vocabulary.
SFX_NAMES = [
    "whoosh", "swoosh_up", "swoosh_down", "pop", "boom", "impact", "sub_drop",
    "ding", "sparkle", "shutter", "glitch", "riser", "transition", "click",
    "camera_flash", "chime", "digi_blip", "reverse_swell", "bass_hit",
    # v4.2 professional additions
    "shutter_burst", "camera_focus", "pen_scribble", "tape_stop",
    "bubble", "snap", "cinematic_hit", "data_tick",
]

# Per-SFX peak gain (approximate, from spec).
SFX_GAINS = {
    "impact": 0.95, "sub_drop": 0.92, "bass_hit": 0.90, "cinematic_hit": 0.92,
    "boom": 0.88, "riser": 0.85, "reverse_swell": 0.85, "tape_stop": 0.82,
    "shutter": 0.84, "shutter_burst": 0.85, "swoosh_up": 0.83, "swoosh_down": 0.83,
    "whoosh": 0.82, "camera_flash": 0.82, "camera_focus": 0.66, "transition": 0.80,
    "glitch": 0.78, "pop": 0.75, "ding": 0.72, "snap": 0.74,
    "chime": 0.72, "sparkle": 0.70, "digi_blip": 0.68, "click": 0.60,
    "bubble": 0.70, "pen_scribble": 0.52, "data_tick": 0.62,
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
# FINAL RENDER — qualité visible (master net pour TikTok/Reels)
# --------------------------------------------------------------------------- #
FINAL_CRF = int(os.getenv("FINAL_CRF", "20"))      # 26 -> 20 : nettement plus net
FINAL_PRESET = os.getenv("FINAL_PRESET", "medium")
FINAL_AUDIO_BITRATE = "192k"                        # 128k -> 192k : voix plus propre

# Fonts (Linux system DejaVu fallback + Google Fonts in ~/.fonts).
FONT_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
