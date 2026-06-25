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
MODE_DEFINITIONS: list[dict] = [
    {
        "id": "credit_saver_creator_edit",
        "name": "Montage créateur économique",
        "icon": "⚡",
        "description": (
            "Recommandé MVP : silences coupés, captions, zooms, flashs caméra, "
            "SFX, transitions et motion design — sans dépendre des images IA."
        ),
        "pipeline": "v2",
        "default": True,
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
