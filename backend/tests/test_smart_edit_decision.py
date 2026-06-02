from app.processing.edit_decision_service import EditDecisionService
from app.processing.types import SilenceRange, Transcript, TranscriptSegment, Word


def _segment(start, words):
    ws = []
    t = start
    for token in words:
        ws.append(Word(token, t, t + 0.3, confidence=0.95))
        t += 0.34
    return TranscriptSegment(start=start, end=t, text=" ".join(words), words=ws)


def test_edit_decision_removes_near_duplicate_repeated_sentence():
    transcript = Transcript(
        language="fr",
        text="bonjour je presente mon projet bonjour je presente mon projet maintenant on avance",
        segments=[
            _segment(0.0, ["bonjour", "je", "presente", "mon", "projet"]),
            _segment(2.5, ["bonjour", "je", "presente", "mon", "projet"]),
            _segment(5.5, ["maintenant", "on", "avance"]),
        ],
    )

    edl = EditDecisionService(repetition_similarity_threshold=0.84).build_edl(
        source_path="source.mp4",
        transcript=transcript,
        silences=[],
        total_duration=8.0,
    )

    repeated = [c for c in edl.cuts if not c.keep and c.reason == "repetition"]
    assert repeated, edl.to_dict()
    assert repeated[0].source_start <= 2.55
    assert repeated[0].source_end >= 4.0
    assert edl.metadata["repetition_ranges_count"] == 1


def test_edit_decision_removes_low_confidence_bad_segments():
    transcript = Transcript(
        language="fr",
        text="bonne partie mauvaise transcription suite claire",
        segments=[
            TranscriptSegment(
                start=0.0,
                end=1.0,
                text="bonne partie",
                words=[Word("bonne", 0.0, 0.4, confidence=0.95), Word("partie", 0.4, 0.8, confidence=0.92)],
            ),
            TranscriptSegment(
                start=1.2,
                end=2.4,
                text="mauvaise transcription",
                words=[Word("mauvaise", 1.2, 1.6, confidence=0.18), Word("transcription", 1.6, 2.1, confidence=0.22)],
            ),
            TranscriptSegment(
                start=2.7,
                end=3.7,
                text="suite claire",
                words=[Word("suite", 2.7, 3.1, confidence=0.92), Word("claire", 3.1, 3.5, confidence=0.9)],
            ),
        ],
    )

    edl = EditDecisionService(low_confidence_threshold=0.35).build_edl(
        source_path="source.mp4",
        transcript=transcript,
        silences=[],
        total_duration=4.0,
    )

    weak = [c for c in edl.cuts if not c.keep and c.reason == "low_confidence"]
    assert weak, edl.to_dict()
    assert weak[0].source_start <= 1.25
    assert weak[0].source_end >= 2.1
    assert edl.metadata["low_confidence_ranges_count"] == 1


def test_edit_decision_combines_silence_and_smart_drop_ranges():
    transcript = Transcript(
        language="fr",
        text="on garde ceci puis on garde ceci final",
        segments=[
            _segment(0.0, ["on", "garde", "ceci"]),
            _segment(3.0, ["on", "garde", "ceci"]),
            _segment(6.0, ["final"]),
        ],
    )
    edl = EditDecisionService().build_edl(
        source_path="source.mp4",
        transcript=transcript,
        silences=[SilenceRange(1.2, 2.2)],
        total_duration=8.0,
    )

    reasons = {c.reason for c in edl.cuts if not c.keep}
    assert "silence" in reasons
    assert "repetition" in reasons
