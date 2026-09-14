"""ScenePlanner — turn a scored opportunity into a fully laid-out scene.

Every layout answers the mission's quality rule: the picture must *explain*.
A list becomes labelled items, a process becomes nodes joined by arrows, a
comparison becomes two panels, a statistic becomes one number you cannot miss.
Nothing here is decorative.

Boxes are normalised 0..1, so the same plan renders at 1920x1080, 1080x1920
or 1080x1080 without a second layout pass.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Sequence, Tuple

from .. import config
from ..assets import icon_library
from ..schemas.scene import IllustrationScene
from ..schemas.visual import (
    AnimationInstruction, Box, COMPARISON, CONCEPT, DIAGRAM, FLOWCHART,
    INFOGRAPHIC, KINETIC_TYPOGRAPHY, MOTION_GRAPHICS, PROCESS, R_CAPTION,
    R_CONNECTOR, R_ICON, R_ITEM, R_LABEL, R_NUMBER, R_SIDE_A, R_SIDE_B,
    R_TITLE, R_UNDERLINE, STATISTICS, TIMELINE, UI_EXPLAINER, VisualElement,
    VisualOpportunity, WHITEBOARD,
)
from ..styles import Style, get_style

# Vertical bands shared by every layout.
TITLE_TOP = 0.07
TITLE_H = 0.13
BODY_TOP = 0.26
BODY_BOTTOM = 0.94
CAPTION_TOP = 0.90


def _title_box() -> Box:
    return Box(0.08, TITLE_TOP, 0.84, TITLE_H)


def _caption_box() -> Box:
    return Box(0.08, CAPTION_TOP, 0.84, 0.07)


def _short(text: str, limit: int = 26) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class ScenePlanner:
    """Builds the element graph and the animation sequence for one scene."""

    def __init__(self, style: str = "professional", aspect: str = "16:9"):
        self.style: Style = get_style(style)
        self.aspect = aspect
        width, height = config.aspect_size(aspect)
        self.wide = width >= height * 1.2
        self.square = 0.85 <= width / max(height, 1) <= 1.2

    # ------------------------------------------------------------------ #
    def plan(self, opportunity: VisualOpportunity, visual_type: str,
             scene_id: str, start: float, end: float,
             title: str = "", subtitle: str = "") -> IllustrationScene:
        scene = IllustrationScene(
            scene_id=scene_id, start=start, end=end,
            spoken_text=opportunity.text, concept=title or "",
            importance=opportunity.importance,
            visual_score=opportunity.visual_score,
            visual_type=visual_type, pattern=opportunity.pattern,
            style=self.style.name, title=title, subtitle=subtitle,
            concepts=list(opportunity.concepts), reason=opportunity.reason,
        )
        builder = self._BUILDERS.get(visual_type, ScenePlanner._build_motion_graphics)
        builder(self, scene, opportunity)
        self._sequence(scene)
        return scene

    # ------------------------------------------------------------------ #
    # element helpers
    # ------------------------------------------------------------------ #
    def _add(self, scene: IllustrationScene, role: str, box: Box, **kw) -> VisualElement:
        element = VisualElement(
            element_id=f"{scene.scene_id}_e{len(scene.elements) + 1:02d}",
            role=role, reveal_order=len(scene.elements) + 1, box=box, **kw)
        scene.elements.append(element)
        return element

    def _add_title(self, scene: IllustrationScene) -> VisualElement:
        title = self._add(scene, R_TITLE, _title_box(), text=scene.title or "",
                          emphasis=1.0, annotation=scene.spoken_text[:60])
        self._add(scene, R_UNDERLINE,
                  Box(0.08, TITLE_TOP + TITLE_H + 0.012, 0.24, 0.008),
                  shape="underline", emphasis=0.8)
        return title

    def _icons_for(self, labels: Sequence[str]) -> List[str]:
        """One icon per label, never twice the same inside a scene."""
        used: List[str] = []
        for label in labels:
            name = icon_library.icon_for(label, exclude=used)
            used.append(name)
        return used

    def _rows(self, n: int, top: float = BODY_TOP,
              bottom: float = BODY_BOTTOM, gap: float = 0.03) -> List[Box]:
        n = max(1, n)
        total = bottom - top
        height = (total - gap * (n - 1)) / n
        return [Box(0.10, top + i * (height + gap), 0.80, height) for i in range(n)]

    def _columns(self, n: int, top: float = BODY_TOP,
                 bottom: float = BODY_BOTTOM, gap: float = 0.035) -> List[Box]:
        """Columns sized for their content, then centred in the body band.

        Filling the whole band with three tall columns leaves a void between
        the icon and the label; a card should be about as tall as it is wide.
        """
        n = max(1, n)
        width = (0.84 - gap * (n - 1)) / n
        band = bottom - top
        # Target a portrait-ish card, clamped to the band we actually have.
        height = min(band * 0.80,
                     max(0.36, width * (1.75 if self.wide else 0.9)))
        y = top + (band - height) / 2.0
        return [Box(0.08 + i * (width + gap), y, width, height)
                for i in range(n)]

    def _slots(self, n: int, bottom: float = BODY_BOTTOM) -> List[Box]:
        """Columns on a wide canvas, rows on a tall one."""
        return (self._columns(n, bottom=bottom) if self.wide
                else self._rows(n, bottom=bottom))

    # ------------------------------------------------------------------ #
    # layouts
    # ------------------------------------------------------------------ #
    def _build_infographic(self, scene: IllustrationScene,
                           opp: VisualOpportunity) -> None:
        """A list: numbered, iconified items the viewer can count."""
        self._add_title(scene)
        items = [i for i in opp.items if i][:4] or opp.concepts[:3] or ["", ""]
        icons = self._icons_for(items)
        slots = self._slots(len(items), bottom=CAPTION_TOP - 0.03)
        for index, (box, label) in enumerate(zip(slots, items)):
            self._add(scene, R_ITEM, box, text=_short(label), shape="card",
                      icon=icons[index], value=float(index + 1),
                      emphasis=0.85, annotation=label)
        self._add(scene, R_CAPTION, _caption_box(), text=_short(scene.subtitle, 40),
                  emphasis=0.4)

    def _build_process(self, scene: IllustrationScene,
                       opp: VisualOpportunity) -> None:
        """Steps: numbered nodes joined by arrows — the flow is the message."""
        self._add_title(scene)
        items = [i for i in opp.items if i][:4] or ["1", "2", "3"]
        icons = self._icons_for(items)
        boxes = self._slots(len(items))
        nodes: List[VisualElement] = []
        for index, (box, label) in enumerate(zip(boxes, items)):
            nodes.append(self._add(
                scene, R_ITEM, box, text=_short(label, 22), shape="node",
                icon=icons[index], value=float(index + 1), emphasis=0.9,
                annotation=label))
        for index in range(len(nodes) - 1):
            a, b = nodes[index], nodes[index + 1]
            if self.wide:
                gap = Box(a.box.x + a.box.w, a.box.y + a.box.h * 0.42,
                          max(b.box.x - (a.box.x + a.box.w), 0.01), 0.08)
            else:
                gap = Box(a.box.x + a.box.w * 0.44, a.box.y + a.box.h,
                          0.10, max(b.box.y - (a.box.y + a.box.h), 0.01))
            self._add(scene, R_CONNECTOR, gap,
                      shape="arrow_h" if self.wide else "arrow_v",
                      emphasis=0.7, connects=(a.element_id, b.element_id))

    def _build_flowchart(self, scene: IllustrationScene,
                         opp: VisualOpportunity) -> None:
        """Cause -> effect, or a short pipeline: two or three linked boxes."""
        labels = [i for i in opp.items if i][:3]
        if not labels and opp.sides[0]:
            labels = [opp.sides[0], opp.sides[1]]
        if len(labels) < 2:
            labels = (labels + opp.concepts + ["Cause", "Effet"])[:2]
        self._add_title(scene)
        icons = self._icons_for(labels)
        boxes = self._slots(len(labels))
        nodes = [
            self._add(scene, R_ITEM, box, text=_short(label, 22), shape="card",
                      icon=icons[i], emphasis=0.85, annotation=label)
            for i, (box, label) in enumerate(zip(boxes, labels))
        ]
        for index in range(len(nodes) - 1):
            a, b = nodes[index], nodes[index + 1]
            if self.wide:
                gap = Box(a.box.x + a.box.w, a.box.y + a.box.h * 0.44,
                          max(b.box.x - (a.box.x + a.box.w), 0.01), 0.09)
            else:
                gap = Box(a.box.x + a.box.w * 0.45, a.box.y + a.box.h,
                          0.10, max(b.box.y - (a.box.y + a.box.h), 0.01))
            self._add(scene, R_CONNECTOR, gap,
                      shape="arrow_h" if self.wide else "arrow_v",
                      emphasis=0.75, connects=(a.element_id, b.element_id))

    def _build_comparison(self, scene: IllustrationScene,
                          opp: VisualOpportunity) -> None:
        """Two panels and a divider: the contrast has to be instant."""
        self._add_title(scene)
        left = opp.sides[0] or (opp.items[0] if opp.items else "Avant")
        right = opp.sides[1] or (opp.items[1] if len(opp.items) > 1 else "Après")
        icons = self._icons_for([left, right])
        if self.wide:
            box_a = Box(0.07, BODY_TOP, 0.40, BODY_BOTTOM - BODY_TOP)
            box_b = Box(0.53, BODY_TOP, 0.40, BODY_BOTTOM - BODY_TOP)
            divider = Box(0.495, BODY_TOP + 0.02, 0.008, BODY_BOTTOM - BODY_TOP - 0.04)
        else:
            half = (BODY_BOTTOM - BODY_TOP - 0.05) / 2
            box_a = Box(0.09, BODY_TOP, 0.82, half)
            box_b = Box(0.09, BODY_TOP + half + 0.05, 0.82, half)
            divider = Box(0.20, BODY_TOP + half + 0.021, 0.60, 0.008)
        self._add(scene, R_SIDE_A, box_a, text=_short(left, 34), shape="panel",
                  icon=icons[0], emphasis=0.85, annotation=left)
        self._add(scene, R_SIDE_B, box_b, text=_short(right, 34), shape="panel",
                  icon=icons[1], emphasis=0.95, annotation=right)
        self._add(scene, R_CONNECTOR, divider, shape="divider", emphasis=0.5)

    def _build_statistics(self, scene: IllustrationScene,
                          opp: VisualOpportunity) -> None:
        """One number, big enough to be the whole point, plus its meaning."""
        self._add_title(scene)
        display, value = (opp.numbers[0] if opp.numbers else ("", 0.0))
        is_percent = "%" in display
        self._add(scene, R_NUMBER,
                  Box(0.10, 0.29, 0.80, 0.26), text=display, value=value,
                  unit="%" if is_percent else "", shape="counter", emphasis=1.0,
                  annotation=display)
        bar_value = min(1.0, value / 100.0) if is_percent else 0.0
        self._add(scene, R_LABEL, Box(0.16, 0.645, 0.68, 0.045),
                  shape="bar" if is_percent else "rule",
                  value=bar_value if is_percent else 1.0, emphasis=0.8)
        caption = _short(opp.concepts and " ".join(opp.concepts[:3]).title()
                         or scene.subtitle, 44)
        self._add(scene, R_CAPTION, Box(0.10, 0.72, 0.80, 0.10), text=caption,
                  emphasis=0.6, annotation=caption)
        self._add(scene, R_ICON, Box(0.44, 0.835, 0.12, 0.09),
                  icon=icon_library.icon_for(opp.text), emphasis=0.5)

    def _build_diagram(self, scene: IllustrationScene,
                       opp: VisualOpportunity) -> None:
        """Architecture: a hub with its components around it."""
        self._add_title(scene)
        parts = [i for i in opp.items if i][:4] or opp.concepts[:3] or ["Système"]
        # A hub box is small: use one concept, never the full scene title.
        hub_label = (opp.concepts[0].title() if opp.concepts
                     else (scene.title.split()[0].title() if scene.title
                           else "Système"))
        hub = self._add(scene, R_ITEM, Box(0.385, 0.47, 0.23, 0.17),
                        text=_short(hub_label, 16), shape="hub",
                        icon=icon_library.icon_for(hub_label), emphasis=1.0,
                        annotation=hub_label)
        # Satellites arranged for the count actually present — a fixed
        # four-corner ring leaves an obvious hole when only three are used.
        rings = {
            1: [(0.68, 0.485)],
            2: [(0.07, 0.485), (0.70, 0.485)],
            3: [(0.07, 0.28), (0.70, 0.28), (0.385, 0.76)],
            4: [(0.07, 0.28), (0.70, 0.28), (0.07, 0.70), (0.70, 0.70)],
        }
        vertical_rings = {
            1: [(0.33, 0.74)],
            2: [(0.09, 0.74), (0.58, 0.74)],
            3: [(0.09, 0.28), (0.58, 0.28), (0.33, 0.76)],
            4: [(0.09, 0.28), (0.58, 0.28), (0.09, 0.76), (0.58, 0.76)],
        }
        count = max(1, min(4, len(parts)))
        ring = (rings if self.wide else vertical_rings)[count]
        icons = self._icons_for(parts)
        for index, label in enumerate(parts[:4]):
            x, y = ring[index]
            node = self._add(scene, R_ITEM, Box(x, y, 0.23, 0.13),
                             text=_short(label, 16), shape="card",
                             icon=icons[index], emphasis=0.8, annotation=label)
            self._add(scene, R_CONNECTOR,
                      Box(min(x, 0.385), min(y, 0.47), 0.23, 0.13),
                      shape="link", emphasis=0.55,
                      connects=(hub.element_id, node.element_id))

    def _build_timeline(self, scene: IllustrationScene,
                        opp: VisualOpportunity) -> None:
        """Milestones on an axis — ordering is the information."""
        self._add_title(scene)
        items = [i for i in opp.items if i][:4] or opp.concepts[:3] or ["", ""]
        axis_y = 0.56 if self.wide else 0.30
        self._add(scene, R_CONNECTOR, Box(0.08, axis_y, 0.84, 0.006),
                  shape="axis", emphasis=0.6)
        n = len(items)
        icons = self._icons_for(items)
        for index, label in enumerate(items):
            cx = 0.10 + (0.80 * (index / max(n - 1, 1)) if n > 1 else 0.40)
            above = index % 2 == 0
            self._add(scene, R_ITEM,
                      Box(max(0.02, cx - 0.09), axis_y - 0.22 if above else axis_y + 0.05,
                          0.18, 0.17),
                      text=_short(label, 16), shape="milestone", icon=icons[index],
                      value=float(index + 1), emphasis=0.85, annotation=label)

    def _build_concept(self, scene: IllustrationScene,
                       opp: VisualOpportunity) -> None:
        """A definition: the term, then what it means."""
        term = scene.title or (opp.concepts[0].title() if opp.concepts else "")
        meaning = scene.subtitle or _short(opp.text, 90)
        self._add(scene, R_ICON, Box(0.42, 0.16, 0.16, 0.14),
                  icon=icon_library.icon_for(term or opp.text), emphasis=0.8)
        self._add(scene, R_TITLE, Box(0.08, 0.34, 0.84, 0.16),
                  text=term.upper(), emphasis=1.0, annotation=term)
        self._add(scene, R_UNDERLINE, Box(0.38, 0.515, 0.24, 0.008),
                  shape="underline", emphasis=0.8)
        self._add(scene, R_CAPTION, Box(0.12, 0.57, 0.76, 0.24),
                  text=meaning, shape="paragraph", emphasis=0.6,
                  annotation=meaning)

    def _build_ui_explainer(self, scene: IllustrationScene,
                            opp: VisualOpportunity) -> None:
        """A stylised interface with the discussed rows highlighted."""
        self._add_title(scene)
        frame = Box(0.14, BODY_TOP, 0.72, BODY_BOTTOM - BODY_TOP) if self.wide \
            else Box(0.10, BODY_TOP, 0.80, BODY_BOTTOM - BODY_TOP)
        self._add(scene, R_ITEM, frame, shape="frame", emphasis=0.5)
        rows = [i for i in opp.items if i][:3] or opp.concepts[:3] or ["", "", ""]
        icons = self._icons_for(rows)
        inner_top = frame.y + 0.12
        row_h = (frame.h - 0.16) / max(len(rows), 1)
        for index, label in enumerate(rows):
            self._add(scene, R_ITEM,
                      Box(frame.x + 0.04, inner_top + index * row_h,
                          frame.w - 0.08, row_h * 0.74),
                      text=_short(label, 26), shape="row", icon=icons[index],
                      emphasis=0.8, annotation=label)

    def _build_kinetic(self, scene: IllustrationScene,
                       opp: VisualOpportunity) -> None:
        """Typography only: the words themselves, one at a time."""
        words = [w for w in (opp.concepts[:3] or (scene.title or opp.text).split()[:3])]
        words = [w.upper() for w in words if w]
        if not words:
            words = [_short(opp.text, 18).upper()]
        boxes = self._rows(len(words), top=0.28, bottom=0.80, gap=0.02)
        for index, (box, word) in enumerate(zip(boxes, words)):
            self._add(scene, R_TITLE, box, text=word, shape="kinetic",
                      emphasis=1.0 - index * 0.15, annotation=word)
        self._add(scene, R_CAPTION, _caption_box(),
                  text=_short(opp.text, 56), emphasis=0.45)

    def _build_whiteboard(self, scene: IllustrationScene,
                          opp: VisualOpportunity) -> None:
        """Hand-drawn: title, sketched items, hand arrows between them.

        Structurally the same graph as a process; the renderer decides it is
        ink on white and draws it stroke by stroke.
        """
        if opp.items and len(opp.items) >= 2:
            self._build_process(scene, opp)
        elif opp.sides[0] and opp.sides[1]:
            self._build_comparison(scene, opp)
        elif opp.numbers:
            self._build_statistics(scene, opp)
        else:
            self._build_motion_graphics(scene, opp)

    def _build_motion_graphics(self, scene: IllustrationScene,
                               opp: VisualOpportunity) -> None:
        """The generic fallback: one card, one icon, one idea."""
        self._add_title(scene)
        label = (opp.items[0] if opp.items
                 else (opp.concepts[0].title() if opp.concepts else ""))
        body = Box(0.16, BODY_TOP + 0.02, 0.68, 0.44) if self.wide \
            else Box(0.12, BODY_TOP + 0.02, 0.76, 0.40)
        self._add(scene, R_ITEM, body, text=_short(label, 24), shape="card",
                  icon=icon_library.icon_for(label or opp.text), emphasis=0.9,
                  annotation=label or opp.text[:40])
        self._add(scene, R_CAPTION, Box(0.10, 0.76, 0.80, 0.14),
                  text=_short(opp.text, 76), shape="paragraph", emphasis=0.55,
                  annotation=opp.text[:60])

    _BUILDERS: Dict[str, Callable] = {
        INFOGRAPHIC: _build_infographic,
        PROCESS: _build_process,
        FLOWCHART: _build_flowchart,
        COMPARISON: _build_comparison,
        STATISTICS: _build_statistics,
        DIAGRAM: _build_diagram,
        TIMELINE: _build_timeline,
        CONCEPT: _build_concept,
        UI_EXPLAINER: _build_ui_explainer,
        KINETIC_TYPOGRAPHY: _build_kinetic,
        WHITEBOARD: _build_whiteboard,
        MOTION_GRAPHICS: _build_motion_graphics,
    }

    # ------------------------------------------------------------------ #
    # animation
    # ------------------------------------------------------------------ #
    _ACTIONS: Dict[str, str] = {
        R_TITLE: "draw", R_UNDERLINE: "wipe", R_ITEM: "pop", R_NUMBER: "count",
        R_CONNECTOR: "connect", R_ICON: "draw", R_LABEL: "wipe",
        R_SIDE_A: "slide", R_SIDE_B: "slide", R_CAPTION: "appear",
    }

    def _sequence(self, scene: IllustrationScene) -> None:
        """Spread the reveals across the scene, weighted by how much each
        element has to say, holding the finished picture at the end."""
        elements = scene.ordered_elements()
        if not elements:
            return
        speed = max(0.4, self.style.anim_speed)
        weights = []
        for element in elements:
            text_weight = len(element.annotation or element.text or "") + 8
            weights.append(text_weight * (0.6 + 0.8 * element.emphasis))

        duration = scene.duration
        budget = duration * 0.72
        total = float(sum(weights)) or 1.0
        cursor = 0.12
        for element, weight in zip(elements, weights):
            slot = budget * (weight / total)
            action = self._ACTIONS.get(element.role, "appear")
            if element.shape == "kinetic":
                action = "pop"
            anim_dur = max(0.22, min(slot * 0.9, 1.4)) / speed
            scene.animation_sequence.append(AnimationInstruction(
                element_id=element.element_id, action=action,
                start=round(min(cursor, max(duration - 0.4, 0.0)), 3),
                duration=round(anim_dur, 3),
                easing="ease_out_back" if action == "pop" else "ease_out_cube",
                direction="left" if element.role == R_SIDE_A else
                          ("right" if element.role == R_SIDE_B else "up"),
            ))
            cursor += slot
