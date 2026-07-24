"""Catalogue des modes de montage (présentation API).

Module SANS dépendance base de données / réseau, pour qu'il soit importable et
testable en isolation. `jobs.py` le ré-exporte; le frontend consomme la liste
via `GET /jobs/modes`.
"""
from __future__ import annotations

# Le PREMIER mode est le défaut produit. `default: True` est explicite pour que
# le frontend n'ait pas à deviner. Chaque mode v2 porte une `visual_mode`:
#   credit_saver  -> jamais d'image IA payante (MVP rapide, non bloquant)
#   ai_broll      -> images IA / B-roll quand possible (ancien comportement)
#   auto_fallback -> tente l'IA, retombe en économique si crédits finis/échec
#
# DÉCISION PRODUIT: le défaut est le style SIGNATURE (images IA 3D + motion
# design varié + sous-titres karaoké lisibles). Jamais le mode économique sans
# images ni le style manuscrit — ils restent sélectionnables plus bas.
MODE_DEFINITIONS: list[dict] = [
    {
        "id": "signature_3d",
        "name": "Signature 3D (recommandé)",
        "icon": "✨",
        "description": (
            "Le montage vedette : illustrations 3D uniques par vidéo, scènes "
            "motion design qui changent de composition (cercle, polaroid, "
            "arche, plein cadre…), B-roll IA, sous-titres karaoké jaunes, "
            "SFX et transitions lumineuses."
        ),
        "pipeline": "v2",
        "default": True,
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "tiktok_yellow",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    # --- Nouveaux styles viraux -----------------------------------------------
    {
        "id": "beast_impact",
        "name": "Impact viral",
        "icon": "🔥",
        "description": (
            "Sous-titres MAJUSCULES massifs, mot actif rouge avec glow, "
            "mots-clés glitch géants — le style rétention maximale des plus "
            "gros créateurs."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "beast_impact",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    {
        "id": "mint_wave",
        "name": "Menthe fraîche",
        "icon": "🌿",
        "description": (
            "Pilule sombre arrondie, karaoké progressif (mot actif menthe, "
            "mots à venir estompés) — doux, premium et ultra lisible."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "mint_wave",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    {
        "id": "board_pitch",
        "name": "Board de présentation",
        "icon": "🟩",
        "description": (
            "Panneau vert sapin texturé, titres serif éditoriaux et pile de "
            "flyers fixes ; une grande carte 9:16 rejoue chaque idée (image "
            "plein cadre, citation typographique, chiffre géant) et les "
            "éléments glissent d'une carte à l'autre — le look des vidéos "
            "publicitaires en motion design."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "board_serif",
            "motion_preset": "board_pitch",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    {
        "id": "bangers_comic",
        "name": "Comic pop",
        "icon": "💥",
        "description": (
            "Sous-titres cartoon Bangers, mot actif cyan, énergie BD — fun et "
            "punchy pour le divertissement."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "bangers_fun",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    # --- Styles Captions AI (réfs TikTok analysées image par image) ----------
    {
        "id": "pill_editorial",
        "name": "Pilule éditoriale",
        "icon": "🏷️",
        "description": (
            "Sous-titres en pilule blanche (mots prononcés en noir, à venir en "
            "gris), bandeaux mots-clés « papier déchiré » bleu + barre noire — "
            "le look éditorial des montages Captions AI."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "pill_editorial",
            "motion_preset": "editorial_paper",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    {
        "id": "neon_hype",
        "name": "Néon hype",
        "icon": "⚡",
        "description": (
            "Sous-titres MAJUSCULES condensés, mot actif cyan avec glow, "
            "mots-clés géants avec glitch chromatique — le style énergique "
            "des montages viraux."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "neon_hype",
            "motion_preset": "neon_social",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    {
        "id": "handwritten_note",
        "name": "Notes manuscrites",
        "icon": "✍️",
        "description": (
            "Sous-titres écriture manuscrite blanche, mots-clés entourés d'un "
            "cercle dessiné à la main, scènes carnet crème + encre pinceau — "
            "le style sketch chaleureux."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "subtitle_template": "handwritten_note",
            "motion_preset": "sketch_notes",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    # --- Mode économique (plus le défaut: pas d'images IA, rendu plus simple) --
    {
        "id": "credit_saver_creator_edit",
        "name": "Économique (sans images IA)",
        "icon": "⚡",
        "description": (
            "Économise les crédits : silences coupés, captions, zooms, SFX, "
            "transitions et motion design procédural — aucune image IA payante."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": False,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "credit_saver",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    {
        "id": "business_premium_african",
        "name": "Images IA + motion design",
        "icon": "🖼️",
        "description": (
            "Ancien montage premium : B-roll/images IA générées quand des "
            "crédits sont disponibles, + motion design et musique sobre."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "ai_broll",
            "broll_style": "african_business_premium", "broll_demographic": "african",
        },
    },
    {
        "id": "tiktok_viral",
        "name": "Automatique (images si dispo, sinon économique)",
        "icon": "🔁",
        "description": (
            "Hybride : tente les images IA, mais continue en mode économique "
            "(flashs, SFX, motion) si les crédits sont finis — jamais bloqué."
        ),
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "broll_style": "tiktok_viral", "broll_demographic": "african",
        },
    },
    {
        "id": "publicite_locale",
        "name": "Publicité locale",
        "icon": "📣",
        "description": "Restaurant, boutique, service local — CTA clair",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "visual_mode": "auto_fallback",
            "broll_style": "publicite_locale", "broll_demographic": "african",
        },
    },
    {
        "id": "podcast_propre",
        "name": "Podcast propre",
        "icon": "🎙️",
        "description": "Suppression silences uniquement, audio préservé",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": False, "ai_broll": False,
            "motion_design": False,
            "music": False, "sfx": False, "vertical_9_16": False, "final_cta": False,
            "visual_mode": "credit_saver",
            "broll_style": "podcast_propre", "broll_demographic": "african",
        },
    },
    {
        "id": "formation_educative",
        "name": "Formation / éducatif",
        "icon": "🎓",
        "description": "Captions lisibles, B-roll discret, horizontal",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "motion_design": True,
            "music": False, "sfx": False, "vertical_9_16": False, "final_cta": False,
            "visual_mode": "auto_fallback",
            "broll_style": "formation_educative", "broll_demographic": "african",
        },
    },
    {
        "id": "tiktok",
        "name": "TikTok (legacy)",
        "icon": "📱",
        "description": "Pipeline v1 — vertical 9:16, sous-titres, cuts rapides",
        "pipeline": "v1",
        "defaults": {},
    },
    {
        "id": "youtube",
        "name": "YouTube (legacy)",
        "icon": "📹",
        "description": "Pipeline v1 — suppression silences + sous-titres",
        "pipeline": "v1",
        "defaults": {},
    },
    {
        "id": "podcast",
        "name": "Podcast (legacy)",
        "icon": "🎧",
        "description": "Pipeline v1 — audio uniquement",
        "pipeline": "v1",
        "defaults": {},
    },
]


DEFAULT_MODE: str = next(
    (m["id"] for m in MODE_DEFINITIONS if m.get("default")),
    MODE_DEFINITIONS[0]["id"],
)
