"""Tests for PreprocessStage — rotation support."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext
from mv_hofki.services.scanner.stages.preprocess import PreprocessStage


def _make_ctx(img: np.ndarray, **config_overrides) -> PipelineContext:
    config = {"deskew_method": "none", "morphology_kernel_size": 1, **config_overrides}
    return PipelineContext(image=img, config=config)


def test_rotation_90_rotates_image():
    """A 100x200 image rotated 90° CW becomes 200x100."""
    img = np.full((100, 200), 200, dtype=np.uint8)
    img[0:10, 0:10] = 0

    ctx = _make_ctx(img, rotation=90, threshold=128)
    result = PreprocessStage().process(ctx)

    assert result.processed_image.shape == (
        200,
        100,
    ), f"Expected (200, 100), got {result.processed_image.shape}"


def test_rotation_0_no_change():
    """No rotation leaves dimensions unchanged."""
    img = np.full((100, 200), 200, dtype=np.uint8)
    ctx = _make_ctx(img, rotation=0, threshold=128)
    result = PreprocessStage().process(ctx)
    assert result.processed_image.shape[0] == 100
    assert result.processed_image.shape[1] == 200


def test_rotation_not_set_no_change():
    """Missing rotation config leaves dimensions unchanged."""
    img = np.full((100, 200), 200, dtype=np.uint8)
    ctx = _make_ctx(img, threshold=128)
    result = PreprocessStage().process(ctx)
    assert result.processed_image.shape[0] == 100
    assert result.processed_image.shape[1] == 200
