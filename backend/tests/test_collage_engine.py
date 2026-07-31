"""Moteur Collage Premium B-roll (`collage_assemble`).

Couvre les 7 étapes du moteur + son branchement:
  * routage automatique du type de B-roll (ÉTAPE 7);
  * planification sémantique LLM + repli heuristique (ÉTAPE 2);
  * verrou de style des prompts (ÉTAPE 3);
  * abstraction des fournisseurs d'images + cache (ÉTAPE 4);
  * animation `collage_assemble` : fond vide -> éléments posés un par un (5);
  * contrôle qualité automatique + relance ciblée (ÉTAPE 6);
  * intégration timeline sans casser les pipelines existants (ÉTAPE 9).

Aucun test ne touche le réseau ni ffmpeg.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.processing.broll_planner import (
    BrollPlanner,
    BrollPlannerConfig,
    BrollTypeRouter,
)
from app.processing.collage import collage_config as ccfg
from app.processing.collage.collage_cache import BinaryCache, JsonCache
from app.processing.collage.collage_concept_planner import CollageConceptPlanner
from app.processing.collage.collage_image_service import (
    CollageImageService,
    NoopCollageImageProvider,
    build_provider,
    register_provider,
    resolve_provider_name,
)
from app.processing.collage.collage_pipeline import CollagePipeline
from app.processing.collage.collage_prompt_builder import (
    NEGATIVE_PROMPT,
    STYLE_LOCK,
    CollagePromptBuilder,
)
from app.processing.collage.collage_quality_service import CollageQualityService
from app.processing.collage.collage_types import (
    LAYOUT_TEMPLATES,
    BrollType,
    CollageConcept,
    CollageObject,
    Emotion,
    QualityReport,
)
from app.processing.collage.collage_video_service import (
    PIECE_SPREAD,
    CollageVideoService,
    LocalAssembleRenderer,
)
from app.processing.types import (
    Cut,
    EditDecisionList,
    GeneratedImage,
    Transcript,
    TranscriptSegment,
    Word,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _concept(n_objects: int = 4, cid: str = "cg_000") -> CollageConcept:
    palette = ["#F7F1E3", "#1D1D1B", "#F2B705", "#2E5EAA", "#1B4D3E", "#D94F70"]
    return CollageConcept(
        id=cid,
        source_start=4.0,
        source_end=8.0,
        excerpt="la confiance se construit une brique à la fois",
        meaning="la confiance se gagne progressivement",
        emotion=Emotion.TRUST,
        metaphor="a wall built one brick at a time",
        objects=[
            CollageObject(name=f"brick {i}", order=i + 1,
                          anchor="center", paper_color=palette[i % len(palette)])
            for i in range(n_objects)
        ],
        background_color="#E8452C",
        palette=palette[:3],
        label="CONFIANCE",
    )


def _seg(start, end, text, words):
    return TranscriptSegment(
        start=start, end=end, text=text,
        words=[Word(text=t, start=s, end=e) for (t, s, e) in words],
    )


def _flat_collage_image(path: str, size=(360, 640)) -> str:
    """Image de collage « propre »: aplats sur palette, zéro typographie."""
    img = Image.new("RGB", size, (232, 69, 44))
    d = ImageDraw.Draw(img)
    d.ellipse((60, 60, 300, 300), fill=(247, 241, 227))
    d.rounded_rectangle((70, 360, 290, 560), radius=24, fill=(29, 29, 27))
    d.rectangle((120, 320, 240, 350), fill=(242, 183, 5))
    img.save(path)
    return path


def _text_image(path: str, size=(360, 640)) -> str:
    """Image saturée de lettrage — doit être rejetée par le contrôle qualité."""
    img = Image.new("RGB", size, (232, 69, 44))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=26)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    for row in range(6):
        d.text((12, 80 + row * 44), "ABCDEFGH IJKLMNOP QRSTU",
               fill=(255, 255, 255), font=font)
    img.save(path)
    return path


class _StubProvider:
    """Fournisseur d'images déterministe (aucun réseau)."""

    name = "stub"

    def __init__(self, payload: bytes, fail_first: int = 0):
        self.payload = payload
        self.calls = 0
        self.fail_first = fail_first

    def generate(self, prompt, *, aspect_ratio="9:16", negative_prompt="",
                 timeout_s=180):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise RuntimeError("provider timeout")
        return GeneratedImage(bytes=self.payload, url=None, mime_type="image/png",
                              provider=self.name, model="stub-1",
                              cost_estimate_usd=0.0, prompt=prompt)


# --------------------------------------------------------------------------- #
# ÉTAPE 7 — routage automatique
# --------------------------------------------------------------------------- #
def test_router_sends_abstract_ideas_to_collage():
    router = BrollTypeRouter()
    decision = router.choose(
        "la confiance c'est comme une clé : sans elle aucune porte ne s'ouvre")
    assert decision.broll_type is BrollType.COLLAGE_PREMIUM
    assert "métaphore" in decision.reason


def test_router_sends_enumerations_to_motion_design():
    router = BrollTypeRouter()
    decision = router.choose(
        "premièrement tu ouvres ton compte, deuxièmement tu verses 5000 francs, "
        "troisièmement tu valides")
    assert decision.broll_type is BrollType.MOTION_DESIGN


def test_router_sends_concrete_scenes_to_static_image():
    router = BrollTypeRouter()
    decision = router.choose(
        "le client paie en mobile money dans la boutique de Lomé")
    assert decision.broll_type is BrollType.STATIC_IMAGE


def test_router_respects_the_collage_budget():
    """Le collage coûte cher: au-delà du quota, on retombe sur l'image."""
    router = BrollTypeRouter(collage_share=0.25)
    texts = ["c'est comme une porte fermée, une idée de liberté"] * 8
    decisions = router.route_many(texts)
    collage = [d for d in decisions if d.broll_type is BrollType.COLLAGE_PREMIUM]
    assert len(collage) == 2                       # 25 % de 8
    assert any(d.reason == "collage_budget_exhausted" for d in decisions)


def test_router_only_returns_enabled_families():
    router = BrollTypeRouter(enabled=[BrollType.STATIC_IMAGE])
    assert router.choose("une idée abstraite de liberté").broll_type is (
        BrollType.STATIC_IMAGE)


# --------------------------------------------------------------------------- #
# ÉTAPE 7 — le planner V2 porte la décision, sans régression
# --------------------------------------------------------------------------- #
def _sample_transcript() -> tuple[Transcript, EditDecisionList]:
    transcript = Transcript(
        language="fr", text="",
        segments=[
            _seg(0.0, 4.0, "le client paie en mobile money dans la boutique", [
                ("le", 0.0, 0.2), ("client", 0.2, 0.8), ("paie", 0.8, 1.2),
                ("en", 1.2, 1.4), ("mobile", 1.4, 2.0), ("money", 2.0, 2.6),
            ]),
            _seg(4.0, 9.0, "la confiance c'est comme une clé qui ouvre une porte", [
                ("la", 4.0, 4.2), ("confiance", 4.2, 5.0), ("comme", 5.0, 5.5),
                ("une", 5.5, 5.7), ("clé", 5.7, 6.2),
            ]),
        ],
    )
    edl = EditDecisionList(source_path="/tmp/x.mp4",
                           cuts=[Cut(0.0, 9.0, keep=True, reason="keep")],
                           total_kept_duration=9.0)
    return transcript, edl


def test_planner_tags_each_cue_with_a_broll_type():
    transcript, edl = _sample_transcript()
    cues = BrollPlanner(BrollPlannerConfig(min_segment_duration=2.0, max_cues=5)).plan(
        transcript, edl)
    assert cues
    assert {c.broll_type for c in cues} <= {t.value for t in BrollType}
    assert all(c.excerpt for c in cues)
    assert any(c.broll_type == BrollType.COLLAGE_PREMIUM.value for c in cues)


def test_auto_routing_can_be_switched_off_for_legacy_behaviour():
    transcript, edl = _sample_transcript()
    cues = BrollPlanner(BrollPlannerConfig(min_segment_duration=2.0, max_cues=5,
                                           auto_broll_type=False)).plan(transcript, edl)
    assert cues
    assert all(c.broll_type == BrollType.STATIC_IMAGE.value for c in cues)


# --------------------------------------------------------------------------- #
# ÉTAPE 2 — planification sémantique
# --------------------------------------------------------------------------- #
def _beats() -> list[dict]:
    return [
        {"id": "cg_000", "source_start": 2.0, "source_end": 7.0,
         "text": "la confiance se construit lentement mais se perd en une seconde"},
        {"id": "cg_001", "source_start": 12.0, "source_end": 17.0,
         "text": "chaque erreur est une leçon si tu prends le temps de la lire"},
    ]


def test_heuristic_planner_produces_a_valid_structured_concept(tmp_path):
    planner = CollageConceptPlanner(api_key="", use_llm=False,
                                   cache=JsonCache("t", enabled=False))
    concepts = planner.plan(_beats())
    assert len(concepts) == 2
    for concept in concepts:
        assert ccfg.MIN_OBJECTS <= len(concept.objects) <= ccfg.MAX_OBJECTS
        assert concept.metaphor
        assert concept.emotion in set(Emotion)
        assert concept.background_color.startswith("#") and len(concept.background_color) == 7
        # L'ordre d'apparition est complet, sans trou ni doublon.
        assert [o.order for o in concept.ordered_objects()] == list(
            range(1, len(concept.objects) + 1))
        assert concept.sequence == [o.name for o in concept.ordered_objects()]
        assert concept.planner == "heuristic"
        # Sérialisable et re-lisible sans perte (contrat Celery / rapport job).
        assert CollageConcept.from_dict(
            json.loads(json.dumps(concept.to_dict()))).metaphor == concept.metaphor


def test_llm_planner_batches_every_beat_in_a_single_call(monkeypatch):
    """Le coût est le point dur: une vidéo = UN appel, pas un par phrase."""
    calls = {"n": 0}
    payload = [
        {"meaning": "m", "emotion": "trust", "metaphor": "a wall of bricks",
         "objects": [{"name": "brick", "order": 1}, {"name": "hand", "order": 2},
                     {"name": "wall", "order": 3}],
         "background_color": "#123456", "palette": ["#F7F1E3"], "label": "CONFIANCE"},
        {"meaning": "m2", "emotion": "hope", "metaphor": "a page turning",
         "objects": [{"name": "page", "order": 1}, {"name": "pen", "order": 2},
                     {"name": "lamp", "order": 3}],
         "background_color": "#654321", "palette": ["#F7F1E3"], "label": "LECON"},
    ]

    def _fake(prompt, *, model, api_key, timeout_s=60):
        calls["n"] += 1
        return "voici le résultat: " + json.dumps(payload)

    monkeypatch.setattr(
        "app.processing.collage.collage_concept_planner.chat_completion", _fake)
    planner = CollageConceptPlanner(api_key="k", use_llm=True,
                                   cache=JsonCache("t", enabled=False))
    concepts = planner.plan(_beats())
    assert calls["n"] == 1
    assert [c.planner for c in concepts] == ["llm", "llm"]
    assert concepts[0].background_color == "#123456"


def test_llm_answer_with_text_disguised_as_objects_is_rejected(monkeypatch):
    """Le style interdit toute typographie: un « objet » chiffré est refusé."""
    payload = [{"meaning": "m", "emotion": "trust", "metaphor": "a wall",
                "objects": [{"name": "the word \"trust\"", "order": 1},
                            {"name": "number 5", "order": 2}],
                "background_color": "#123456", "palette": [], "label": "X"}]
    monkeypatch.setattr(
        "app.processing.collage.collage_concept_planner.chat_completion",
        lambda *a, **k: json.dumps(payload))
    planner = CollageConceptPlanner(api_key="k", use_llm=True,
                                    cache=JsonCache("t", enabled=False))
    concept = planner.plan(_beats()[:1])[0]
    assert concept.planner == "heuristic"          # repli, pas de texte accepté


def test_planner_falls_back_when_the_llm_is_unreachable(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(
        "app.processing.collage.collage_concept_planner.chat_completion", _boom)
    planner = CollageConceptPlanner(api_key="k", use_llm=True,
                                    cache=JsonCache("t", enabled=False))
    concepts = planner.plan(_beats())
    assert len(concepts) == 2                      # jamais bloquant
    assert all(c.planner == "heuristic" for c in concepts)


def test_concept_cache_avoids_paying_twice_for_the_same_sentence(monkeypatch, tmp_path):
    calls = {"n": 0}
    payload = [{"meaning": "m", "emotion": "hope", "metaphor": "a rising staircase",
                "objects": [{"name": "step", "order": 1}, {"name": "foot", "order": 2},
                            {"name": "door", "order": 3}],
                "background_color": "#112233", "palette": [], "label": "MONTER"}]

    def _fake(prompt, *, model, api_key, timeout_s=60):
        calls["n"] += 1
        return json.dumps(payload)

    monkeypatch.setattr(
        "app.processing.collage.collage_concept_planner.chat_completion", _fake)
    cache = JsonCache("t", enabled=True, root=str(tmp_path))
    beats = _beats()[:1]
    CollageConceptPlanner(api_key="k", cache=cache).plan(beats)
    CollageConceptPlanner(api_key="k", cache=cache).plan(beats)
    assert calls["n"] == 1


# --------------------------------------------------------------------------- #
# ÉTAPE 3 — verrou de style
# --------------------------------------------------------------------------- #
def test_image_prompt_carries_the_locked_style_and_bans_typography():
    prompts = CollagePromptBuilder().build(_concept())
    text = prompts.image_prompt
    assert STYLE_LOCK.split(".")[0] in text
    for token in ("halftone", "cardstock", "cream keyline", "paper grain"):
        assert token in text.lower()
    for banned in ("NO text", "NO logo", "NO watermark"):
        assert banned in text
    assert prompts.negative_prompt == NEGATIVE_PROMPT
    assert prompts.style_lock_version == ccfg.STYLE_LOCK_VERSION


def test_image_prompt_places_every_object_in_a_known_layout_cell():
    concept = _concept(n_objects=5)
    text = CollagePromptBuilder().build_image_prompt(concept)
    for obj in concept.ordered_objects():
        assert obj.name in text
        assert obj.paper_color in text
    assert "Exactly 5 paper elements" in text


def test_video_prompt_describes_an_assembly_from_an_empty_field():
    text = CollagePromptBuilder().build_video_prompt(_concept())
    assert "STARTS on a completely empty background" in text
    assert "no camera movement" in text.lower()
    assert "one by one" in text.lower()


def test_retry_hints_are_injected_into_the_prompt():
    prompts = CollagePromptBuilder().build(
        _concept(), quality_hints=["remove every letter"])
    assert "Corrections required" in prompts.image_prompt
    assert "remove every letter" in prompts.image_prompt


def test_two_concepts_share_the_same_visual_identity():
    a = CollagePromptBuilder().build_image_prompt(_concept(cid="a"))
    b = CollagePromptBuilder().build_image_prompt(_concept(n_objects=6, cid="b"))
    assert STYLE_LOCK in a and STYLE_LOCK in b


# --------------------------------------------------------------------------- #
# ÉTAPE 4 — abstraction des fournisseurs
# --------------------------------------------------------------------------- #
def test_provider_registry_is_open_for_extension():
    class _Custom(NoopCollageImageProvider):
        name = "custom_vendor"

    register_provider("custom_vendor", _Custom)
    assert resolve_provider_name("custom_vendor") == "custom_vendor"
    assert build_provider("custom_vendor").name == "custom_vendor"


def test_unknown_provider_falls_back_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(ccfg, "IMAGE_PROVIDER", "does_not_exist")
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "also_missing")
    assert build_provider().name in {"noop", "openrouter"}


def test_broken_provider_never_breaks_the_render(monkeypatch):
    def _explode():
        raise RuntimeError("bad credentials")

    register_provider("broken_vendor", _explode)
    assert build_provider("broken_vendor").name == "noop"


def test_image_service_writes_the_asset_and_records_provenance(tmp_path):
    png = tmp_path / "src.png"
    _flat_collage_image(str(png))
    service = CollageImageService(provider=_StubProvider(png.read_bytes()),
                                  cache=BinaryCache("t", enabled=False))
    concept = _concept()
    asset = service.generate(concept, CollagePromptBuilder().build(concept),
                             str(tmp_path / "out"))
    assert asset.image_path and os.path.exists(asset.image_path)
    assert asset.provider == "stub" and asset.model == "stub-1"


def test_image_service_failure_is_reported_not_raised(tmp_path):
    service = CollageImageService(provider=_StubProvider(b"", fail_first=99),
                                  cache=BinaryCache("t", enabled=False))
    concept = _concept()
    asset = service.generate(concept, CollagePromptBuilder().build(concept),
                             str(tmp_path / "out"))
    assert asset.image_path is None
    assert asset.failure_reason


def test_image_cache_is_keyed_by_prompt_so_a_retry_never_serves_the_reject(tmp_path):
    png = tmp_path / "src.png"
    _flat_collage_image(str(png))
    provider = _StubProvider(png.read_bytes())
    service = CollageImageService(
        provider=provider, cache=BinaryCache("t", enabled=True, root=str(tmp_path)))
    concept = _concept()
    builder = CollagePromptBuilder()

    first = builder.build(concept)
    service.generate(concept, first, str(tmp_path / "out"), attempt=1)
    service.generate(concept, first, str(tmp_path / "out"), attempt=1)
    assert provider.calls == 1                      # 2e appel servi par le cache

    retry = builder.build(concept, quality_hints=["remove every letter"])
    service.generate(concept, retry, str(tmp_path / "out"), attempt=2)
    assert provider.calls == 2                      # prompt corrigé => vraie relance


# --------------------------------------------------------------------------- #
# ÉTAPE 5 — animation `collage_assemble`
# --------------------------------------------------------------------------- #
def _ai_image(renderer, concept) -> Image.Image:
    """Une image « générée » factice, pour exercer le chemin de découpe."""
    img = Image.new("RGBA", (renderer.width, renderer.height), (232, 69, 44, 255))
    draw = ImageDraw.Draw(img)
    for i, (x, y) in enumerate([(0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]):
        r = renderer.width * 0.14
        draw.ellipse((x * renderer.width - r, y * renderer.height - r,
                      x * renderer.width + r, y * renderer.height + r),
                     fill=(30 + i * 40, 200, 120, 255))
    return img


def test_ai_image_is_partitioned_one_piece_per_object():
    """Chemin « image générée »: la découpe suit les zones imposées au modèle."""
    renderer = LocalAssembleRenderer(width=180, height=320, fps=12)
    concept = _concept(n_objects=4)
    pieces = renderer._slice_pieces(concept, _ai_image(renderer, concept))
    assert len(pieces) == 4
    assert [p.order for p in pieces] == [1, 2, 3, 4]


def test_pieces_are_drawn_cutouts_when_no_image_was_generated():
    """Chemin des moteurs UGC: une pièce DESSINÉE par objet, aucune image IA."""
    renderer = LocalAssembleRenderer(width=180, height=320, fps=12)
    concept = _concept(n_objects=4)
    pieces = renderer._pictogram_pieces(concept)
    assert len(pieces) == 4
    assert [p.order for p in pieces] == [1, 2, 3, 4]
    # Chaque pièce est un vrai calque avec de la matière (pas un cadre vide).
    for piece in pieces:
        assert np.asarray(piece.layer.split()[3]).max() > 0


def test_drawn_pieces_do_not_overlap_in_any_layout_variant():
    """Des pièces qui se recouvrent rendent la scène illisible.

    On balaie TOUS les gabarits, pas seulement ceux qu'un concept d'exemple
    tirerait au sort: une variante mal calibrée ne doit pas pouvoir se glisser
    dans le jeu et n'apparaître qu'au montage d'un client.
    """
    renderer = LocalAssembleRenderer(width=1080, height=1920, fps=30)
    for n, variants in LAYOUT_TEMPLATES.items():
        for index, cells in enumerate(variants):
            boxes = []
            for (_, cx, cy, radius) in cells:
                size = radius * 1080 * PIECE_SPREAD + 2 * ccfg.SHADOW_OFFSET * 2
                boxes.append((cx * 1080 - size / 2, cy * 1920 - size / 2,
                              cx * 1080 + size / 2, cy * 1920 + size / 2))
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    overlap_x = min(a[2], b[2]) - max(a[0], b[0])
                    overlap_y = min(a[3], b[3]) - max(a[1], b[1])
                    area = max(0, overlap_x) * max(0, overlap_y)
                    smaller = min((a[2] - a[0]) * (a[3] - a[1]),
                                  (b[2] - b[0]) * (b[3] - b[1]))
                    # L'ombre portée déborde un peu: on tolère un chevauchement
                    # marginal, jamais un recouvrement de la forme.
                    assert area <= smaller * 0.12, (
                        f"{n} objets, variante {index}: pièces superposées")
    # Et le rendu réel respecte bien ce gabarit.
    assert len(renderer._pictogram_pieces(_concept(n_objects=5))) == 5


def test_layout_varies_between_scenes_but_stays_reproducible():
    """Sans variantes, toutes les scènes d'un montage ont la même composition."""
    layouts = {tuple(c[0] for c in _concept(n_objects=4, cid=f"cg_{i:03d}").layout())
               for i in range(12)}
    assert len(layouts) > 1, "aucune variété de composition entre les scènes"
    # Même scène = même gabarit, toujours (montage reproductible).
    once = _concept(n_objects=4, cid="cg_007").layout()
    assert once == _concept(n_objects=4, cid="cg_007").layout()


def test_clip_starts_empty_and_ends_assembled():
    """La promesse du mouvement: fond vide au départ, scène complète à la fin."""
    renderer = LocalAssembleRenderer(width=180, height=320, fps=12)
    concept = _concept(n_objects=4)
    background = renderer._background_plate(concept)
    pieces = renderer._pictogram_pieces(concept)

    first = renderer._compose(background, pieces, 0.0, 4.0)
    assert np.array_equal(np.asarray(first), np.asarray(background))

    def _ink(frame):
        diff = np.abs(np.asarray(frame, dtype=np.int16)
                      - np.asarray(background, dtype=np.int16)).sum()
        return int(diff)

    mid = _ink(renderer._compose(background, pieces, 1.4, 4.0))
    end = _ink(renderer._compose(background, pieces, 3.9, 4.0))
    assert 0 < mid < end                     # les éléments arrivent progressivement


def test_elements_appear_in_the_planned_order():
    renderer = LocalAssembleRenderer(width=180, height=320, fps=12)
    concept = _concept(n_objects=3)
    background = renderer._background_plate(concept)
    pieces = renderer._pictogram_pieces(concept)

    # Zone de la 1re pièce vs zone de la dernière, juste après la 1re pose.
    frame = np.asarray(renderer._compose(background, pieces, 0.9, 4.0), dtype=np.int16)
    plate = np.asarray(background, dtype=np.int16)
    changed = np.abs(frame - plate).sum(axis=2) > 8
    top_half = changed[: changed.shape[0] // 2].mean()
    bottom_half = changed[changed.shape[0] // 2:].mean()
    # Le layout à 3 objets pose le héros en haut en premier.
    assert top_half > bottom_half


def test_renderer_never_blocks_on_a_missing_image():
    """Sans image générée, la scène existe quand même — dessinée."""
    renderer = LocalAssembleRenderer(width=120, height=200, fps=10)
    concept = _concept()
    assert renderer._load_ai_image(None) is None
    assert renderer._load_ai_image("/introuvable/nope.png") is None

    background = renderer._background_plate(concept)
    frame = renderer._compose(background, renderer._pictogram_pieces(concept),
                              3.9, 4.0)
    assert frame.size == (120, 200)
    # La scène finale diffère du fond vide: il y a bien des pièces posées.
    assert not np.array_equal(np.asarray(frame), np.asarray(background))


def test_video_service_produces_a_timeline_ready_clip(tmp_path, monkeypatch):
    """Sans ffmpeg dans l'environnement, on vérifie le CONTRAT de sortie."""
    written = {"frames": 0}

    class _FakePipe:
        def __init__(self, out_path, width=0, height=0, fps=30):
            self.out_path = out_path

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            with open(self.out_path, "wb") as fh:
                fh.write(b"MOV")

        def write(self, img):
            written["frames"] += 1

    monkeypatch.setattr("app.autoedit_engine.render_utils.ProResPipe", _FakePipe)
    service = CollageVideoService(renderer=LocalAssembleRenderer(160, 288, 8),
                                  max_workers=1)
    concept = _concept()
    clip = service.animate(concept, None, str(tmp_path))
    assert clip is not None
    assert clip.motion == "collage_assemble"
    assert written["frames"] > 0
    overlay = clip.to_engine_overlay()
    # Même dialecte que `broll_anim.render_all` -> plan_overlays sait le placer.
    assert set(overlay) >= {"id", "mov", "duration", "source_start", "kind"}
    assert overlay["kind"] == "collage_assemble"


# --------------------------------------------------------------------------- #
# ÉTAPE 6 — contrôle qualité
# --------------------------------------------------------------------------- #
def test_quality_accepts_a_clean_collage(tmp_path):
    path = _flat_collage_image(str(tmp_path / "clean.png"))
    report = CollageQualityService().review_image(path, _concept())
    assert report.text_free and report.watermark_free
    assert report.usable, report.to_dict()
    assert report.visual_clarity > 0 and report.style_consistency > 0


def test_quality_rejects_an_image_full_of_lettering(tmp_path):
    path = _text_image(str(tmp_path / "text.png"))
    report = CollageQualityService().review_image(path, _concept())
    assert not report.text_free
    assert "text_detected" in report.issues
    assert not report.usable


def test_quality_does_not_mistake_the_halftone_texture_for_text(tmp_path):
    """Faux positif à éviter absolument: la trame N&B FAIT PARTIE du style.

    Si le détecteur la confondait avec du lettrage, chaque scène serait
    relancée deux fois puis jugée inutilisable — le moteur brûlerait son budget
    API pour rien.
    """
    renderer = LocalAssembleRenderer(width=540, height=960, fps=30)
    concept = _concept()
    path = str(tmp_path / "halftone.png")
    frame = renderer._compose(renderer._background_plate(concept),
                              renderer._pictogram_pieces(concept), 3.9, 4.0)
    frame.convert("RGB").save(path)

    report = CollageQualityService().review_image(path, concept)
    assert report.text_free, report.to_dict()
    assert report.watermark_free
    assert report.usable


def test_quality_report_exposes_the_public_contract(tmp_path):
    path = _flat_collage_image(str(tmp_path / "clean.png"))
    payload = CollageQualityService().review_image(path, _concept()).to_dict()
    assert {"visual_clarity", "style_consistency", "usable"} <= set(payload)
    assert isinstance(payload["usable"], bool)
    assert 0 <= payload["visual_clarity"] <= 100


def test_missing_image_is_never_usable():
    report = CollageQualityService().review_image(None, _concept())
    assert not report.usable and "missing_image" in report.issues


def test_retry_hints_are_actionable():
    report = QualityReport(issues=["text_detected", "elements_not_separated"])
    hints = CollageQualityService.retry_hints(report)
    assert len(hints) == 2
    assert any("typography" in h for h in hints)


# --------------------------------------------------------------------------- #
# ÉTAPE 1 — orchestration bout en bout
# --------------------------------------------------------------------------- #
class _StubRenderer:
    name = "stub_renderer"

    def __init__(self):
        self.calls = 0

    def render(self, concept, image_path, out_path, *, duration, prompts=None):
        self.calls += 1
        with open(out_path, "wb") as fh:
            fh.write(b"MOV")
        return duration


def _pipeline(tmp_path, provider, *, quality=None) -> CollagePipeline:
    return CollagePipeline(
        planner=CollageConceptPlanner(api_key="", use_llm=False,
                                      cache=JsonCache("t", enabled=False)),
        image_service=CollageImageService(provider=provider,
                                          cache=BinaryCache("t", enabled=False),
                                          max_workers=1),
        video_service=CollageVideoService(renderer=_StubRenderer(), max_workers=1),
        quality_service=quality or CollageQualityService(),
    )


def test_pipeline_runs_end_to_end_without_any_human_gate(tmp_path):
    png = tmp_path / "src.png"
    _flat_collage_image(str(png))
    pipeline = _pipeline(tmp_path, _StubProvider(png.read_bytes()))
    result = pipeline.run(_beats(), str(tmp_path))

    assert result.skipped_reason is None
    assert len(result.concepts) == 2
    assert len(result.clips) == 2
    assert result.stats["clips"] == 2
    assert all(c.motion == "collage_assemble" for c in result.clips)
    # Le résultat est entièrement sérialisable (rapport de job).
    json.dumps(result.to_dict())


def test_pipeline_retries_only_the_scenes_that_fail_quality(tmp_path):
    png = tmp_path / "src.png"
    _flat_collage_image(str(png))
    provider = _StubProvider(png.read_bytes())

    class _AlwaysBad(CollageQualityService):
        def review_image(self, image_path, concept):
            return QualityReport(usable=False, score=10, issues=["text_detected"])

    pipeline = _pipeline(tmp_path, provider, quality=_AlwaysBad())
    result = pipeline.run(_beats()[:1], str(tmp_path))
    # QUALITY_MAX_ATTEMPTS essais, puis on garde le meilleur (jamais de trou).
    assert provider.calls == ccfg.QUALITY_MAX_ATTEMPTS
    assert result.assets and result.assets[0].attempts == ccfg.QUALITY_MAX_ATTEMPTS
    assert len(result.clips) == 1


def test_pipeline_still_delivers_clips_when_image_generation_is_dead(tmp_path):
    pipeline = _pipeline(tmp_path, _StubProvider(b"", fail_first=99))
    result = pipeline.run(_beats(), str(tmp_path))
    assert not any(a.image_path for a in result.assets)
    assert len(result.clips) == 2        # collage procédural: la scène existe
    assert result.stats["images"] == 0


def test_pipeline_caps_the_number_of_scenes(tmp_path):
    png = tmp_path / "src.png"
    _flat_collage_image(str(png))
    pipeline = _pipeline(tmp_path, _StubProvider(png.read_bytes()))
    pipeline.max_scenes = 1
    result = pipeline.run(_beats(), str(tmp_path))
    assert len(result.concepts) == 1


def test_pipeline_without_beats_is_a_no_op(tmp_path):
    result = _pipeline(tmp_path, _StubProvider(b"x")).run([], str(tmp_path))
    assert result.skipped_reason == "no_beats"
    assert result.clips == []


# --------------------------------------------------------------------------- #
# ÉTAPE 9 — intégration sans régression
# --------------------------------------------------------------------------- #
def test_engine_router_is_disabled_until_the_flag_is_on(monkeypatch):
    from app.autoedit_engine.pipeline import _split_collage_ideas

    ideas = [{"id": "br_000", "excerpt": "c'est comme une porte fermée",
              "prompt": "x", "source_start": 1.0, "source_end": 5.0}]
    monkeypatch.setenv("COLLAGE_BROLL_ENABLED", "0")
    assert _split_collage_ideas(ideas) == ([], ideas)

    monkeypatch.setenv("COLLAGE_BROLL_ENABLED", "1")
    collage, photo = _split_collage_ideas(ideas)
    assert len(collage) == 1 and photo == []
    monkeypatch.setenv("COLLAGE_BROLL_ENABLED", "0")
    ccfg.refresh()


def test_plan_overlays_places_collage_clips_and_their_sfx(tmp_path):
    from app.autoedit_engine import plan_overlays

    edl = {"ranges": [{"start": 0.0, "end": 30.0}], "overlays": []}
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps(edl), encoding="utf-8")

    mov = tmp_path / "cg.mov"
    mov.write_bytes(b"MOV")
    collage_json = tmp_path / "_collage_clips.json"
    collage_json.write_text(json.dumps([
        {"id": "cg_000", "mov": str(mov), "duration": 4.0,
         "source_start": 6.0, "kind": "collage_assemble"},
    ]), encoding="utf-8")

    planned = plan_overlays.plan(str(edl_path), None, None,
                                 outdir=str(tmp_path),
                                 collage_json=str(collage_json))
    placed = [o for o in planned["overlays"] if o["kind"] == "collage"]
    assert len(placed) == 1 and placed[0]["start"] == pytest.approx(6.0)
    assert any(c["src"] == "collage" for c in planned["cues"])


def test_plan_overlays_without_collage_is_unchanged(tmp_path):
    """Garantie de non-régression: sans collage, le contrat historique tient."""
    from app.autoedit_engine import plan_overlays

    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps({"ranges": [{"start": 0.0, "end": 20.0}],
                                    "overlays": []}), encoding="utf-8")
    planned = plan_overlays.plan(str(edl_path), None, None, outdir=str(tmp_path))
    assert planned["overlays"] == []
    assert planned["cues"] == []


def test_collage_sfx_come_from_the_existing_engine_vocabulary():
    from app.autoedit_engine import config as engine_config
    from app.autoedit_engine.plan_overlays import _collage_sfx_pool

    assert set(_collage_sfx_pool()) <= set(engine_config.SFX_NAMES)


def test_pipeline_v2_exports_the_collage_settings(monkeypatch):
    from app.processing.pipeline_v2 import _export_collage_env

    for key in ("COLLAGE_BROLL_ENABLED", "COLLAGE_MAX_SCENES"):
        monkeypatch.delenv(key, raising=False)
    _export_collage_env({"collage_broll": True, "collage_max_scenes": 2})
    assert os.environ["COLLAGE_BROLL_ENABLED"] == "1"
    assert os.environ["COLLAGE_MAX_SCENES"] == "2"

    _export_collage_env({})
    assert os.environ["COLLAGE_BROLL_ENABLED"] == "0"   # opt-in par défaut


def test_collage_mode_is_selectable_and_maps_to_the_engine():
    from app.api.v1 import modes
    from app.config import VALID_MODES
    from app.processing.pipeline_v2 import MODE_TO_TEMPLATE, V2_MODE_PRESETS

    assert "collage_premium" in VALID_MODES
    assert V2_MODE_PRESETS["collage_premium"]["collage_broll"] is True
    assert MODE_TO_TEMPLATE["collage_premium"] in ("pill_editorial",)
    by_id = {m["id"]: m for m in modes.MODE_DEFINITIONS}
    assert by_id["collage_premium"]["defaults"]["collage_broll"] is True
    assert by_id["collage_premium"].get("default") is True
