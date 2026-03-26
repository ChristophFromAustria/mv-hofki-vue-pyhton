"""Preprocessing stage: binarization, deskew, noise removal."""

from __future__ import annotations

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


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
            # block_size must be odd for adaptiveThreshold
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

        # Deskew using Hough line detection
        binary = self._deskew(binary)

        # Morphological noise removal
        k_size = ctx.config.get("morphology_kernel_size", 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        ctx.processed_image = binary
        ctx.image = binary
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None

    @staticmethod
    def _deskew(img: np.ndarray) -> np.ndarray:
        """Detect and correct skew angle using Hough transform."""
        edges = cv2.Canny(img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
        )

        if lines is None:
            return img

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(angle) < 5:  # only consider near-horizontal lines
                angles.append(angle)

        if not angles:
            return img

        median_angle = np.median(angles)
        if abs(median_angle) < 0.1:  # skip if nearly straight
            return img

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=255
        )
        return rotated
