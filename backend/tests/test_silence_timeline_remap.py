from app.processing.silence import build_kept_ranges, remap_transcription_to_kept_ranges


def test_build_kept_ranges_maps_source_to_compacted_timeline():
    kept = build_kept_ranges(
        10.0,
        [
            {"start": 2.0, "end": 4.0},
            {"start": 7.0, "end": 8.0},
        ],
        margin="0s",
    )

    assert kept == [
        {"source_start": 0.0, "source_end": 2.0, "output_start": 0.0, "output_end": 2.0},
        {"source_start": 4.0, "source_end": 7.0, "output_start": 2.0, "output_end": 5.0},
        {"source_start": 8.0, "source_end": 10.0, "output_start": 5.0, "output_end": 7.0},
    ]


def test_remap_transcription_clips_segments_across_removed_silence():
    transcription = {
        "segments": [
            {"start": 1.0, "end": 2.5, "text": "avant silence"},
            {"start": 4.5, "end": 6.0, "text": "apres silence"},
        ]
    }
    kept = [
        {"source_start": 0.0, "source_end": 2.0, "output_start": 0.0, "output_end": 2.0},
        {"source_start": 4.0, "source_end": 10.0, "output_start": 2.0, "output_end": 8.0},
    ]

    remapped = remap_transcription_to_kept_ranges(transcription, kept)

    assert remapped["segments"] == [
        {"start": 1.0, "end": 2.0, "text": "avant silence"},
        {"start": 2.5, "end": 4.0, "text": "apres silence"},
    ]
    assert transcription["segments"][1]["start"] == 4.5
