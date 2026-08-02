"""ÉTAPE 3 — `CollagePromptBuilder`: concept → prompts image & vidéo verrouillés.

Le style N'EST PAS négociable. Il est déclaré une fois ici, versionné
(`STYLE_LOCK_VERSION`) et injecté à l'identique dans chaque prompt:

  * collage éditorial premium ;
  * texture papier (grain de papier non couché) ;
  * photos noir & blanc tramées (halftone) ;
  * papier coloré en aplats ;
  * contours crème ;
  * ombres portées légères ;
  * AUCUNE typographie, AUCUN logo, AUCUN watermark.

C'est ce verrou qui donne à toutes les vidéos CutForge la même identité
visuelle, quel que soit le fournisseur d'images derrière.

Le prompt image porte aussi le LAYOUT choisi par le planner: le modèle est
explicitement prié de poser chaque objet dans une zone précise du cadre. Le
`CollageVideoService` réutilise ces mêmes zones pour révéler l'image pièce par
pièce — le prompt et l'animation partagent donc une seule source de vérité.
"""
from __future__ import annotations

from typing import Optional

from . import collage_config as ccfg
from .collage_types import (
    ANCHOR_LABELS,
    CollageConcept,
    CollagePrompts,
    Emotion,
    layout_for,
)

# --------------------------------------------------------------------------- #
# LE VERROU DE STYLE (ne pas modifier sans incrémenter STYLE_LOCK_VERSION)
# --------------------------------------------------------------------------- #
STYLE_LOCK = (
    "Premium editorial stop-motion paper collage. Black-and-white halftone "
    "photographic cut-outs mixed with flat saturated coloured cardstock shapes. "
    "Every element is a physically cut piece of paper with crisp scissor edges "
    "and a thin cream keyline, resting on a flat bold colour field. Visible "
    "uncoated paper grain over the whole frame, soft short drop shadows so the "
    "pieces feel lifted a few millimetres off the background. Hand-made "
    "editorial poster craft, generous negative space, confident composition."
)

#: Contraintes négatives — répétées en positif ET en négatif, car beaucoup de
#: modèles image ignorent le champ `negative_prompt`.
STYLE_BANS = (
    "Absolutely NO typography, NO text, NO letters, NO words, NO numbers, "
    "NO captions, NO labels, NO signature, NO logo, NO watermark, NO UI, "
    "NO speech bubbles with writing, NO fake or garbled characters. "
    "No photorealistic 3D render, no glossy CGI, no gradient mesh, no drop-in "
    "stock photography, no busy background clutter."
)

NEGATIVE_PROMPT = (
    "text, typography, lettering, letters, words, numbers, captions, subtitles, "
    "watermark, logo, signature, brand mark, UI elements, garbled characters, "
    "fake glyphs, gradients, 3d render, glossy cgi, photorealistic background, "
    "cluttered composition, blurry, low contrast, overlapping unreadable shapes"
)

#: Le rythme et la lumière suivent l'émotion — la palette, elle, vient du
#: concept. Deux leviers seulement: on garde l'identité serrée.
_EMOTION_DIRECTION: dict[Emotion, str] = {
    Emotion.URGENCY: "high contrast, tilted dynamic angles, pieces caught mid-fall",
    Emotion.WARNING: "heavy dark field, one alarming accent colour, torn paper edges",
    Emotion.HOPE: "airy composition, rising diagonal, light cream negative space",
    Emotion.PRIDE: "centred heroic composition, one element lifted above the others",
    Emotion.CURIOSITY: "off-centre composition, one element partially revealed",
    Emotion.TRUST: "calm symmetrical balance, clean horizontal alignment",
    Emotion.FRUSTRATION: "compressed composition, one element blocked by another",
    Emotion.NEUTRAL: "balanced editorial composition, calm spacing",
}


class CollagePromptBuilder:
    """Concept → (`image_prompt`, `video_prompt`, `negative_prompt`)."""

    def __init__(self, aspect_ratio: Optional[str] = None):
        self.aspect_ratio = aspect_ratio or ccfg.ASPECT_RATIO

    # ------------------------------------------------------------------ #
    def build(self, concept: CollageConcept,
              quality_hints: Optional[list[str]] = None) -> CollagePrompts:
        """Construit les deux prompts.

        *quality_hints* est utilisé par le retry du contrôle qualité: les
        défauts détectés (texte résiduel, éléments collés…) sont renvoyés au
        modèle en consignes explicites plutôt que de retenter à l'identique.
        """
        return CollagePrompts(
            image_prompt=self.build_image_prompt(concept, quality_hints),
            video_prompt=self.build_video_prompt(concept),
            negative_prompt=NEGATIVE_PROMPT,
            style_lock_version=ccfg.STYLE_LOCK_VERSION,
            aspect_ratio=self.aspect_ratio,
        )

    # ------------------------------------------------------------------ #
    def build_image_prompt(self, concept: CollageConcept,
                           quality_hints: Optional[list[str]] = None) -> str:
        objects = concept.ordered_objects()
        cells = concept.layout()
        placement = "; ".join(
            f"{obj.name} {ANCHOR_LABELS.get(cells[i][0], 'in the frame')} "
            f"on {obj.paper_color} paper"
            for i, obj in enumerate(objects[: len(cells)])
        )
        direction = _EMOTION_DIRECTION.get(concept.emotion, _EMOTION_DIRECTION[Emotion.NEUTRAL])
        parts = [
            STYLE_LOCK,
            f"Flat background colour field: {concept.background_color}.",
            f"Visual metaphor to build: {concept.metaphor}.",
            f"Exactly {len(objects)} paper elements, clearly separated, "
            f"never overlapping more than a third of each other: {placement}.",
            f"Emotional direction: {concept.emotion.value} — {direction}.",
            f"Vertical {self.aspect_ratio} full-frame composition.",
        ]
        # ANCRAGE LITTÉRAL. Le style pousse à l'abstraction: sans cette ligne,
        # un modèle d'image illustre volontiers « la liberté » quand la personne
        # parle de sa voiture. Ce qui est NOMMÉ doit être reconnaissable.
        subject = _literal_subject(concept)
        if subject:
            parts.append(
                f"The subject actually being talked about is: {subject}. "
                f"It must be immediately recognisable as {subject}, "
                "cut from paper — never replaced by an unrelated object.")
        parts.append(STYLE_BANS)
        if quality_hints:
            parts.append("Corrections required on this retry: "
                         + "; ".join(quality_hints[:4]) + ".")
        return " ".join(p.strip() for p in parts if p).strip()

    # ------------------------------------------------------------------ #
    def build_video_prompt(self, concept: CollageConcept) -> str:
        """Prompt image→vidéo: assemblage depuis un fond VIDE, sans caméra.

        Formulé pour un modèle vidéo, mais il sert aussi de spécification
        lisible du rendu local (`collage_video_service`): la même phrase décrit
        ce que produit le compositeur déterministe.
        """
        steps = []
        for obj in concept.ordered_objects():
            steps.append(f"{obj.order}. the {obj.name} is placed "
                         f"({_ENTRANCE_WORDS.get(obj.entrance, 'dropped in')})")
        return " ".join([
            f"Stop-motion paper collage assembly on a flat {concept.background_color} "
            "colour field.",
            "The clip STARTS on a completely empty background — no element visible.",
            "Then the paper pieces are laid down one by one, in this exact order: "
            + "; ".join(steps) + ".",
            "Each placement snaps into position in a few stop-motion steps, with a "
            "short soft paper shadow settling under it.",
            "No camera movement, no zoom, no pan, no morphing, no dissolve between "
            "shapes: pieces are physically placed, never faded in.",
            f"The final frame must match the reference still exactly and read as: "
            f"{concept.metaphor}.",
            STYLE_BANS,
        ]).strip()


def _literal_subject(concept: CollageConcept) -> str:
    """Les choses CONCRÈTES nommées dans l'extrait, telles quelles.

    Se lit dans l'extrait source plutôt que dans les objets du concept: c'est
    la parole qui fait foi. Renvoie une chaîne vide quand la phrase ne nomme
    rien de matériel — dans ce cas la métaphore reste seule aux commandes, ce
    qui est exactement le rôle du moteur éditorial.
    """
    from . import collage_lexicon

    entities = collage_lexicon.ground(concept.excerpt, limit=2)
    return " and ".join(entity.noun for entity in entities)


_ENTRANCE_WORDS = {
    "drop": "dropped from above",
    "slide_left": "slid in from the left",
    "slide_right": "slid in from the right",
    "scale_pop": "pressed down into place",
    "rotate_in": "rotated into place",
    "rise": "pushed up from below",
}
