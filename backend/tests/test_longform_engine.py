"""Tests du moteur « YouTube long » (app/processing/longform)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import wave

import numpy as np
import pytest

from app.processing.longform import LONGFORM_MODES, chapters, graphics, render, styles, takes


def _w(text, start, end):
    return {"word": text, "start": start, "end": end}


def _vu(words):
    return {"language": "fr", "duration": words[-1]["end"] + 0.5,
            "segments": [{"text": "", "start": words[0]["start"], "end": words[-1]["end"],
                          "words": words}]}


def _seq(texts, t0=0.0, gap=0.05, dur=0.3):
    out, t = [], t0
    for x in texts:
        out.append(_w(x, round(t, 3), round(t + dur, 3)))
        t += dur + gap
    return out, t


# --------------------------------------------------------------------------- #
# Coupe de la voix
# --------------------------------------------------------------------------- #
def test_last_take_wins_false_start():
    a, t = _seq("aujourd'hui je vais vous".split())
    b, t = _seq("aujourd'hui je vais vous montrer la méthode".split(), t0=t + 1.2)
    ranges, rep = takes.build_ranges(_vu(a + b))
    text = " ".join(r["text"] for r in ranges)
    assert text == "aujourd'hui je vais vous montrer la méthode"
    assert rep["removed_counts"].get("faux_depart") == 1
    assert ranges[0]["start"] >= b[0]["start"] - 0.2


def test_distant_repeat_keeps_the_later_take():
    s1, t = _seq("le prix est de cinq cents euros par mois".split())
    mid, t = _seq("attendez je regarde mes notes rapidement ici".split(), t0=t + 1.0)
    s2, t = _seq("le prix est de cinq cents euros par mois".split(), t0=t + 1.0)
    ranges, rep = takes.build_ranges(_vu(s1 + mid + s2))
    assert rep["removed_counts"].get("phrase_repetee") == 1
    assert ranges[-1]["text"] == "le prix est de cinq cents euros par mois"
    assert ranges[0]["start"] >= mid[0]["start"] - 0.2


def test_stutter_filler_and_retake_marker():
    a, t = _seq("il faut il faut tester chaque semaine".split(), dur=0.3, gap=0.08)
    e, t = _seq(["euh"], t0=t + 0.8)
    m, t = _seq("et ensuite non je reprends".split(), t0=t + 0.8)
    ranges, rep = takes.build_ranges(_vu(a + e + m))
    text = " ".join(r["text"] for r in ranges)
    assert "il faut il faut" not in text and "il faut tester" in text
    assert "euh" not in text.split()
    assert "reprends" not in text
    c = rep["removed_counts"]
    assert c.get("begaiement") == 1 and c.get("tic_de_langage") == 1 and c.get("marqueur_reprise") == 1


def test_silences_are_capped_at_joins():
    a, t = _seq("première phrase complète ici".split())
    b, _ = _seq("deuxième phrase après une longue pause".split(), t0=t + 3.0)
    ranges, rep = takes.build_ranges(_vu(a + b))
    kept = sum(r["end"] - r["start"] for r in ranges)
    spoken = (a[-1]["end"] - a[0]["start"]) + (b[-1]["end"] - b[0]["start"])
    assert kept - spoken <= 0.45          # air naturel, jamais les 3 s de pause
    assert rep["removed_duration"] > 2.5


def test_micro_fragment_is_attached_to_neighbour():
    a, t = _seq("voici la première idée importante".split())
    f, t = _seq(["donc"], t0=t + 0.45, dur=0.25)     # tic seul : retiré
    g, t = _seq(["mais"], t0=t + 0.45, dur=0.25)
    b, _ = _seq("la suite arrive maintenant".split(), t0=t + 0.45)
    ranges, rep = takes.build_ranges(_vu(a + f + g + b))
    assert all(r["end"] - r["start"] >= takes.TakeConfig().min_fragment for r in ranges)
    assert rep["micro_fragments"] == []


def test_cut_points_snap_to_energy_trough():
    words, t = _seq("un deux".split(), dur=0.3, gap=0.5)
    rms = np.ones(int(2.0 / takes.Envelope.HOP), np.float32)
    trough = 0.55
    rms[int(trough / takes.Envelope.HOP)] = 0.0
    env = takes.Envelope(rms)
    lo, hi = words[0]["end"], words[1]["start"]
    assert abs(env.trough(lo, hi) - (trough + 0.005)) < 0.011


# --------------------------------------------------------------------------- #
# Timeline exacte
# --------------------------------------------------------------------------- #
def test_timeline_has_no_rounding_drift():
    ranges = [{"start": i * 1.7, "end": i * 1.7 + 0.8123} for i in range(500)]
    tl = render.Timeline(ranges)
    assert tl.total_samples == sum(int(round(0.8123 * render.SR)) for _ in range(500))
    assert tl.n_frames == int(np.ceil(tl.total_samples / render.SR * render.FPS - 1e-9))
    last = tl.items[-1]
    assert abs(tl.s2o(last.start + 0.1) - (last.out_start + 0.1)) < 1e-9
    assert tl.s2o(1.0) is None                      # dans une coupe


# --------------------------------------------------------------------------- #
# Chapitres
# --------------------------------------------------------------------------- #
def _topic_words(topics, per_topic_s=150.0):
    out, t = [], 0.0
    for vocab in topics:
        end = t + per_topic_s
        i = 0
        while t < end:
            w = vocab[i % len(vocab)]
            out.append({"word": w + ("." if i % 9 == 8 else ""), "start": t, "end": t + 0.3})
            t += 0.4
            i += 1
    return out, t


def test_chapters_follow_topics_and_youtube_rules():
    topics = [
        "bienvenue vidéo aujourd'hui chaîne abonnez apprendre ensemble".split(),
        "prix tarif euros abonnement mensuel paiement facture coût".split(),
        "livraison colis transport délai expédition commande adresse".split(),
        "marketing publicité facebook audience ciblage campagne budget".split(),
    ]
    words, dur = _topic_words(topics)
    res = chapters.build_chapters(words, dur, use_llm=False)
    ch = res["chapters"]
    assert ch[0]["start"] == 0.0 and ch[0]["title"] == "Introduction"
    assert res["youtube_valid"]
    starts = [c["start"] for c in ch[1:]]
    for expected in (150.0, 300.0, 450.0):
        assert min(abs(s - expected) for s in starts) < 20.0
    assert res["text"].splitlines()[0] == "00:00 Introduction"


def test_short_video_has_single_chapter():
    words, dur = _topic_words([["bonjour", "tout", "le", "monde"]], per_topic_s=40)
    res = chapters.build_chapters(words, dur, use_llm=False)
    assert len(res["chapters"]) == 1 and not res["youtube_valid"]


# --------------------------------------------------------------------------- #
# Styles & habillage
# --------------------------------------------------------------------------- #
def test_auto_style_varies_between_videos():
    picked = {styles.resolve_style("auto", seed).id for seed in range(12)}
    assert len(picked) == len(styles.AUTO_POOL)
    assert styles.resolve_style("documentaire", 3).id == "documentaire"


def test_ass_contains_captions_popups_cards_and_sfx():
    words, dur = _seq(("le prix est de 500 euros et c'est vraiment important pour vous "
                       "maintenant passons à la suite de la méthode ").split() * 12, t0=0.5)
    chs = [{"start": 0.0, "title": "Introduction"}, {"start": 20.0, "title": "La méthode"}]
    for sid, st in styles.STYLES.items():
        ass, cues, stats = graphics.build_ass(words, chs, st, dur, seed=1)
        assert "PlayResX: 1920" in ass and "Style: Caption" in ass
        assert stats["chapter_cards"] == 1 and "La méthode" in ass
        assert stats["keyword_popups"] >= 1 and stats["popups"][0] == "500 euros"
        kinds = {c["kind"] for c in cues}
        assert {"caption", "chapter", "popup"} <= kinds
        # jamais de popup pendant une carte chapitre
        for c in cues:
            if c["kind"] == "popup":
                assert not (19.0 <= c["t"] <= 20.0 + graphics.CARD_S + 1.0)


def test_numbers_come_from_speech_only():
    words, _ = _seq("nous avons trois clients et 20 % de croissance".split(), t0=4.0)
    picks = graphics.find_keywords(words, [], every=1.0)
    texts = [p["text"] for p in picks]
    assert "trois clients" in texts and "20 %" in texts


def test_modes_are_registered():
    from app.api.v1.modes import MODE_DEFINITIONS, FAMILIES
    from app.config import VALID_MODES
    from app.processing.pipeline_v2 import V2_MODE_PRESETS
    ids = {m["id"] for m in MODE_DEFINITIONS}
    for m in LONGFORM_MODES:
        assert m in ids and m in VALID_MODES and m in V2_MODE_PRESETS
    assert any(f["id"] == "longform" for f in FAMILIES)
    lf = [m for m in MODE_DEFINITIONS if m["id"] in LONGFORM_MODES]
    assert all(m["family"] == "longform" and m["defaults"]["vertical_9_16"] is False for m in lf)


def test_job_options_accept_longform_style():
    from app.schemas.job import JobOptions
    assert JobOptions(longform_style="tech_minimal").longform_style == "tech_minimal"
    with pytest.raises(ValueError):
        JobOptions(longform_style="inconnu")


# --------------------------------------------------------------------------- #
# Bout en bout (ffmpeg requis) : coupe + synchro prouvée par flashs/bips
# --------------------------------------------------------------------------- #
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")


def _onsets(b):
    return [i for i in range(1, len(b)) if b[i] and not b[i - 1]]


@needs_ffmpeg
@pytest.mark.parametrize("vertical", [False, True])
def test_end_to_end_cut_and_sync(tmp_path, vertical):
    from tests import longform_fixture as fx
    from app.processing.longform.pipeline import run_longform

    video, vu = fx.make(str(tmp_path), vertical=vertical)
    res = run_longform(video, str(tmp_path / "out"), mode="youtube_long",
                       options={"transcript_vu": vu, "longform_style": "studio_clean",
                                "keep_intermediates": True, "llm_titles": False})
    lf = res["longform"]
    assert res["steps_failed"] == []
    assert lf["checks"]["sync_ok"] and lf["checks"]["loudness_ok"]
    assert set(lf["cut"]["removed_counts"]) >= {"faux_depart", "begaiement", "tic_de_langage"}
    assert os.path.exists(res["output_path"])
    assert (tmp_path / "out" / "chapitres.txt").exists()
    report = json.load(open(tmp_path / "out" / "rapport_montage.json"))
    assert report["longform"]["timeline"]

    # Synchro : chaque bip (voix montée) doit tomber sur un flash (image montée).
    W, H = 96, 54
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i",
                                   str(tmp_path / "out/longform/video.mp4"),
                                   "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "pipe:1"])
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
    # centre-haut: loin des sous-titres (bas) et des popups (haut-droite)
    vid = fr[:, 12:26, 30:60].mean((1, 2)) > 200
    with wave.open(str(tmp_path / "out/longform/voice.wav")) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    hop = render.SR // render.FPS
    n = len(x) // hop
    e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1))
    aud = e > e.max() * 0.3
    ve, ae = _onsets(vid), _onsets(aud)
    assert len(ae) >= 30 and len(ve) >= 30
    offsets = [min(ve, key=lambda v: abs(v - a)) - a for a in ae]
    assert max(abs(o) for o in offsets) <= 1       # ≤ 1 image partout, début comme fin


@needs_ffmpeg
def test_delayed_audio_start_is_compensated(tmp_path):
    """Audio qui démarre après l'image dans le conteneur (.mov / téléphone)."""
    from tests import longform_fixture as fx
    video, _ = fx.make(str(tmp_path))
    a = tmp_path / "a.m4a"
    real = tmp_path / "real.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn",
                    "-af", "atrim=start=0.4,asetpts=N/SR/TB", "-c:a", "aac", str(a)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-itsoffset", "0.4", "-i", str(a),
                    "-map", "0:v", "-map", "1:a", "-c", "copy", str(real)], check=True)
    info = render.probe_video(str(real))
    assert 0.3 < info.video_offset < 0.45
    assert render.probe_video(video).video_offset < 0.05
