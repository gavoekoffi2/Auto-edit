"""StoryboardPlanner — choose which moments become scenes, and in what order.

This is where the mission's "ce que je ne veux pas" list is enforced: the
talking head stays the backbone, animations appear only where they earn their
place, never back-to-back, never twice the same idea, never the same visual
type over and over.
"""
from __future__ import annotations

import math
import re

from typing import Dict, List, Optional, Sequence, Tuple

from .. import config
from ..analyzer.concept_detector import ConceptDetector
from ..analyzer.lexicon import fold
from ..schemas.scene import IllustrationScene
from ..schemas.storyboard import Storyboard
from ..schemas.visual import P_DEFINITION, P_NUMBER, VisualOpportunity
from .scene_planner import ScenePlanner
from .timing_planner import TimingPlanner
from .visual_type_selector import VisualTypeSelector


def _similarity(a: Sequence[str], b: Sequence[str]) -> float:
    """Jaccard overlap of two concept sets."""
    sa, sb = {fold(x) for x in a if x}, {fold(x) for x in b if x}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


class StoryboardPlanner:
    def __init__(self, style: str = "professional", intensity: str = "medium",
                 aspect: str = "16:9", concepts: Optional[ConceptDetector] = None):
        self.style = style
        self.intensity = intensity or config.DEFAULT_INTENSITY
        self.profile = config.intensity_profile(self.intensity)
        self.selector = VisualTypeSelector(style)
        self.scene_planner = ScenePlanner(style, aspect)
        self.concepts = concepts or ConceptDetector()

    # ------------------------------------------------------------------ #
    def _budget(self, total_duration: float) -> int:
        """Upper bound on scene count for this video at this intensity.

        Rounded up, not to nearest: the coverage ceiling is the real governor
        of how much screen the illustrations get, and rounding down here would
        silently drop a deserved scene from a 50-second video while a
        60-second one keeps it.
        """
        minutes = max(total_duration, 1.0) / 60.0
        planned = math.ceil(minutes * float(self.profile["per_minute"]))
        return max(1, min(config.MAX_SCENES, planned))

    @staticmethod
    def _number_sentence(opp: VisualOpportunity) -> str:
        """The sentence of the unit that actually contains the first figure."""
        if not opp.numbers:
            return opp.text
        needle = opp.numbers[0][0]
        for sentence in re.split(r"(?<=[.!?…])\s+", opp.text or ""):
            if needle in sentence:
                return sentence
        return opp.text

    def _title_for(self, opp: VisualOpportunity) -> Tuple[str, str]:
        """(title, subtitle) — the words the viewer reads first."""
        if opp.pattern == P_NUMBER and opp.numbers:
            # Title the statistic from the sentence that carries the figure,
            # not from the whole unit — the neighbouring sentence is usually
            # about something else entirely.
            return (self.concepts.headline(self._number_sentence(opp), 3)
                    or "CHIFFRE CLÉ", "CHIFFRE CLÉ")
        if opp.pattern == P_DEFINITION:
            return (self.concepts.headline(opp.text, 3), "DÉFINITION")
        subtitle = {
            "list": "À RETENIR", "steps": "ÉTAPES", "comparison": "AVANT / APRÈS",
            "problem_solution": "PROBLÈME / SOLUTION", "cause_effect": "POURQUOI",
            "process": "PROCESSUS", "architecture": "ARCHITECTURE",
        }.get(opp.pattern, "À RETENIR")
        # When the passage enumerates, the items ARE the subject: titling from
        # them avoids picking up the verb that introduced the list.
        source = " ".join(opp.items) if len(opp.items) >= 2 else opp.text
        return (self.concepts.headline(source, 4), subtitle)

    def _target_duration(self, opp: VisualOpportunity) -> float:
        """How long this scene needs on screen, from how much it has to reveal.

        A three-item list needs longer than a single statistic. Sizing the
        scene to its content is what keeps the face on screen the rest of the
        time instead of padding every takeover to the maximum.
        """
        reveals = len([i for i in opp.items if i])
        if opp.sides[0] and opp.sides[1]:
            reveals = max(reveals, 2)
        if opp.numbers:
            reveals = max(reveals, 1)
        return 3.2 + 0.85 * reveals

    # ------------------------------------------------------------------ #
    def plan(self, opportunities: Sequence[VisualOpportunity], vu: dict,
             total_duration: float = 0.0, ai_mode: str = "offline",
             provider: str = "heuristic") -> Storyboard:
        total = float(total_duration or (vu or {}).get("duration") or 0.0)
        if not total and opportunities:
            total = max(o.end for o in opportunities)

        board = Storyboard(source_duration=total, style=self.style,
                           intensity=self.intensity, ai_mode=ai_mode,
                           provider=provider)
        if not opportunities:
            board.notes.append("aucune opportunité visuelle détectée")
            return board

        threshold = float(self.profile["threshold"])
        budget = self._budget(total)
        max_coverage = float(self.profile["max_coverage"])
        min_gap = float(self.profile.get("min_gap", config.MIN_GAP))

        # Strongest first: a limited budget must go to the best moments, not
        # simply to the earliest ones.
        ranked = sorted(
            [o for o in opportunities if o.visual_score >= threshold],
            key=lambda o: (-o.visual_score, o.start))
        if not ranked:
            board.notes.append(
                f"aucun passage au-dessus du seuil {threshold:.2f} "
                f"(intensité « {self.intensity} »)")
            return board

        timing = TimingPlanner(vu, total)
        accepted: List[Tuple[float, float, VisualOpportunity]] = []
        rejected: Dict[str, int] = {}

        def _reject(reason: str) -> None:
            rejected[reason] = rejected.get(reason, 0) + 1

        for opp in ranked:
            if len(accepted) >= budget:
                _reject("budget")
                break
            # Spacing is checked against every accepted scene, not just the
            # previous one, because ranking is by score and not by time.
            conflict = False
            for start, end, _o in accepted:
                if opp.start < end + min_gap and opp.end > start - min_gap:
                    conflict = True
                    break
            if conflict:
                _reject("espacement")
                continue
            if any(_similarity(opp.concepts, other.concepts) >= config.REPEAT_SIMILARITY
                   for _s, _e, other in accepted):
                _reject("répétition")
                continue
            span = timing.plan(opp.start, opp.end,
                               target_duration=self._target_duration(opp))
            if span is None:
                _reject("placement impossible")
                continue
            # The coverage ceiling protects the talking head from being
            # crowded out; it must not make a short clip un-illustratable.
            # The first scene is always allowed — one picture in a 15 s video
            # is the product working, not the backbone being lost.
            if accepted:
                projected = (sum(e - s for s, e, _o in accepted)
                             + (span[1] - span[0]))
                if total > 0 and projected / total > max_coverage:
                    _reject("couverture maximale")
                    continue
            accepted.append((span[0], span[1], opp))

        accepted.sort(key=lambda item: item[0])

        chosen_types: List[str] = []
        for index, (start, end, opp) in enumerate(accepted):
            visual_type = self.selector.select(opp, chosen_types, len(accepted))
            chosen_types.append(visual_type)
            title, subtitle = self._title_for(opp)
            # A provider may have proposed a better title than the heuristic
            # one; the type it proposed was already offered to the selector.
            suggested_title = getattr(opp, "suggested_title", "")
            if suggested_title:
                title = suggested_title
            scene = self.scene_planner.plan(
                opp, visual_type, f"ill_{index + 1:03d}", start, end,
                title=title, subtitle=subtitle)
            board.scenes.append(scene)

        for reason, count in sorted(rejected.items()):
            board.notes.append(f"{count} passage(s) écarté(s) — {reason}")
        board.notes.append(
            f"{len(board.scenes)} scène(s) retenue(s) sur {len(opportunities)} "
            f"passage(s) analysé(s), couverture {board.coverage * 100:.1f}%")
        return board
