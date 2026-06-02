from app.processing.edit_decision_service import EditDecisionService
from app.processing.types import (
    SilenceRange,
    Transcript,
    TranscriptSegment,
    Word,
)


def _make_transcript(words: list[tuple[str, float, float]]) -> Transcript:
    return Transcript(
        language="fr",
        text=" ".join(w[0] for w in words),
        segments=[
            TranscriptSegment(
                start=words[0][1],
                end=words[-1][2],
                text=" ".join(w[0] for w in words),
                words=[Word(text=w[0], start=w[1], end=w[2]) for w in words],
            )
        ],
    )


def test_passthrough_when_no_words():
    eds = EditDecisionService()
    edl = eds.build_edl(
        "/tmp/x.mp4",
        Transcript(language="fr", text="", segments=[]),
        [],
        total_duration=10.0,
    )
    assert len(edl.cuts) == 1
    assert edl.cuts[0].keep is True
    assert edl.total_kept_duration == 10.0


def test_filler_words_french_are_cut():
    transcript = _make_transcript([
        ("euh", 0.0, 0.3),
        ("donc", 0.3, 0.7),
        ("je", 0.7, 0.9),
        ("vais", 0.9, 1.3),
        ("parler", 1.3, 1.9),
    ])
    edl = EditDecisionService().build_edl("/tmp/x.mp4", transcript, [], total_duration=2.0)
    # 2 cuts: 1 drop (filler) + 1 keep
    assert len(edl.cuts) == 2
    assert edl.cuts[0].keep is False
    assert edl.cuts[0].reason == "filler_word"
    assert edl.cuts[1].keep is True
    assert edl.total_kept_duration > 0


def test_long_silences_inside_a_kept_block_are_dropped():
    # "Bonjour ... [silence] ... aujourd'hui"
    transcript = _make_transcript([
        ("Bonjour", 0.0, 0.6),
        ("aujourd'hui", 3.0, 3.8),
    ])
    silences = [SilenceRange(start=0.7, end=2.9, reason="silence")]
    edl = EditDecisionService(max_silence_keep=0.3).build_edl(
        "/tmp/x.mp4", transcript, silences, total_duration=4.0,
    )
    assert any(c.reason == "silence" and not c.keep for c in edl.cuts)
    # kept must be split into 2 keep cuts around the silence
    keep_count = sum(1 for c in edl.cuts if c.keep)
    assert keep_count >= 2
