"""Tests for the processing pipeline framework."""

import cv2
import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, ProcessingStage


class DummyStage(ProcessingStage):
    name = "dummy"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        ctx.metadata["dummy_ran"] = True
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return ctx.image is not None


class FailingValidationStage(ProcessingStage):
    name = "failing"

    def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx

    def validate(self, ctx: PipelineContext) -> bool:
        return False


def test_pipeline_context_creation():
    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img)
    assert ctx.image is not None
    assert ctx.metadata == {}
    assert ctx.staves == []
    assert ctx.symbols == []


def test_stage_process():
    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img)
    stage = DummyStage()
    result = stage.process(ctx)
    assert result.metadata["dummy_ran"] is True


def test_stage_validate():
    ctx = PipelineContext(image=np.zeros((10, 10), dtype=np.uint8))
    assert DummyStage().validate(ctx) is True

    ctx_no_image = PipelineContext(image=None)
    assert DummyStage().validate(ctx_no_image) is False


def test_pipeline_runs_stages_in_order():
    from mv_hofki.services.scanner.pipeline import Pipeline

    class StageA(ProcessingStage):
        name = "a"

        def process(self, ctx):
            ctx.metadata.setdefault("order", []).append("a")
            return ctx

        def validate(self, ctx):
            return True

    class StageB(ProcessingStage):
        name = "b"

        def process(self, ctx):
            ctx.metadata.setdefault("order", []).append("b")
            return ctx

        def validate(self, ctx):
            return True

    pipeline = Pipeline(stages=[StageA(), StageB()])
    ctx = PipelineContext(image=np.zeros((10, 10), dtype=np.uint8))
    result = pipeline.run(ctx)
    assert result.metadata["order"] == ["a", "b"]


def test_pipeline_skips_disabled_stages():
    from mv_hofki.services.scanner.pipeline import Pipeline

    class StageA(ProcessingStage):
        name = "a"

        def process(self, ctx):
            ctx.metadata["a_ran"] = True
            return ctx

        def validate(self, ctx):
            return True

    pipeline = Pipeline(stages=[StageA()])
    ctx = PipelineContext(
        image=np.zeros((10, 10), dtype=np.uint8),
        config={"disabled_stages": ["a"]},
    )
    result = pipeline.run(ctx)
    assert "a_ran" not in result.metadata


def test_pipeline_records_completed_stages():
    from mv_hofki.services.scanner.pipeline import Pipeline

    class StageA(ProcessingStage):
        name = "a"

        def process(self, ctx):
            return ctx

        def validate(self, ctx):
            return True

    pipeline = Pipeline(stages=[StageA()])
    ctx = PipelineContext(image=np.zeros((10, 10), dtype=np.uint8))
    result = pipeline.run(ctx)
    assert "a" in result.completed_stages


def test_preprocess_stage_binarizes():
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    # Create a grayscale image with some gray areas
    img = np.full((200, 200), 180, dtype=np.uint8)
    img[50:150, 50:150] = 40  # dark square

    ctx = PipelineContext(image=img)
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.processed_image is not None
    # Should be binary — only 0 and 255
    unique = np.unique(result.processed_image)
    assert all(v in (0, 255) for v in unique)


def test_preprocess_stage_preserves_original():
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    img = np.full((100, 100), 128, dtype=np.uint8)
    ctx = PipelineContext(image=img)
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.original_image is not None
    assert np.array_equal(result.original_image, img)


def _create_staff_image(num_staves=3, staff_spacing=60, line_gap=10, width=800):
    """Create a test image with horizontal staff lines."""
    height = num_staves * staff_spacing * 2 + 100
    img = np.full((height, width), 255, dtype=np.uint8)
    y = 50
    for _ in range(num_staves):
        for line in range(5):
            line_y = y + line * line_gap
            img[line_y : line_y + 2, 20 : width - 20] = 0
        y += staff_spacing + 5 * line_gap
    return img


def test_stave_detection_finds_staves():
    from mv_hofki.services.scanner.stages.stave_detection import StaveDetectionStage

    img = _create_staff_image(num_staves=3)
    ctx = PipelineContext(image=img, processed_image=img)
    stage = StaveDetectionStage()
    result = stage.process(ctx)

    assert len(result.staves) == 3
    for staff in result.staves:
        assert len(staff.line_positions) == 5
        assert staff.line_spacing > 0


def test_stave_detection_single_staff():
    from mv_hofki.services.scanner.stages.stave_detection import StaveDetectionStage

    img = _create_staff_image(num_staves=1)
    ctx = PipelineContext(image=img, processed_image=img)
    stage = StaveDetectionStage()
    result = stage.process(ctx)

    assert len(result.staves) == 1


def test_staff_removal_removes_lines():
    from mv_hofki.services.scanner.stages.base import StaffData
    from mv_hofki.services.scanner.stages.staff_removal import StaffRemovalStage

    img = _create_staff_image(num_staves=1, width=200)
    ctx = PipelineContext(
        image=img,
        processed_image=img,
        staves=[
            StaffData(
                staff_index=0,
                y_top=30,
                y_bottom=120,
                line_positions=[50, 60, 70, 80, 90],
                line_spacing=10.0,
            )
        ],
    )
    stage = StaffRemovalStage()
    result = stage.process(ctx)

    # Staff lines should be mostly removed
    for y in [50, 60, 70, 80, 90]:
        row_black = np.sum(result.image[y : y + 2, :] == 0)
        original_black = np.sum(img[y : y + 2, :] == 0)
        assert row_black < original_black


def test_segmentation_finds_symbols():
    from mv_hofki.services.scanner.stages.base import StaffData
    from mv_hofki.services.scanner.stages.segmentation import SegmentationStage

    # Create image with staff lines and some "note" blobs
    img = np.full((200, 400), 255, dtype=np.uint8)
    # Add some black circles (fake notes)
    cv2.circle(img, (100, 80), 8, 0, -1)
    cv2.circle(img, (200, 90), 8, 0, -1)
    cv2.circle(img, (300, 75), 8, 0, -1)

    ctx = PipelineContext(
        image=img,
        processed_image=img,
        staves=[
            StaffData(
                staff_index=0,
                y_top=30,
                y_bottom=150,
                line_positions=[50, 65, 80, 95, 110],
                line_spacing=15.0,
            )
        ],
    )
    stage = SegmentationStage()
    result = stage.process(ctx)

    assert len(result.symbols) == 3
    # Should be ordered left to right
    xs = [s.x for s in result.symbols]
    assert xs == sorted(xs)


def test_matching_computes_features():
    from mv_hofki.services.scanner.stages.matching import MatchingStage

    # Create a simple symbol snippet
    snippet = np.zeros((20, 15), dtype=np.uint8)
    cv2.circle(snippet, (7, 10), 5, 255, -1)

    stage = MatchingStage(variant_images=[], variant_template_ids=[])
    features = stage.compute_features(snippet)

    assert "hu_moments" in features
    assert "aspect_ratio" in features
    assert "fill_density" in features
    assert len(features["hu_moments"]) == 7


def test_matching_finds_best_match():
    from mv_hofki.services.scanner.stages.matching import MatchingStage

    # Create a "library" variant — a black circle
    variant = np.zeros((20, 15), dtype=np.uint8)
    cv2.circle(variant, (7, 10), 5, 255, -1)

    # Create a query snippet — same circle
    query = np.zeros((20, 15), dtype=np.uint8)
    cv2.circle(query, (7, 10), 5, 255, -1)

    stage = MatchingStage(
        variant_images=[variant],
        variant_template_ids=[42],
    )
    template_id, confidence, alternatives = stage.match_snippet(query)

    assert template_id == 42
    assert confidence > 0.8


def test_preprocess_reads_adaptive_params_from_config():
    """Preprocessing should use adaptive threshold params from config."""
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    img = np.full((200, 200), 180, dtype=np.uint8)
    img[50:150, 50:150] = 40

    ctx = PipelineContext(
        image=img,
        config={
            "adaptive_threshold_block_size": 25,
            "adaptive_threshold_c": 5,
            "morphology_kernel_size": 3,
        },
    )
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.processed_image is not None
    unique = np.unique(result.processed_image)
    assert all(v in (0, 255) for v in unique)


def test_preprocess_global_threshold():
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    img = np.full((100, 100), 180, dtype=np.uint8)
    img[30:70, 30:70] = 40

    ctx = PipelineContext(image=img, config={"threshold": 128})
    stage = PreprocessStage()
    result = stage.process(ctx)

    assert result.processed_image is not None
    unique = np.unique(result.processed_image)
    assert all(v in (0, 255) for v in unique)
    # With global threshold=128: pixels at 180 → white, pixels at 40 → black
    assert result.processed_image[50, 50] == 0  # dark area → black
    assert result.processed_image[5, 5] == 255  # light area → white


def test_preprocess_uses_configured_deskew_method():
    """PreprocessStage should delegate to the deskew method set in config."""
    from mv_hofki.services.scanner.stages.preprocess import PreprocessStage

    # Create a slightly tilted image with staff-like lines
    img = np.full((300, 600, 3), 255, dtype=np.uint8)
    for y in [100, 120, 140, 160, 180]:
        cv2.line(img, (0, y + 5), (600, y - 5), 0, 2)  # ~1° tilt

    # Test with projection method
    ctx = PipelineContext(image=img.copy(), config={"deskew_method": "projection"})
    stage = PreprocessStage()
    result = stage.process(ctx)
    assert result.corrected_image is not None
    assert result.corrected_image.shape[:2] == img.shape[:2]

    # Test with hough method
    ctx2 = PipelineContext(image=img.copy(), config={"deskew_method": "hough"})
    result2 = stage.process(ctx2)
    assert result2.corrected_image is not None

    # Test default (none = skip deskew, backward compatible)
    ctx3 = PipelineContext(image=img.copy(), config={"deskew_method": "none"})
    result3 = stage.process(ctx3)
    assert result3.corrected_image is None
