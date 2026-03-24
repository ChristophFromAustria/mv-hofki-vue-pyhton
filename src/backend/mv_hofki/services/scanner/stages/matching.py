"""Symbol matching stage: compare detected regions against library."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

# Confidence thresholds
HIGH_CONFIDENCE = 0.85
LOW_CONFIDENCE = 0.40


class MatchingStage(ProcessingStage):
    """Compare extracted symbol snippets against library variants."""

    name = "matching"

    def __init__(
        self,
        variant_images: list[np.ndarray],
        variant_template_ids: list[int],
    ) -> None:
        self._variant_images = variant_images
        self._variant_template_ids = variant_template_ids
        self._variant_features: list[dict] | None = None

    def process(self, ctx: PipelineContext) -> PipelineContext:
        self._ensure_features()

        for symbol in ctx.symbols:
            if symbol.snippet is None:
                continue
            template_id, confidence, alternatives = self.match_snippet(symbol.snippet)
            symbol.matched_template_id = template_id
            symbol.confidence = confidence
            symbol.alternatives = alternatives

        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return len(ctx.symbols) > 0

    def match_snippet(
        self, snippet: np.ndarray
    ) -> tuple[int | None, float, list[tuple[int, float]]]:
        """Match a snippet against all library variants.

        Returns (best_template_id, confidence, [(template_id, score), ...]).
        """
        self._ensure_features()

        if not self._variant_features:
            return None, 0.0, []

        query_features = self.compute_features(snippet)
        scores: list[tuple[int, float]] = []

        for i, variant_feat in enumerate(self._variant_features):
            score = self._compare_features(query_features, variant_feat)
            template_id = self._variant_template_ids[i]
            scores.append((template_id, score))

        # Aggregate by template_id (take max score per template)
        template_scores: dict[int, float] = {}
        for tid, score in scores:
            if tid not in template_scores or score > template_scores[tid]:
                template_scores[tid] = score

        ranked = sorted(template_scores.items(), key=lambda x: x[1], reverse=True)

        if not ranked or ranked[0][1] < LOW_CONFIDENCE:
            return None, ranked[0][1] if ranked else 0.0, ranked[:5]

        return ranked[0][0], ranked[0][1], ranked[:5]

    @staticmethod
    def compute_features(snippet: np.ndarray) -> dict:
        """Compute feature vector for a symbol snippet."""
        if len(snippet.shape) == 3:
            snippet = cv2.cvtColor(snippet, cv2.COLOR_BGR2GRAY)

        h, w = snippet.shape
        aspect_ratio = w / max(h, 1)
        fill_density = np.sum(snippet > 128) / max(h * w, 1)

        # Hu moments — shape-based, scale/rotation invariant
        moments = cv2.moments(snippet)
        hu = cv2.HuMoments(moments).flatten()
        # Log-transform for better comparison
        hu_log = [-1 * np.sign(v) * np.log10(abs(v) + 1e-10) for v in hu]

        return {
            "hu_moments": hu_log,
            "aspect_ratio": float(aspect_ratio),
            "fill_density": float(fill_density),
        }

    def _ensure_features(self) -> None:
        """Compute features for library variants if not already done."""
        if self._variant_features is not None:
            return
        self._variant_features = [
            self.compute_features(img) for img in self._variant_images
        ]

    @staticmethod
    def _compare_features(a: dict, b: dict) -> float:
        """Compare two feature vectors, return similarity score 0-1."""
        # Hu moment distance (weighted heavily)
        hu_a = np.array(a["hu_moments"])
        hu_b = np.array(b["hu_moments"])
        hu_dist = np.sqrt(np.sum((hu_a - hu_b) ** 2))
        hu_score = max(0, 1 - hu_dist / 20.0)

        # Aspect ratio similarity
        ar_diff = abs(a["aspect_ratio"] - b["aspect_ratio"])
        ar_score = max(0, 1 - ar_diff / 2.0)

        # Fill density similarity
        fd_diff = abs(a["fill_density"] - b["fill_density"])
        fd_score = max(0, 1 - fd_diff)

        # Weighted combination
        return float(hu_score * 0.6 + ar_score * 0.2 + fd_score * 0.2)
