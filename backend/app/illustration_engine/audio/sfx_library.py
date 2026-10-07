"""SFX vocabulary of the illustration engine.

The mission's eleven semantic sounds are mapped onto CutForge's existing
**synthesised** library: every sample is generated numerically at render time
from numpy oscillators and noise, so there is no third-party audio asset, no
sample clearance, and nothing to license. See docs/SFX_LICENSES.md.

An operator may still drop their own WAV files into
`illustration_engine/assets_data/audio/sfx/<name>.wav`; those take precedence,
and the licence of anything placed there is the operator's responsibility.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional

# The mission's contextual vocabulary.
WHOOSH = "whoosh"
POP = "pop"
CLICK = "click"
MARKER = "marker"
PENCIL = "pencil"
WRITING = "writing"
TRANSITION = "transition"
IMPACT = "impact"
NOTIFICATION = "notification"
SUCCESS = "success"
SUBTLE_HIT = "subtle_hit"
RISER = "riser"
EXIT = "exit"

VOCABULARY = (WHOOSH, POP, CLICK, MARKER, PENCIL, WRITING, TRANSITION, IMPACT,
              NOTIFICATION, SUCCESS, SUBTLE_HIT, RISER, EXIT)

# Semantic name -> generator in the montage engine's synthesised library.
_SYNTH: Dict[str, str] = {
    WHOOSH: "whoosh",
    POP: "pop",
    CLICK: "click",
    MARKER: "pen_scribble",
    PENCIL: "pen_scribble",
    WRITING: "pen_scribble",
    TRANSITION: "transition",
    IMPACT: "cinematic_hit",
    NOTIFICATION: "digi_blip",
    SUCCESS: "chime",
    SUBTLE_HIT: "bass_hit",
    RISER: "riser",
    EXIT: "swoosh_down",
}

# Per-sound level so a pencil never sits on top of the voice.
GAINS: Dict[str, float] = {
    WHOOSH: 0.52, POP: 0.60, CLICK: 0.42, MARKER: 0.38, PENCIL: 0.38,
    WRITING: 0.38, TRANSITION: 0.58, IMPACT: 0.66, NOTIFICATION: 0.46,
    SUCCESS: 0.54, SUBTLE_HIT: 0.44, RISER: 0.50, EXIT: 0.50,
}

_LOCAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets_data", "audio", "sfx")


def local_override(name: str) -> Optional[str]:
    """An operator-supplied WAV for this sound, if one exists."""
    path = os.path.join(_LOCAL_DIR, f"{name}.wav")
    return path if os.path.exists(path) else None


def synth_name(name: str) -> str:
    """The synthesised generator backing a semantic sound."""
    return _SYNTH.get(name, _SYNTH[POP])


def generate(name: str, out_dir: str) -> Optional[str]:
    """Materialise one sound as a WAV. Returns None if it cannot be produced."""
    override = local_override(name)
    if override:
        return override
    try:
        from ...autoedit_engine import sfx_lib
    except Exception as exc:  # noqa: BLE001 - SFX are never worth failing a job
        print(f"[illustration_engine] WARN bibliothèque SFX indisponible: {exc}",
              file=sys.stderr)
        return None
    os.makedirs(out_dir, exist_ok=True)
    try:
        return sfx_lib.generate(synth_name(name), out_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"[illustration_engine] WARN SFX '{name}' non généré: {exc}",
              file=sys.stderr)
        return None


def build(names: List[str], out_dir: str) -> Dict[str, str]:
    """Materialise the sounds actually used by a job. Missing ones are skipped."""
    built: Dict[str, str] = {}
    for name in sorted(set(names)):
        path = generate(name, out_dir)
        if path:
            built[name] = path
    return built
