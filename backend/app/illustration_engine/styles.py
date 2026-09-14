"""Style presets.

A style controls palette, typography, line thickness, animation speed,
transition, density and icon treatment — everything that makes two videos look
like they came from different studios while each stays internally consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

RGBA = Tuple[int, int, int, int]


@dataclass
class Style:
    name: str
    # palette
    bg: RGBA
    bg_alt: RGBA
    ink: RGBA              # primary text / strokes
    muted: RGBA            # secondary text
    accent: RGBA           # the one colour that carries meaning
    accent_alt: RGBA       # second accent, for comparisons / second series
    surface: RGBA          # cards, plates
    positive: RGBA
    negative: RGBA
    # typography
    font_title: str
    font_body: str
    font_number: str
    title_scale: float = 1.0
    # drawing
    line_width: int = 8
    corner_radius: int = 28
    # motion
    anim_speed: float = 1.0     # >1 = snappier
    transition: str = "slide_up"
    # composition
    density: float = 1.0        # >1 = more elements allowed per scene
    icon_style: str = "line"    # line | solid
    on_white: bool = False      # whiteboard-family styles draw ink on white

    def scaled(self, px: int) -> int:
        return max(1, int(round(px * self.title_scale)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "font_title": self.font_title,
            "line_width": self.line_width, "anim_speed": self.anim_speed,
            "density": self.density, "icon_style": self.icon_style,
            "on_white": self.on_white, "transition": self.transition,
        }


_W: RGBA = (255, 255, 255, 255)
_BLACK: RGBA = (17, 19, 24, 255)


STYLES: Dict[str, Style] = {
    "professional": Style(
        name="professional",
        bg=(12, 16, 28, 255), bg_alt=(22, 28, 46, 255),
        ink=_W, muted=(163, 176, 201, 255),
        accent=(64, 156, 255, 255), accent_alt=(255, 199, 64, 255),
        surface=(28, 36, 58, 255),
        positive=(56, 208, 142, 255), negative=(255, 106, 106, 255),
        font_title="Montserrat", font_body="Inter", font_number="Anton",
        line_width=8, anim_speed=1.0, transition="slide_up", density=1.0,
    ),
    "education": Style(
        name="education",
        bg=(255, 252, 244, 255), bg_alt=(246, 238, 222, 255),
        ink=(32, 34, 40, 255), muted=(112, 108, 98, 255),
        accent=(232, 106, 51, 255), accent_alt=(45, 128, 196, 255),
        surface=(255, 255, 255, 255),
        positive=(46, 160, 108, 255), negative=(206, 68, 60, 255),
        font_title="Poppins", font_body="Inter", font_number="Anton",
        line_width=9, anim_speed=0.9, transition="draw", density=1.1,
        icon_style="line", on_white=True,
    ),
    "business": Style(
        name="business",
        bg=(14, 20, 30, 255), bg_alt=(24, 34, 50, 255),
        ink=_W, muted=(158, 172, 190, 255),
        accent=(0, 196, 180, 255), accent_alt=(255, 186, 73, 255),
        surface=(26, 38, 56, 255),
        positive=(0, 196, 140, 255), negative=(240, 96, 96, 255),
        font_title="Montserrat", font_body="Inter", font_number="Anton",
        line_width=7, anim_speed=1.1, transition="slide_left", density=1.0,
    ),
    "technology": Style(
        name="technology",
        bg=(8, 10, 20, 255), bg_alt=(16, 20, 38, 255),
        ink=_W, muted=(140, 152, 186, 255),
        accent=(0, 224, 255, 255), accent_alt=(168, 106, 255, 255),
        surface=(20, 26, 46, 255),
        positive=(0, 230, 176, 255), negative=(255, 88, 120, 255),
        font_title="Montserrat", font_body="Inter", font_number="Anton",
        line_width=6, anim_speed=1.25, transition="glitch", density=1.15,
    ),
    "finance": Style(
        name="finance",
        bg=(10, 22, 20, 255), bg_alt=(16, 34, 30, 255),
        ink=_W, muted=(150, 178, 168, 255),
        accent=(212, 175, 82, 255), accent_alt=(86, 196, 156, 255),
        surface=(18, 40, 36, 255),
        positive=(72, 208, 138, 255), negative=(228, 92, 84, 255),
        font_title="Playfair", font_body="Inter", font_number="Anton",
        line_width=7, anim_speed=0.95, transition="fade", density=0.9,
    ),
    "marketing": Style(
        name="marketing",
        bg=(26, 12, 38, 255), bg_alt=(44, 18, 60, 255),
        ink=_W, muted=(198, 176, 216, 255),
        accent=(255, 86, 148, 255), accent_alt=(255, 206, 84, 255),
        surface=(46, 22, 64, 255),
        positive=(88, 220, 160, 255), negative=(255, 104, 104, 255),
        font_title="Anton", font_body="Poppins", font_number="Anton",
        line_width=9, anim_speed=1.3, transition="pop", density=1.2,
    ),
    "minimal": Style(
        name="minimal",
        bg=(248, 248, 246, 255), bg_alt=(238, 238, 234, 255),
        ink=(24, 24, 26, 255), muted=(128, 128, 132, 255),
        accent=(24, 24, 26, 255), accent_alt=(220, 76, 52, 255),
        surface=(255, 255, 255, 255),
        positive=(40, 150, 100, 255), negative=(200, 70, 60, 255),
        font_title="Inter", font_body="Inter", font_number="Inter",
        line_width=5, corner_radius=8, anim_speed=0.85, transition="fade",
        density=0.8, on_white=True,
    ),
    "whiteboard": Style(
        name="whiteboard",
        bg=_W, bg_alt=(250, 250, 248, 255),
        ink=_BLACK, muted=(96, 100, 108, 255),
        accent=(214, 62, 48, 255), accent_alt=(36, 96, 200, 255),
        surface=_W,
        positive=(36, 140, 84, 255), negative=(214, 62, 48, 255),
        font_title="Caveat", font_body="Caveat", font_number="Caveat",
        line_width=10, corner_radius=16, anim_speed=0.8, transition="draw",
        density=1.0, icon_style="line", on_white=True,
    ),
    "dark_premium": Style(
        name="dark_premium",
        bg=(6, 7, 10, 255), bg_alt=(14, 16, 22, 255),
        ink=_W, muted=(146, 150, 160, 255),
        accent=(226, 190, 118, 255), accent_alt=(120, 150, 255, 255),
        surface=(18, 20, 28, 255),
        positive=(96, 206, 150, 255), negative=(226, 96, 96, 255),
        font_title="Playfair", font_body="Inter", font_number="Anton",
        line_width=6, corner_radius=20, anim_speed=0.9, transition="fade",
        density=0.85,
    ),
    "clean": Style(
        name="clean",
        bg=_W, bg_alt=(244, 247, 252, 255),
        ink=(20, 26, 38, 255), muted=(118, 130, 150, 255),
        accent=(38, 110, 232, 255), accent_alt=(246, 158, 40, 255),
        surface=(248, 250, 254, 255),
        positive=(32, 168, 112, 255), negative=(224, 78, 68, 255),
        font_title="Poppins", font_body="Inter", font_number="Anton",
        line_width=7, corner_radius=22, anim_speed=1.0, transition="slide_up",
        density=1.0, on_white=True,
    ),
}

DEFAULT_STYLE = "professional"

# Frontend-facing subset (the six the UI offers), mapped to preset names.
UI_STYLES: Dict[str, str] = {
    "Professional": "professional",
    "Education": "education",
    "Business": "business",
    "Tech": "technology",
    "Whiteboard": "whiteboard",
    "Minimal": "minimal",
}


def get_style(name: str | None) -> Style:
    """Resolve a style by preset name or UI label; never raises."""
    if not name:
        return STYLES[DEFAULT_STYLE]
    key = str(name).strip()
    if key in STYLES:
        return STYLES[key]
    if key in UI_STYLES:
        return STYLES[UI_STYLES[key]]
    low = key.lower().replace(" ", "_").replace("-", "_")
    return STYLES.get(low, STYLES[DEFAULT_STYLE])


def style_names() -> list:
    return sorted(STYLES)
