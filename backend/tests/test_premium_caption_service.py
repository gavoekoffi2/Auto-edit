from app.processing.premium_caption_service import PremiumCaptionService
from app.processing.types import Transcript, TranscriptSegment, Word


def test_premium_caption_service_writes_centered_word_level_ass(tmp_path):
    transcript = Transcript(
        language="fr",
        text="AutoEdit fait un montage premium",
        segments=[
            TranscriptSegment(
                start=0.0,
                end=2.2,
                text="AutoEdit fait un montage premium",
                words=[
                    Word("AutoEdit", 0.00, 0.42),
                    Word("fait", 0.42, 0.76),
                    Word("un", 0.76, 1.02),
                    Word("montage", 1.02, 1.55),
                    Word("premium", 1.55, 2.08),
                ],
            )
        ],
    )

    out = tmp_path / "premium.ass"
    rendered = PremiumCaptionService().write_ass(transcript, str(out))

    assert rendered == str(out)
    content = out.read_text(encoding="utf-8")
    assert "Style: Premium" in content
    assert ",5,70,70," in content  # ASS alignment 5 = centered safe zone
    assert "\\fs108" in content  # active word pop sizing
    assert "&H002CF7FF" in content  # cyan active word highlight
    assert "BorderStyle=3" not in content
    assert "AUTOEDIT" in content
    assert "MONTAGE" in content
    assert content.count("Dialogue:") >= 5
