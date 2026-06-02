"""Types partagés du pipeline V2 (dataclasses immuables).

On évite les dépendances externes (pydantic, etc.) pour rester utilisables
depuis Celery sans coût d'import. Sérialisation JSON via `to_dict`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
@dataclass
class Word:
    text: str
    start: float
    end: float
    confidence: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
        }


@dataclass
class Transcript:
    language: str
    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "text": self.text,
            "segments": [s.to_dict() for s in self.segments],
        }

    @property
    def words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]


# ---------------------------------------------------------------------------
# Silence detection
# ---------------------------------------------------------------------------
@dataclass
class SilenceRange:
    start: float
    end: float
    reason: str = "silence"  # silence | noise | filler_word

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Edit decision list
# ---------------------------------------------------------------------------
@dataclass
class Cut:
    source_start: float
    source_end: float
    keep: bool
    reason: str = "keep"  # keep | silence | filler_word | weak
    text: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EditDecisionList:
    source_path: str
    cuts: list[Cut] = field(default_factory=list)
    total_kept_duration: float = 0.0
    metadata: dict = field(default_factory=dict)

    def kept_cuts(self) -> list[Cut]:
        return [c for c in self.cuts if c.keep]

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "total_kept_duration": self.total_kept_duration,
            "cuts": [c.to_dict() for c in self.cuts],
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# B-roll
# ---------------------------------------------------------------------------
@dataclass
class BrollCue:
    segment_start: float
    segment_end: float
    prompt: str
    style: str = "african_business_premium"
    aspect_ratio: str = "9:16"
    priority: int = 3
    image_path: Optional[str] = None
    clip_path: Optional[str] = None
    failure_reason: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.segment_end - self.segment_start)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeneratedImage:
    bytes: Optional[bytes]
    url: Optional[str]
    mime_type: str
    provider: str
    model: str
    cost_estimate_usd: Optional[float]
    prompt: str

    def to_metadata(self) -> dict:
        # Note: ne jamais sérialiser les bytes en JSON.
        return {
            "url": self.url,
            "mime_type": self.mime_type,
            "provider": self.provider,
            "model": self.model,
            "cost_estimate_usd": self.cost_estimate_usd,
            "prompt": self.prompt,
        }


# ---------------------------------------------------------------------------
# Overlays / templates
# ---------------------------------------------------------------------------
@dataclass
class OverlayClip:
    kind: str           # intro_card | lower_third | cta | logo
    start: float
    end: float
    props: dict[str, Any] = field(default_factory=dict)
    clip_path: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
