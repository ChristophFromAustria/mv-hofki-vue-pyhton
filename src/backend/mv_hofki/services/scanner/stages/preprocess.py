"""Preprocessing stage: binarization, deskew, noise removal."""

from __future__ import annotations

import cv2

from mv_hofki.services.scanner.deskew import deskew_hough, deskew_projection
from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage

_DESKEW_STRATEGIES = {
    "hough": deskew_hough,
    "projection": deskew_projection,
}


class PreprocessStage(ProcessingStage):
    """Adaptive thresholding, deskew, and morphological noise removal."""

    name = "preprocess"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        assert ctx.image is not None
        img = ctx.image
        ctx.original_image = img.copy()

        # Convert to grayscale if needed
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Apply brightness/contrast adjustments from config
        brightness = ctx.config.get("brightness", 0)
        contrast = ctx.config.get("contrast", 1.0)
        if brightness != 0 or contrast != 1.0:
            gray = cv2.convertScaleAbs(gray, alpha=contrast, beta=brightness)

        # Binarize: use global threshold if provided, otherwise adaptive
        threshold_val = ctx.config.get("threshold")
        if threshold_val is not None:
            _, binary = cv2.threshold(gray, int(threshold_val), 255, cv2.THRESH_BINARY)
        else:
            block_size = ctx.config.get("adaptive_threshold_block_size", 15)
            if block_size % 2 == 0:
                block_size += 1
            c_val = ctx.config.get("adaptive_threshold_c", 10)
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=block_size,
                C=c_val,
            )

        # Deskew using configured strategy
        method = ctx.config.get("deskew_method", "none")
        deskew_fn = _DESKEW_STRATEGIES.get(method)
        if deskew_fn is not None:
            binary = deskew_fn(binary)
            # Also rotate the grayscale image for frontend preview
            ctx.corrected_image = deskew_fn(gray)
            ctx.log(f"Deskew angewendet (Methode: {method})")

        # Morphological noise removal
        k_size = ctx.config.get("morphology_kernel_size", 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        ctx.processed_image = binary
        ctx.image = binary
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None
