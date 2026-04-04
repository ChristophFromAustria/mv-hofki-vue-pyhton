"""Tests for the text masking pipeline stage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData


def _make_staff_image():
    """Create a binary image with staff lines."""
    img = np.full((300, 800), 255, dtype=np.uint8)
    for y in [50, 60, 70, 80, 90]:
        img[y : y + 2, 20:780] = 0
    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=200,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    return img, staff


def _mock_easyocr_results(*_args, **_kwargs):
    """Return fake EasyOCR results: list of (bbox, text, confidence)."""
    return [
        ([[100, 120], [180, 120], [180, 135], [100, 135]], "cresc.", 0.85),
        ([[250, 120], [290, 120], [290, 135], [250, 135]], "Trio", 0.90),
    ]


def _mock_easyocr_empty(*_args, **_kwargs):
    """Return empty EasyOCR result."""
    return []


def test_text_masking_uses_easyocr(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_easyocr", _mock_easyocr_results)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 2
    assert result.text_regions[0].text == "cresc."
    assert result.text_regions[0].confidence == 85.0
    assert result.text_regions[1].text == "Trio"
    assert result.text_regions[1].confidence == 90.0


def test_text_masking_masks_detected_regions(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_easyocr", _mock_easyocr_results)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    # Region at x=100, y=120, w=80, h=15 should be white
    region = result.processed_image[120:135, 100:180]
    assert np.all(region == 255)


def test_text_masking_assigns_nearest_staff(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_easyocr", _mock_easyocr_results)

    img = np.full((500, 800), 255, dtype=np.uint8)
    staff0 = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=150,
        line_positions=[50, 60, 70, 80, 90],
        line_spacing=10.0,
    )
    staff1 = StaffData(
        staff_index=1,
        y_top=200,
        y_bottom=350,
        line_positions=[250, 260, 270, 280, 290],
        line_spacing=10.0,
    )
    ctx = PipelineContext(
        image=img, processed_image=img.copy(), staves=[staff0, staff1]
    )

    stage = TextMaskingStage()
    result = stage.process(ctx)

    # Mock data has y=120, closer to staff0 (center ~70) than staff1 (center ~270)
    for r in result.text_regions:
        assert r.staff_index == 0


def test_text_masking_filters_low_confidence(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    def mock_low_conf(*_args, **_kwargs):
        return [
            ([[100, 120], [180, 120], [180, 135], [100, 135]], "noise", 0.10),
            ([[250, 120], [290, 120], [290, 135], [250, 135]], "real", 0.85),
        ]

    monkeypatch.setattr(text_masking, "_run_easyocr", mock_low_conf)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 1
    assert result.text_regions[0].text == "real"


def test_text_masking_filters_staff_line_overlap(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    def mock_on_staff(*_args, **_kwargs):
        return [
            # This overlaps with staff lines at y=50-90
            ([[100, 60], [150, 60], [150, 80], [100, 80]], "noise", 0.90),
            # This is below staff lines
            ([[100, 120], [180, 120], [180, 135], [100, 135]], "cresc.", 0.85),
        ]

    monkeypatch.setattr(text_masking, "_run_easyocr", mock_on_staff)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 1
    assert result.text_regions[0].text == "cresc."


def test_text_masking_no_results_on_empty(monkeypatch):
    from mv_hofki.services.scanner.stages import text_masking
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    monkeypatch.setattr(text_masking, "_run_easyocr", _mock_easyocr_empty)

    img, staff = _make_staff_image()
    ctx = PipelineContext(image=img, processed_image=img.copy(), staves=[staff])

    stage = TextMaskingStage()
    result = stage.process(ctx)

    assert len(result.text_regions) == 0


def test_text_masking_validate():
    from mv_hofki.services.scanner.stages.text_masking import TextMaskingStage

    stage = TextMaskingStage()

    ctx = PipelineContext(image=None, processed_image=None)
    assert stage.validate(ctx) is False

    img = np.zeros((100, 100), dtype=np.uint8)
    ctx = PipelineContext(image=img, processed_image=img)
    assert stage.validate(ctx) is False

    staff = StaffData(
        staff_index=0,
        y_top=0,
        y_bottom=100,
        line_positions=[20, 30, 40, 50, 60],
        line_spacing=10.0,
    )
    ctx = PipelineContext(image=img, processed_image=img, staves=[staff])
    assert stage.validate(ctx) is True
