"""Contrats de données du moteur « Pub explicative »."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Brief:
    """Ce que l'entretien récolte auprès du client (tout en langue du client)."""
    business: str = ""                 # nom de l'entreprise / de la marque
    offer: str = ""                    # ce qui est vendu (produit, service, programme)
    audience: str = ""                 # à qui ça s'adresse
    problem: str = ""                  # douleur principale de la cible
    promise: str = ""                  # résultat / transformation promise
    benefits: list[str] = field(default_factory=list)   # 2-4 bénéfices concrets
    proof: str = ""                    # preuve RÉELLE (chiffre, témoignage) — optionnel
    cta_action: str = "Cliquez sur le bouton juste en bas de cette vidéo"
    cta_detail: str = ""               # ex: « 30 minutes avec un conseiller », « livraison gratuite »
    tone: str = "vous"                 # vous | tu
    language: str = "fr"
    angle: str = "douleur"
    template: str = "prestige"
    brand_color: Optional[str] = None
    duration: int = 40                 # secondes visées
    disclaimer: str = ""               # mention légale courte si nécessaire
    voice: Optional[str] = None        # id de voix (provider-dépendant) ; « eleven:<id> » = ElevenLabs
    # --- Studio Pub (montages) ---
    montage: str = "impact"            # mode de montage (grammaire), cf. montages.MONTAGES
    domain: str = ""                   # domaine d'activité (ecommerce, physique, digital, services…)
    product_desc: str = ""             # description du produit / service
    consequences: str = ""             # ce que le problème coûte à la cible (agitation)
    price: str = ""                    # prix ou offre spéciale (fourni par le client)
    contact_phone: str = ""            # numéro affiché et prononcé à la fin
    product_asset: str = ""            # photo produit importée (id)
    logo_asset: str = ""               # logo importé (id)
    product_image_path: str = ""       # chemins résolus par le worker (internes)
    logo_path: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Brief":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        data = {k: v for k, v in (d or {}).items() if k in known}
        if isinstance(data.get("benefits"), str):
            data["benefits"] = [b.strip(" -•") for b in data["benefits"].replace(";", "\n").split("\n") if b.strip()]
        try:
            data["duration"] = max(20, min(75, int(data.get("duration", 40))))
        except (TypeError, ValueError):
            data["duration"] = 40
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Beat:
    """Une phrase de voix off + la scène qui l'illustre."""
    text: str
    scene: dict[str, Any]              # {"type": ..., params...} ou {"type": "continue"}
    pause_after: float = 0.35


@dataclass
class Storyboard:
    angle: str
    template: str
    beats: list[Beat]
    title: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"angle": self.angle, "template": self.template, "title": self.title,
                "notes": self.notes, "beats": [asdict(b) for b in self.beats]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Storyboard":
        beats = [Beat(text=str(b.get("text", "")).strip(), scene=dict(b.get("scene") or {"type": "continue"}),
                      pause_after=float(b.get("pause_after", 0.35) or 0.35))
                 for b in d.get("beats", []) if str(b.get("text", "")).strip()]
        return cls(angle=d.get("angle", "douleur"), template=d.get("template", "prestige"),
                   beats=beats, title=d.get("title", ""), notes=list(d.get("notes") or []))
