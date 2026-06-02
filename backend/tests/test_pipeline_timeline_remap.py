from app.processing.pipeline_v2 import _remap_transcript_to_edl
from app.processing.types import Cut, EditDecisionList, Transcript, TranscriptSegment, Word


def test_remap_transcript_to_edl_compacts_word_times_after_dropped_cuts():
    transcript = Transcript(
        language="fr",
        text="premier silence deuxième",
        segments=[
            TranscriptSegment(
                start=0.0,
                end=5.0,
                text="premier silence deuxième",
                words=[
                    Word("premier", 0.5, 1.0, confidence=0.9),
                    Word("silence", 2.2, 2.8, confidence=0.9),
                    Word("deuxième", 4.1, 4.6, confidence=0.9),
                ],
            )
        ],
    )
    edl = EditDecisionList(
        source_path="source.mp4",
        cuts=[
            Cut(0.0, 1.5, True, "keep"),
            Cut(1.5, 3.5, False, "silence"),
            Cut(3.5, 5.0, True, "keep"),
        ],
        total_kept_duration=3.0,
    )

    compact = _remap_transcript_to_edl(transcript, edl)
    words = compact.words

    assert [w.text for w in words] == ["premier", "deuxième"]
    assert round(words[0].start, 2) == 0.5
    assert round(words[1].start, 2) == 2.1
    assert round(words[1].end, 2) == 2.6
    assert compact.segments[0].start == words[0].start
    assert compact.segments[0].end == words[-1].end
