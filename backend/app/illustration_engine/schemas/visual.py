"""Visual vocabulary: what kinds of scenes exist and what they are made of.

These are plain dataclasses on purpose. The illustration engine must stay
importable from the standalone `autoedit_engine` CLI, whose dependency budget
is numpy + Pillow + requests — no pydantic, no FastAPI.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# scene types
# --------------------------------------------------------------------------- #
# The twelve supported visual types. Ordered roughly from "hand drawn" to
# "graphic", which is also the order the router falls back through.
WHITEBOARD = "whiteboard"
DIAGRAM = "diagram"
FLOWCHART = "flowchart"
PROCESS = "process"
TIMELINE = "timeline"
COMPARISON = "comparison"
STATISTICS = "statistics"
INFOGRAPHIC = "infographic"
CONCEPT = "concept"
UI_EXPLAINER = "ui_explainer"
KINETIC_TYPOGRAPHY = "kinetic_typography"
MOTION_GRAPHICS = "motion_graphics"

VISUAL_TYPES: Tuple[str, ...] = (
    WHITEBOARD, DIAGRAM, FLOWCHART, PROCESS, TIMELINE, COMPARISON,
    STATISTICS, INFOGRAPHIC, CONCEPT, UI_EXPLAINER, KINETIC_TYPOGRAPHY,
    MOTION_GRAPHICS,
)

# --------------------------------------------------------------------------- #
# discourse patterns the analyzer can recognise
# --------------------------------------------------------------------------- #
P_LIST = "list"                  # "il y a trois choses"
P_STEPS = "steps"                # "premièrement... ensuite... enfin"
P_COMPARISON = "comparison"      # "avant... maintenant"
P_NUMBER = "number"              # "87% des..."
P_CAUSE = "cause_effect"         # "parce que... donc"
P_PROBLEM = "problem_solution"   # "le problème... la solution"
P_DEFINITION = "definition"      # "X, c'est..."
P_PROCESS = "process"            # "d'abord on... puis le système..."
P_ARCHITECTURE = "architecture"  # "il y a le serveur, la base..."
P_KEYWORD = "keyword"            # dense keyword emphasis, no structure

PATTERNS: Tuple[str, ...] = (
    P_LIST, P_STEPS, P_COMPARISON, P_NUMBER, P_CAUSE, P_PROBLEM,
    P_DEFINITION, P_PROCESS, P_ARCHITECTURE, P_KEYWORD,
)

# Element roles — drive both layout and reveal style.
R_TITLE = "title"
R_ITEM = "item"
R_NUMBER = "number"
R_ICON = "icon"
R_CONNECTOR = "connector"
R_LABEL = "label"
R_SIDE_A = "side_a"
R_SIDE_B = "side_b"
R_CAPTION = "caption"
R_UNDERLINE = "underline"


@dataclass
class Box:
    """Normalised placement in 0..1 canvas coordinates, origin top-left."""
    x: float
    y: float
    w: float
    h: float

    def pixels(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """(x1, y1, x2, y2) in pixels, clamped inside the canvas."""
        x1 = max(0, min(width, int(round(self.x * width))))
        y1 = max(0, min(height, int(round(self.y * height))))
        x2 = max(x1 + 1, min(width, int(round((self.x + self.w) * width))))
        y2 = max(y1 + 1, min(height, int(round((self.y + self.h) * height))))
        return x1, y1, x2, y2

    def center(self, width: int, height: int) -> Tuple[int, int]:
        x1, y1, x2, y2 = self.pixels(width, height)
        return (x1 + x2) // 2, (y1 + y2) // 2

    @property
    def area(self) -> float:
        return max(self.w, 0.0) * max(self.h, 0.0)

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass
class VisualElement:
    """One drawable thing on the canvas.

    `text` is what the viewer reads, `icon` names an entry of the icon library,
    and `box` says where it goes. `reveal_order` is 1-indexed and unique inside
    a scene — it is the order a hand would draw them.
    """
    element_id: str
    role: str
    reveal_order: int
    box: Box
    text: str = ""
    icon: str = ""
    shape: str = ""             # card | circle | arrow | bar | underline | ...
    value: Optional[float] = None
    unit: str = ""
    emphasis: float = 0.5       # 0..1 — drives size, weight and colour
    annotation: str = ""        # narration spoken while this element draws
    connects: Tuple[str, str] = ("", "")   # for connectors: (from_id, to_id)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["box"] = self.box.to_dict()
        d["connects"] = list(self.connects)
        return d


@dataclass
class AnimationInstruction:
    """When and how one element comes alive, relative to the scene start."""
    element_id: str
    action: str             # draw | appear | pop | slide | count | connect | wipe
    start: float
    duration: float
    easing: str = "ease_out_cube"
    direction: str = ""     # for slide/wipe: up | down | left | right

    @property
    def end(self) -> float:
        return self.start + self.duration

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisualOpportunity:
    """A moment in the speech that may deserve an illustration."""
    start: float
    end: float
    text: str
    pattern: str
    visual_score: float
    importance: float
    concepts: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    numbers: List[Tuple[str, float]] = field(default_factory=list)
    sides: Tuple[str, str] = ("", "")
    reason: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["numbers"] = [list(n) for n in self.numbers]
        d["sides"] = list(self.sides)
        return d
