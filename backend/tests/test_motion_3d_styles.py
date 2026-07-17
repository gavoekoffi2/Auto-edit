"""Rendu 3D des illustrations motion design + rotation de style par vidéo.

Demande produit: fini le "dessin animé" 2D flat — chaque illustration doit
ressembler à une vraie animation 3D, ET le style doit CHANGER d'une vidéo à
l'autre (seed stable par transcript/job) pour que les montages ne se
ressemblent pas.
"""
from app.autoedit_engine import config as engine_config
from app.autoedit_engine import genimg


def test_every_style_template_is_3d_and_text_free():
    prefixes = engine_config.MOTION_STYLE_3D_PREFIXES
    assert len(prefixes) >= 4, "il faut plusieurs templates pour varier les vidéos"
    for p in prefixes:
        assert "3D" in p or "CGI" in p, p[:80]
        assert "NO text" in p and "NO words" in p, "l'image ne doit jamais contenir de texte"
        assert p.rstrip().endswith("Scene to illustrate:")
    # plus aucun style "flat 2D cartoon"
    assert "flat vector" not in engine_config.MOTION_STYLE_PREFIX
    assert "cartoon characters" not in engine_config.MOTION_STYLE_PREFIX


def test_style_selection_is_seeded_and_varies_across_videos():
    a = genimg.select_3d_style_prefix("video-transcript-A")
    b = genimg.select_3d_style_prefix("video-transcript-A")
    assert a == b, "même seed => même style (job reproductible)"
    seeds = [f"transcript-{i}" for i in range(24)]
    styles = {genimg.select_3d_style_prefix(s) for s in seeds}
    assert len(styles) >= 3, "des vidéos différentes doivent tourner sur plusieurs styles"
    # sans seed: style signature (index 0), jamais un crash
    assert genimg.select_3d_style_prefix(None) == engine_config.MOTION_STYLE_3D_PREFIXES[0]
    assert genimg.select_3d_style_prefix("") == engine_config.MOTION_STYLE_3D_PREFIXES[0]
