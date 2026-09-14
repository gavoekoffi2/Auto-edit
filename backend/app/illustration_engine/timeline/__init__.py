"""Scene timing, synchronisation and compositing."""
from .encoder import ClipWriter, ffmpeg_bin
from .synchronization import (
    source_to_output, output_duration, place_scene, resolve_overlaps,
    narration_weights,
)
from .scene_timeline import build_timeline, to_output_overlays, write_manifest
from .compositor import Compositor, composite_illustrations, build_batch_filter

__all__ = [
    "ClipWriter", "ffmpeg_bin", "source_to_output", "output_duration",
    "place_scene", "resolve_overlaps", "narration_weights", "build_timeline",
    "to_output_overlays", "write_manifest", "Compositor",
    "composite_illustrations", "build_batch_filter",
]
