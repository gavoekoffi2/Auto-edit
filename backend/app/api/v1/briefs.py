"""Brief-to-ad storyboard preview.

This endpoint deliberately produces a transparent, deterministic storyboard. The
actual media generation remains delegated to the existing Celery/FFmpeg pipeline.
"""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

TemplateId = Literal[
    "direct_response",
    "urgency_proof",
    "saas_explainer",
    "facecam_editorial",
    "facecam_neon",
    "facecam_notes",
]


class BriefPreviewRequest(BaseModel):
    description: str = Field(min_length=20, max_length=6000)
    template_id: TemplateId = "direct_response"
    brand_name: str = Field(default="", max_length=80)
    audience: str = Field(default="", max_length=240)
    offer: str = Field(default="", max_length=500)
    proof: str = Field(default="", max_length=500)
    cta: str = Field(default="Découvre l’offre", max_length=120)
    tone: Literal["expert", "direct", "premium", "chaleureux"] = "direct"
    format: Literal["9:16", "1:1", "16:9"] = "9:16"
    duration_s: int = Field(default=45, ge=20, le=90)


class StoryScene(BaseModel):
    order: int
    role: str
    start_s: float
    end_s: float
    narration: str
    visual_direction: str
    motion: str
    audio: str
    text_overlay: str


class BriefPreviewResponse(BaseModel):
    template_id: TemplateId
    format: str
    duration_s: int
    title: str
    summary: str
    scenes: list[StoryScene]
    render_plan: dict[str, object]
    warnings: list[str]


def _sentences(value: str) -> list[str]:
    return [part.strip(" -\n\t") for part in re.split(r"(?<=[.!?])\s+|\n+", value) if part.strip()]


def _first(value: str, fallback: str) -> str:
    parts = _sentences(value)
    return parts[0] if parts else fallback


def _template_profile(template_id: TemplateId) -> dict[str, str]:
    profiles = {
        "direct_response": {
            "name": "Direct Response",
            "visual": "Split-screen : produit ou mockup ancré à gauche, preuves et bénéfices dynamiques à droite.",
            "motion": "Pop-ins, slides latéraux, push-in léger et empilement de bénéfices.",
            "audio": "Voix persuasive, musique corporate rythmée, pops et whooshes sur les entrées.",
        },
        "urgency_proof": {
            "name": "Urgence & Preuve",
            "visual": "Fond texturé, contraste problème/solution, compte à rebours, captures et badges de preuve.",
            "motion": "Compteur animé, tampon visuel, barre de progression et texte mot par mot.",
            "audio": "Tic-tac au problème, montée musicale à la solution, stamp et whoosh sur les transitions.",
        },
        "saas_explainer": {
            "name": "Démonstration SaaS",
            "visual": "Fenêtres d’interface, écrans de produit et cartes fonctionnelles dans un cadre propre.",
            "motion": "Zooms d’interface, curseurs, highlights, slides et démonstration par étapes.",
            "audio": "Voix pédagogique, musique discrète et clics doux sur les interactions produit.",
        },
        "facecam_editorial": {
            "name": "Face caméra éditorial",
            "visual": "Vidéo parlée plein cadre, captions en pilule, mots-clés éditoriaux et B-roll contextuel.",
            "motion": "Coupes des pauses, push-ins sur les mots forts, transitions douces et overlays papier.",
            "audio": "Voix conservée au premier plan, musique basse et effets discrets synchronisés.",
        },
        "facecam_neon": {
            "name": "Face caméra néon",
            "visual": "Face caméra recadrée verticalement, captions contrastées et accents lumineux sur les mots actifs.",
            "motion": "Jump cuts rapides, zooms rythmiques, glitch léger et mots-clés en grand format.",
            "audio": "Musique énergique, whooshes et impacts courts sur les changements de rythme.",
        },
        "facecam_notes": {
            "name": "Face caméra notes",
            "visual": "Cadre chaleureux, captions manuscrites, annotations et illustrations façon carnet.",
            "motion": "Cercles dessinés, flèches, surlignages, transitions de page et apparitions progressives.",
            "audio": "Voix intime, texture musicale légère, page-flip et petits sons analogiques.",
        },
    }
    return profiles[template_id]


def build_storyboard(data: BriefPreviewRequest) -> BriefPreviewResponse:
    profile = _template_profile(data.template_id)
    subject = data.brand_name or "ton entreprise"
    audience = data.audience or "ton audience cible"
    offer = data.offer or _first(data.description, "une offre utile")
    proof = data.proof or "preuve, résultat ou démonstration à fournir"
    hook = _first(data.description, f"Une solution pour {audience}")
    body = _sentences(data.description)[1:]
    benefit_1 = body[0] if body else offer
    benefit_2 = body[1] if len(body) > 1 else "Une méthode claire, simple et immédiatement utile."
    slots = [0.14, 0.18, 0.22, 0.18, 0.14, 0.14]
    roles = ["hook", "problem", "promise", "proof", "offer", "cta"]
    narrations = [
        hook,
        f"Si tu es {audience}, {benefit_1}",
        f"Avec {subject}, {benefit_2}",
        proof,
        f"Voici ce que tu peux obtenir : {offer}",
        data.cta,
    ]
    overlays = [
        hook[:72],
        "Le problème que ton audience rencontre",
        "Une solution simple et concrète",
        "La preuve à montrer",
        offer[:72],
        data.cta,
    ]
    scenes: list[StoryScene] = []
    cursor = 0.0
    for index, (role, share) in enumerate(zip(roles, slots), start=1):
        end = data.duration_s if index == len(roles) else round(cursor + data.duration_s * share, 2)
        scenes.append(StoryScene(
            order=index,
            role=role,
            start_s=round(cursor, 2),
            end_s=round(end, 2),
            narration=narrations[index - 1],
            visual_direction=profile["visual"],
            motion=profile["motion"],
            audio=profile["audio"],
            text_overlay=overlays[index - 1],
        ))
        cursor = end
    return BriefPreviewResponse(
        template_id=data.template_id,
        format=data.format,
        duration_s=data.duration_s,
        title=f"{profile['name']} — {subject}",
        summary=f"Storyboard {profile['name']} pour {audience}, au format {data.format}, avec une narration {data.tone}.",
        scenes=scenes,
        render_plan={
            "template": profile["name"],
            "aspect_ratio": data.format,
            "captions": data.template_id.startswith("facecam") or data.format == "9:16",
            "remove_silence": data.template_id.startswith("facecam"),
            "ai_broll": True,
            "motion_design": True,
            "music": True,
            "sfx": True,
            "cta": data.cta,
        },
        warnings=["La preuve sociale, les captures et les assets de marque doivent être fournis ou validés avant le rendu final."]
        if not data.proof
        else [],
    )


@router.post("/preview", response_model=BriefPreviewResponse)
async def preview_brief(data: BriefPreviewRequest) -> BriefPreviewResponse:
    return build_storyboard(data)
