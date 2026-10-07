"""IllustrationDirector — the engine's single entry point.

    transcript
      -> semantic analysis        (analyzer/)
      -> importance scoring       (analyzer/)
      -> visual opportunity score (analyzer/)
      -> provider refinement      (providers/, optional)
      -> storyboard               (planner/)
      -> renderer selection       (renderers/)
      -> asset generation         (assets/)
      -> animation + SFX          (renderers/, audio/)
      -> timeline                 (timeline/)

It answers, for every moment of the speech: *should the viewer see something
here, what, and how should it be animated to land on the voice?*
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import config
from .analyzer.concept_detector import ConceptDetector
from .analyzer.semantic_analyzer import SemanticAnalyzer, SemanticUnit
from .analyzer.visual_opportunity_detector import VisualOpportunityDetector
from .assets.asset_manager import AssetManager
from .audio.sfx_planner import SFXPlanner
from .planner.storyboard_planner import StoryboardPlanner
from .renderers.renderer_router import RendererRouter
from .schemas.render_job import IllustrationTimeline, RenderedIllustration
from .schemas.scene import IllustrationScene
from .schemas.storyboard import Storyboard
from .schemas.visual import VisualOpportunity
from .styles import get_style
from .timeline.scene_timeline import build_timeline, to_output_overlays, write_manifest


@dataclass
class DirectorResult:
    storyboard: Storyboard
    timeline: IllustrationTimeline
    report: Dict[str, Any] = field(default_factory=dict)

    @property
    def legacy_clips(self) -> List[Dict[str, Any]]:
        """`_motion_clips.json`-shaped records for the existing pipeline."""
        return self.timeline.to_legacy_motion_clips()

    def spans(self) -> List[tuple]:
        """Source spans B-roll and keyword popups must avoid."""
        return [(s.start, s.end) for s in self.storyboard.scenes]


class IllustrationDirector:
    def __init__(self, style: str = "professional", intensity: str = None,
                 aspect: str = None, ai_mode: str = None, fps: int = None,
                 workdir: str = "", preview: bool = False,
                 allow_paid_images: bool = False,
                 width: int = 0, height: int = 0):
        self.style_name = style or "professional"
        self.style = get_style(self.style_name)
        self.intensity = intensity or config.DEFAULT_INTENSITY
        self.aspect = aspect or config.DEFAULT_ASPECT
        self.ai_mode = (ai_mode or config.AI_MODE or "offline").lower()
        if self.ai_mode not in config.VALID_AI_MODES:
            self.ai_mode = "offline"
        self.preview = bool(preview)
        self.workdir = workdir or ""

        aw, ah = config.aspect_size(self.aspect)
        self.width = int(width or aw)
        self.height = int(height or ah)
        base_fps = fps or config.FPS
        if self.preview:
            scale = max(0.2, min(1.0, config.PREVIEW_SCALE))
            self.width = int(self.width * scale) // 2 * 2
            self.height = int(self.height * scale) // 2 * 2
            base_fps = config.PREVIEW_FPS
        self.fps = max(1, int(base_fps))

        self.assets = AssetManager(
            workdir=os.path.join(self.workdir, "illustration_assets")
            if self.workdir else "",
            allow_generation=bool(allow_paid_images),
            style_hint=f"{self.style_name} flat vector illustration")
        self.sfx = SFXPlanner()

    # ------------------------------------------------------------------ #
    # analysis
    # ------------------------------------------------------------------ #
    def analyze(self, vu: dict) -> Tuple[List[SemanticUnit], List[VisualOpportunity], str]:
        """Transcript -> understood units + scored opportunities + provider used."""
        units = SemanticAnalyzer().analyze(vu or {})
        if not units:
            return [], [], "heuristic"

        total = float((vu or {}).get("duration") or units[-1].end)
        concepts = ConceptDetector().fit([u.text for u in units])
        detector = VisualOpportunityDetector(total, concepts)
        opportunities = detector.detect(units)

        provider_name = "heuristic"
        if self.ai_mode != "offline":
            from .providers import resolve_provider
            refinements, provider_name = resolve_provider(units, self.ai_mode)
            if refinements:
                self._apply_refinements(opportunities, refinements)
        self._concepts = concepts
        return units, opportunities, provider_name

    @staticmethod
    def _apply_refinements(opportunities: List[VisualOpportunity],
                           refinements: Sequence) -> None:
        """Merge provider output onto the heuristic reading.

        Only fields the provider actually filled are overwritten, so a model
        that answers partially improves the plan instead of degrading it.
        """
        for refinement in refinements:
            if not (0 <= refinement.index < len(opportunities)):
                continue
            opportunity = opportunities[refinement.index]
            if refinement.pattern:
                opportunity.pattern = refinement.pattern
            if refinement.items:
                opportunity.items = list(refinement.items)
            if refinement.visual_score is not None:
                opportunity.visual_score = refinement.visual_score
            if refinement.concept:
                opportunity.reason = f"provider: {refinement.concept}"
            if refinement.visual_type:
                # A suggestion, not a decision: the planner's diversity and
                # spacing rules still get the final say.
                setattr(opportunity, "suggested_type", refinement.visual_type)
            if refinement.title:
                setattr(opportunity, "suggested_title", refinement.title)

    # ------------------------------------------------------------------ #
    # planning
    # ------------------------------------------------------------------ #
    def storyboard(self, vu: dict) -> Storyboard:
        units, opportunities, provider_name = self.analyze(vu)
        if not opportunities:
            board = Storyboard(source_duration=float((vu or {}).get("duration") or 0.0),
                               style=self.style_name, intensity=self.intensity,
                               ai_mode=self.ai_mode, provider=provider_name)
            board.notes.append("transcript vide ou trop court pour être illustré")
            return board

        planner = StoryboardPlanner(
            style=self.style_name, intensity=self.intensity,
            aspect=self.aspect, concepts=getattr(self, "_concepts", None))
        board = planner.plan(opportunities, vu,
                             float((vu or {}).get("duration") or 0.0),
                             ai_mode=self.ai_mode, provider=provider_name)
        for scene in board.scenes:
            scene.sfx = self.sfx.plan(scene)
        return board

    # ------------------------------------------------------------------ #
    # rendering
    # ------------------------------------------------------------------ #
    def _workers(self, n_scenes: int) -> int:
        if config.RENDER_WORKERS > 0:
            return max(1, min(config.RENDER_WORKERS, n_scenes))
        # Each scene drives its own ffmpeg process; two at a time keeps a
        # small VPS responsive without starving it.
        return max(1, min(2, n_scenes, (os.cpu_count() or 2)))

    def render(self, board: Storyboard, outdir: str) -> IllustrationTimeline:
        os.makedirs(outdir, exist_ok=True)
        router = RendererRouter(self.style, self.width, self.height, self.fps,
                                assets=self.assets, preview=self.preview)
        rendered: Dict[str, RenderedIllustration] = {}
        if not board.scenes:
            return build_timeline(board, rendered, self.fps, self.width, self.height)

        def _one(scene: IllustrationScene):
            path = os.path.join(outdir, f"{scene.scene_id}.mov")
            return scene.scene_id, router.render(scene, path)

        workers = self._workers(len(board.scenes))
        if workers == 1:
            for scene in board.scenes:
                scene_id, clip = _one(scene)
                if clip is not None:
                    rendered[scene_id] = clip
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_one, scene) for scene in board.scenes]
                for future in as_completed(futures):
                    try:
                        scene_id, clip = future.result()
                    except Exception as exc:  # noqa: BLE001
                        print(f"[illustration_engine] WARN rendu échoué: {exc}",
                              file=sys.stderr)
                        continue
                    if clip is not None:
                        rendered[scene_id] = clip
        return build_timeline(board, rendered, self.fps, self.width, self.height)

    # ------------------------------------------------------------------ #
    # one-call path
    # ------------------------------------------------------------------ #
    def run(self, vu: dict, outdir: str,
            edl_ranges: Sequence[dict] = (),
            write_json: bool = True) -> DirectorResult:
        """Transcript in, rendered clips and a timeline out."""
        started = time.time()
        board = self.storyboard(vu)
        timeline = self.render(board, outdir)

        report: Dict[str, Any] = {
            "enabled": True,
            "style": self.style_name,
            "intensity": self.intensity,
            "aspect": self.aspect,
            "resolution": f"{self.width}x{self.height}",
            "fps": self.fps,
            "ai_mode": self.ai_mode,
            "provider": board.provider,
            "preview": self.preview,
            "scenes_planned": len(board.scenes),
            "scenes_rendered": len(timeline),
            "coverage": round(board.coverage, 4),
            "type_histogram": board.type_histogram(),
            "renderers": sorted({i.rendered.renderer for i in timeline}),
            "fallbacks": [i.rendered.fallback_from for i in timeline
                          if i.rendered.fallback_from],
            "assets": self.assets.report(),
            "notes": list(board.notes),
            "elapsed_s": round(time.time() - started, 2),
            # What the UI shows the user: when, what, and how confident.
            "plan": board.plan_summary(),
        }
        if edl_ranges:
            report["output_overlays"] = to_output_overlays(timeline, edl_ranges)
        if write_json:
            write_manifest(timeline,
                           os.path.join(outdir, "_illustrations.json"), board)
        return DirectorResult(storyboard=board, timeline=timeline, report=report)
