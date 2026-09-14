"""VisualTypeSelector — which of the twelve scene types explains this best?

Selection is driven first by the discourse pattern (a list wants an
enumeration, a process wants a flow), then nudged by the active style, then
constrained by diversity so a video never becomes twelve identical cards.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from .. import config
from ..schemas.visual import (
    COMPARISON, CONCEPT, DIAGRAM, FLOWCHART, INFOGRAPHIC, KINETIC_TYPOGRAPHY,
    MOTION_GRAPHICS, P_ARCHITECTURE, P_CAUSE, P_COMPARISON, P_DEFINITION,
    P_KEYWORD, P_LIST, P_NUMBER, P_PROBLEM, P_PROCESS, P_STEPS, PROCESS,
    STATISTICS, TIMELINE, UI_EXPLAINER, WHITEBOARD, VisualOpportunity,
)

# Ordered preference per discourse pattern. The first entry is the natural
# reading; the rest are equally correct alternatives used for variety.
PATTERN_TYPES: Dict[str, Tuple[str, ...]] = {
    P_LIST: (INFOGRAPHIC, WHITEBOARD, MOTION_GRAPHICS),
    P_STEPS: (PROCESS, WHITEBOARD, FLOWCHART, TIMELINE),
    P_COMPARISON: (COMPARISON, MOTION_GRAPHICS, INFOGRAPHIC),
    P_NUMBER: (STATISTICS, INFOGRAPHIC, MOTION_GRAPHICS),
    P_CAUSE: (FLOWCHART, DIAGRAM, MOTION_GRAPHICS),
    P_PROBLEM: (COMPARISON, DIAGRAM, WHITEBOARD),
    P_DEFINITION: (CONCEPT, KINETIC_TYPOGRAPHY, WHITEBOARD),
    P_PROCESS: (FLOWCHART, PROCESS, DIAGRAM),
    P_ARCHITECTURE: (DIAGRAM, UI_EXPLAINER, FLOWCHART),
    P_KEYWORD: (KINETIC_TYPOGRAPHY, MOTION_GRAPHICS, CONCEPT),
}

# Styles that pull the whole video toward one visual language.
STYLE_BIAS: Dict[str, Tuple[str, ...]] = {
    "whiteboard": (WHITEBOARD,),
    "education": (WHITEBOARD, PROCESS),
    "technology": (DIAGRAM, UI_EXPLAINER),
    "marketing": (KINETIC_TYPOGRAPHY, INFOGRAPHIC),
    "finance": (STATISTICS, INFOGRAPHIC),
    "minimal": (KINETIC_TYPOGRAPHY, CONCEPT),
}


class VisualTypeSelector:
    def __init__(self, style: str = "professional"):
        self.style = style or "professional"

    def candidates(self, pattern: str) -> List[str]:
        base = list(PATTERN_TYPES.get(pattern, PATTERN_TYPES[P_KEYWORD]))
        for biased in STYLE_BIAS.get(self.style, ()):
            if biased in base:
                base.remove(biased)
                base.insert(0, biased)
        return base

    def select(self, opportunity: VisualOpportunity,
               chosen_types: Sequence[str] = (),
               total_planned: int = 0) -> str:
        """Pick a type, avoiding over-representation and back-to-back repeats.

        `chosen_types` is the storyboard so far, in order.
        """
        options = self.candidates(opportunity.pattern)
        if not options:
            return MOTION_GRAPHICS

        counts: Dict[str, int] = {}
        for t in chosen_types:
            counts[t] = counts.get(t, 0) + 1
        planned = max(total_planned, len(chosen_types) + 1)
        cap = max(1, int(config.MAX_TYPE_SHARE * planned + 0.999))
        previous = chosen_types[-1] if chosen_types else ""

        for option in options:
            if option == previous:
                continue                       # never twice in a row
            if counts.get(option, 0) >= cap:
                continue                       # over its diversity share
            return option
        # Every option is saturated: take the least-used one that is not a
        # direct repeat, rather than dropping a scene that deserves a visual.
        ranked = sorted(options, key=lambda o: (o == previous, counts.get(o, 0)))
        return ranked[0]
