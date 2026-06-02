from app.processing.smart_cuts import detect_repeated_segments, subtract_ranges, SmartCutRange


def test_detect_repeated_segments_drops_later_near_duplicate_take():
    transcription = {
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Vous êtes immigrant francophone au Canada"},
            {"start": 2.5, "end": 4.5, "text": "Vous êtes immigrant francophone au Canada"},
            {"start": 5.0, "end": 7.0, "text": "Ce message est pour vous"},
        ]
    }

    drops = detect_repeated_segments(transcription)

    assert len(drops) == 1
    assert drops[0].start == 2.5
    assert drops[0].reason == "repetition"


def test_subtract_ranges_keeps_non_dropped_timeline():
    keeps = subtract_ranges(
        10.0,
        [SmartCutRange(start=2.0, end=4.0, reason="repetition")],
        pad=0.0,
    )

    assert keeps == [(0.0, 2.0), (4.0, 10.0)]
