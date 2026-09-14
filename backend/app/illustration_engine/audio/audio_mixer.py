"""AudioMixer — voice first, then SFX, then music.

Priority is enforced with real gain staging, not by hoping the levels work out:

* the music is side-chained to the voice, so it steps back whenever the person
  is speaking and comes back up in the gaps;
* the illustration SFX are side-chained to the voice too, at a gentler ratio,
  so a pop never lands on top of a word;
* the whole bed is normalised to a broadcast target at the end.

`build_filter` is a pure function so the graph can be asserted in tests without
ffmpeg present.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .. import config


@dataclass
class SFXPlacement:
    """One sound, at an absolute time on the montage timeline."""
    path: str
    at: float
    gain: float = 1.0


def _db_to_linear(db: float) -> float:
    return round(10.0 ** (db / 20.0), 4)


def build_filter(sfx: Sequence[SFXPlacement], has_music: bool,
                 music_duck_db: float = None, sfx_duck_db: float = None,
                 loudnorm_target: float = -14.0) -> Tuple[str, str]:
    """Return (filter_complex, output_label) for the mix.

    Input order is fixed by `mix()`: 0 = the montage (voice), 1 = music when
    present, then one input per SFX.
    """
    music_duck_db = config.MUSIC_DUCK_DB if music_duck_db is None else music_duck_db
    sfx_duck_db = config.SFX_DUCK_DB if sfx_duck_db is None else sfx_duck_db
    attack_ms = max(1, int(config.DUCK_ATTACK * 1000))
    release_ms = max(1, int(config.DUCK_RELEASE * 1000))

    parts: List[str] = []
    # The voice is split: one copy is the programme, the others key the
    # side-chains. A side-chain input can only be consumed once.
    keys_needed = 1 + (1 if has_music else 0) + (1 if sfx else 0)
    parts.append(f"[0:a]asplit={keys_needed}" +
                 "".join(f"[voice{i}]" for i in range(keys_needed)))

    mix_labels = ["[voice0]"]
    key_index = 1

    if has_music:
        parts.append(
            f"[1:a]volume={_db_to_linear(music_duck_db)}[musiclow]")
        parts.append(
            f"[musiclow][voice{key_index}]sidechaincompress="
            f"threshold=0.045:ratio=9:attack={attack_ms}:release={release_ms}"
            f":makeup=1[musicduck]")
        mix_labels.append("[musicduck]")
        key_index += 1

    if sfx:
        first_sfx_input = 2 if has_music else 1
        sfx_labels: List[str] = []
        for index, placement in enumerate(sfx):
            stream = first_sfx_input + index
            delay_ms = max(0, int(round(placement.at * 1000)))
            label = f"[sfx{index}]"
            parts.append(
                f"[{stream}:a]adelay={delay_ms}|{delay_ms},"
                f"volume={round(max(0.0, placement.gain), 4)}{label}")
            sfx_labels.append(label)
        parts.append("".join(sfx_labels) +
                     f"amix=inputs={len(sfx_labels)}:normalize=0:"
                     f"dropout_transition=0[sfxraw]")
        parts.append(
            f"[sfxraw][voice{key_index}]sidechaincompress="
            f"threshold=0.08:ratio=4:attack={attack_ms}:release={release_ms}"
            f":makeup=1[sfxduck]")
        mix_labels.append("[sfxduck]")

    parts.append("".join(mix_labels) +
                 f"amix=inputs={len(mix_labels)}:normalize=0:"
                 f"dropout_transition=0[premix]")
    parts.append(f"[premix]loudnorm=I={loudnorm_target}:TP=-1.5:LRA=11[aout]")
    return (";".join(parts), "[aout]")


class AudioMixer:
    def __init__(self, music_duck_db: float = None, sfx_duck_db: float = None,
                 loudnorm_target: float = -14.0):
        self.music_duck_db = music_duck_db
        self.sfx_duck_db = sfx_duck_db
        self.loudnorm_target = loudnorm_target

    def mix(self, video_path: str, out_path: str,
            sfx: Sequence[SFXPlacement] = (),
            music_path: Optional[str] = None,
            timeout: int = 1800) -> str:
        """Remux `video_path` with its ducked SFX and music bed.

        The video stream is copied: only the audio is rebuilt.
        """
        from ..timeline.encoder import ffmpeg_bin

        placements = [p for p in sfx if p.path and os.path.exists(p.path)]
        has_music = bool(music_path and os.path.exists(music_path))
        if not placements and not has_music:
            return video_path

        cmd = [ffmpeg_bin(), "-y", "-v", "error", "-i", video_path]
        if has_music:
            cmd += ["-i", music_path]
        for placement in placements:
            cmd += ["-i", placement.path]

        graph, out_label = build_filter(
            placements, has_music, self.music_duck_db, self.sfx_duck_db,
            self.loudnorm_target)
        cmd += ["-filter_complex", graph,
                "-map", "0:v", "-map", out_label,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", out_path]
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
        return out_path
