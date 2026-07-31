"""Garde-fous d'échelle: un montage LONG doit produire des commandes ffmpeg
exécutables, pas des arguments que le noyau refuse.

Le bug corrigé ici est celui rapporté en production: « une vidéo un peu lourde,
le montage échoue ». La cause n'était pas la taille du fichier mais le NOMBRE de
coupes: chaque élément du filtergraph était généré par coupe / par cue / par
entrée, donc la commande ffmpeg grossissait linéairement avec la durée jusqu'à
dépasser des limites système (taille max d'UN argument, nombre d'entrées
ouvertes, mémoire d'`amix`). Ces tests fixent le contrat: coût BORNÉ.
"""
from __future__ import annotations

import pytest

from app.autoedit_engine import build_edl, config as engine_config, ffmpeg_utils
from app.autoedit_engine import smart_crop, video_dynamics
from app.autoedit_engine.mix_sfx import _build_filter


#: Limite du noyau Linux sur la taille d'UN argument (MAX_ARG_STRLEN = 32 pages).
KERNEL_MAX_ARG = 128 * 1024


def _ranges(n: int, dur: float = 2.4) -> list[dict]:
    return [{"start": i * (dur + 0.5), "end": i * (dur + 0.5) + dur} for i in range(n)]


# --------------------------------------------------------------------------- #
# 1. Expression de zoom
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n_ranges", [400, 900])
def test_zoom_expression_stays_under_kernel_arg_limit(n_ranges):
    """Une vidéo de 20-40 min ne doit pas produire un argument de 128 Ko."""
    expr = video_dynamics.build_zoom_expr(_ranges(n_ranges))
    assert len(expr) < KERNEL_MAX_ARG // 2


def test_zoom_expression_nesting_is_bounded():
    """Le parseur d'expressions de ffmpeg récurse: la profondeur doit être bornée."""
    expr = video_dynamics.build_zoom_expr(_ranges(600))
    assert expr.count("if(lt(") <= engine_config.MAX_ZOOM_SEGMENTS


def test_short_video_zoom_expression_is_unchanged():
    """Sous les plafonds, le rendu historique doit être STRICTEMENT préservé."""
    short = _ranges(12)
    expr = video_dynamics.build_zoom_expr(short)
    # Une transition `if` par coupe sauf la dernière (qui sert de défaut).
    assert expr.count("if(lt(") == len(short) - 1


def test_merge_ranges_preserves_total_output_duration():
    """Fusionner les coupes ne doit décaler AUCUN instant de la timeline."""
    src = _ranges(500)
    merged = video_dynamics._merge_ranges(src, engine_config.MAX_ZOOM_SEGMENTS)
    assert len(merged) <= engine_config.MAX_ZOOM_SEGMENTS
    total = lambda rs: sum(r["end"] - r["start"] for r in rs)  # noqa: E731
    assert total(merged) == pytest.approx(total(src), abs=1e-6)


def test_accent_terms_are_capped():
    """Des centaines d'accents = des centaines d'exp() évaluées par frame."""
    # 5 familles de termes plafonnés séparément: punch-zooms de base, accents de
    # moments clés, accents de lumière, et la pulsation `eq` (luma + gamma r/b).
    ceiling = engine_config.MAX_PUNCH_TERMS + 5 * engine_config.MAX_ACCENT_TERMS
    small = video_dynamics.build_vf(_ranges(300),
                                    flash_times=[i * 1.7 for i in range(600)],
                                    light_times=[i * 1.7 for i in range(600)],
                                    eq_light_times=[i * 1.7 for i in range(600)])
    huge = video_dynamics.build_vf(_ranges(1200),
                                   flash_times=[i * 0.9 for i in range(4000)],
                                   light_times=[i * 0.9 for i in range(4000)],
                                   eq_light_times=[i * 0.9 for i in range(4000)])
    assert small.count("exp(") <= ceiling
    # Le coût du filtre ne doit PAS croître avec la durée de la vidéo.
    assert huge.count("exp(") <= ceiling
    assert len(huge) < KERNEL_MAX_ARG // 2


def test_thin_keeps_first_and_spreads_evenly():
    kept = video_dynamics._thin(list(range(100)), 10)
    assert len(kept) == 10
    assert kept[0] == 0
    assert kept == sorted(kept)


# --------------------------------------------------------------------------- #
# 2. Mixage SFX
# --------------------------------------------------------------------------- #
def test_sfx_inputs_bounded_by_library_size_not_video_length():
    cues = [{"sfx": engine_config.SFX_NAMES[i % 5], "t": i * 1.3}
            for i in range(400)]
    index = {n: f"sfx/{n}.wav" for n in engine_config.SFX_NAMES}
    filt, inputs = _build_filter(cues, index)
    assert len(inputs) == 5                      # 400 cues, 5 sons distincts
    # Le graphe reste linéaire en nombre de cues, mais il part par fichier
    # (-filter_complex_script) au lieu d'être un argument: cf. filter_flag.
    assert ffmpeg_utils.filter_flag(filt, complex_graph=True)[0] in {
        "-filter_complex", "-filter_complex_script"}


def test_sfx_amix_fanin_is_bounded():
    """`amix` alloue un tampon par entrée: pas de fan-in illimité."""
    cues = [{"sfx": engine_config.SFX_NAMES[i % 5], "t": i * 1.3}
            for i in range(400)]
    index = {n: f"sfx/{n}.wav" for n in engine_config.SFX_NAMES}
    filt, _ = _build_filter(cues, index)
    fanins = [int(part.split("amix=inputs=")[1].split(":")[0])
              for part in filt.split(";") if "amix=inputs=" in part]
    assert fanins, "le graphe doit contenir au moins un amix"
    assert max(fanins) <= max(2, engine_config.SFX_MIX_BATCH)


def test_sfx_voice_defines_output_duration():
    """La voix reste la référence: un SFX tardif ne rallonge pas la piste."""
    cues = [{"sfx": engine_config.SFX_NAMES[i % 5], "t": i * 1.3}
            for i in range(400)]
    index = {n: f"sfx/{n}.wav" for n in engine_config.SFX_NAMES}
    filt, _ = _build_filter(cues, index)
    final = [p for p in filt.split(";") if p.startswith("[0:a]") and "amix" in p]
    assert final and "duration=first" in final[0]


# --------------------------------------------------------------------------- #
# 3. Concaténation des segments
# --------------------------------------------------------------------------- #
def test_concat_runs_in_bounded_batches(monkeypatch, tmp_path):
    """Aucune commande ffmpeg ne doit ouvrir des centaines d'entrées."""
    calls: list[int] = []

    def fake_run_filter(prefix, filter_str, suffix, **kwargs):
        calls.append(sum(1 for a in prefix if a == "-i"))
        # Matérialise la sortie attendue pour que la cascade continue.
        open(suffix[-1], "wb").write(b"x")

    monkeypatch.setattr(ffmpeg_utils, "ensure_ffmpeg", lambda: None)
    monkeypatch.setattr(ffmpeg_utils, "run_filter", fake_run_filter)

    segments = []
    for i in range(300):
        seg = tmp_path / f"seg_{i:04d}.mp4"
        seg.write_bytes(b"x")
        segments.append(str(seg))

    out = tmp_path / "base_only.mp4"
    build_edl.concat_segments(segments, str(out))
    assert calls, "la concaténation doit lancer au moins une passe"
    assert max(calls) <= engine_config.CONCAT_BATCH


def test_concat_single_pass_for_short_video(monkeypatch, tmp_path):
    calls: list[int] = []
    monkeypatch.setattr(ffmpeg_utils, "ensure_ffmpeg", lambda: None)
    monkeypatch.setattr(
        ffmpeg_utils, "run_filter",
        lambda prefix, f, suffix, **kw: calls.append(
            sum(1 for a in prefix if a == "-i")))
    segments = [str(tmp_path / f"seg_{i}.mp4") for i in range(8)]
    build_edl.concat_segments(segments, str(tmp_path / "out.mp4"))
    assert calls == [8]                          # une seule passe, comme avant


# --------------------------------------------------------------------------- #
# 4. Passage du filtergraph par fichier
# --------------------------------------------------------------------------- #
def test_short_filter_stays_inline():
    flag, value, tmp = ffmpeg_utils.filter_flag("scale=2:2", complex_graph=False)
    assert (flag, value, tmp) == ("-vf", "scale=2:2", None)


def test_huge_filter_moves_to_a_script_file():
    huge = "x" * (ffmpeg_utils.FILTER_ARG_MAX + 10)
    flag, value, tmp = ffmpeg_utils.filter_flag(huge, complex_graph=True)
    try:
        assert flag == "-filter_complex_script"
        assert value == tmp
        with open(tmp, encoding="utf-8") as fh:
            assert fh.read() == huge
    finally:
        import os
        os.unlink(tmp)


def test_ffmpeg_calls_are_non_interactive():
    hardened = ffmpeg_utils._harden([ffmpeg_utils.FFMPEG, "-y", "-i", "a.mp4", "out.mp4"])
    assert "-nostdin" in hardened
    assert hardened[0] == ffmpeg_utils.FFMPEG
    # ffprobe n'accepte pas ces options: il ne doit pas être touché.
    assert ffmpeg_utils._harden([ffmpeg_utils.FFPROBE, "-i", "a.mp4"])[1] == "-i"


# --------------------------------------------------------------------------- #
# 5. Recadrage intelligent
# --------------------------------------------------------------------------- #
def test_smart_crop_analysis_is_capped():
    idx = smart_crop.sampled_indices(400, 60)
    assert len(idx) <= 60
    assert idx[0] == 0 and idx == sorted(idx) and len(set(idx)) == len(idx)


def test_smart_crop_analyses_every_segment_when_short():
    assert smart_crop.sampled_indices(12, 60) == list(range(12))


# --------------------------------------------------------------------------- #
# 6. Préflight disque
# --------------------------------------------------------------------------- #
def test_disk_estimate_follows_duration_not_file_weight(tmp_path):
    """Une vidéo lourde mais COURTE ne doit plus être refusée à tort."""
    from app.processing.pipeline_v2 import estimate_render_disk_gb

    import os as _os

    heavy_short = tmp_path / "phone.mp4"
    heavy_short.write_bytes(b"0")
    # 4 Go de source pour 3 minutes: l'ancienne formule exigeait 16 Go libres et
    # refusait le rendu sur un serveur pourtant confortable.
    _os.truncate(heavy_short, 4_000_000_000)
    need = estimate_render_disk_gb(str(heavy_short), duration_s=180)
    assert need < 8.0
    # Et une vidéo longue en demande davantage.
    assert estimate_render_disk_gb(str(heavy_short), duration_s=3600) > need
