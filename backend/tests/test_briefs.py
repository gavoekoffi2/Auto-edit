from app.api.v1.briefs import BriefPreviewRequest, build_storyboard


def test_direct_response_brief_builds_ad_storyboard():
    result = build_storyboard(BriefPreviewRequest(
        description="Les boutiques perdent du temps à répondre aux clients. Notre outil automatise les relances et augmente les ventes.",
        brand_name="Kora Shop",
        audience="e-commerçants",
        offer="un assistant WhatsApp pour vendre plus",
        proof="Déjà utilisé par 120 boutiques",
        cta="Teste Kora Shop",
    ))

    assert result.template_id == "direct_response"
    assert result.format == "9:16"
    assert len(result.scenes) == 6
    assert [scene.role for scene in result.scenes] == ["hook", "problem", "promise", "proof", "offer", "cta"]
    assert result.scenes[-1].text_overlay == "Teste Kora Shop"
    assert result.scenes[-1].end_s == 45
    assert result.render_plan["motion_design"] is True
    assert result.render_plan["ai_broll"] is True
    assert result.warnings == []


def test_facecam_brief_warns_when_proof_is_missing():
    result = build_storyboard(BriefPreviewRequest(
        description="J’aide les créateurs à publier plus vite avec une méthode simple.",
        template_id="facecam_editorial",
        audience="créateurs de contenu",
        cta="Commence maintenant",
    ))

    assert result.title.startswith("Face caméra éditorial")
    assert result.render_plan["remove_silence"] is True
    assert result.render_plan["captions"] is True
    assert result.warnings
    assert result.scenes[0].narration.startswith("J’aide")
