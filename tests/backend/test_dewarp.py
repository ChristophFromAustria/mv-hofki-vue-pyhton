"""Tests for the dewarp (bent staff line correction) stage."""

import numpy as np

from mv_hofki.services.scanner.stages.base import PipelineContext, StaffData
from mv_hofki.services.scanner.stages.dewarp import DewarpStage


def _draw_curved_staff(img, base_y, spacing, amplitude=8, width=None, thickness=3):
    """Draw 5 staff lines with sinusoidal curvature onto img."""
    if width is None:
        width = img.shape[1]
    xs = np.arange(width)
    curve = (amplitude * np.sin(2 * np.pi * xs / width)).astype(int)
    positions = []
    for i in range(5):
        line_y = base_y + i * spacing
        positions.append(line_y)
        for x in xs:
            y = line_y + curve[x]
            for dy in range(-(thickness // 2), thickness // 2 + 1):
                yy = y + dy
                if 0 <= yy < img.shape[0]:
                    img[yy, x] = 0
    return positions


def test_dewarp_straightens_curved_lines():
    """Curved staff lines should be straightened after dewarping."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    spacing = 12
    positions = _draw_curved_staff(img, 80, spacing, amplitude=10)

    staff = StaffData(
        staff_index=0,
        y_top=40,
        y_bottom=200,
        line_positions=positions,
        line_spacing=float(spacing),
    )

    stage = DewarpStage()
    ctx = PipelineContext(
        image=img.copy(),
        staves=[staff],
        config={"dewarp_smoothing": 30},
    )
    result = stage.process(ctx)

    # After dewarping, line_positions should be updated to straight values
    new_positions = result.staves[0].line_positions
    # The new positions should be roughly evenly spaced
    diffs = np.diff(new_positions)
    assert all(abs(d - spacing) <= 2 for d in diffs), f"Spacing not uniform: {diffs}"

    # The image should have changed (not identical to input)
    assert not np.array_equal(result.image, img)


def test_dewarp_noop_on_straight_lines():
    """Straight staff lines should produce minimal displacement."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    spacing = 12
    positions = []
    for i in range(5):
        y = 80 + i * spacing
        positions.append(y)
        img[y - 1 : y + 2, 20:580] = 0  # 3px thick

    staff = StaffData(
        staff_index=0,
        y_top=40,
        y_bottom=200,
        line_positions=positions,
        line_spacing=float(spacing),
    )

    stage = DewarpStage()
    ctx = PipelineContext(
        image=img.copy(),
        staves=[staff],
        config={"dewarp_smoothing": 30},
    )
    result = stage.process(ctx)

    # Positions should stay the same
    for orig, new in zip(positions, result.staves[0].line_positions):
        assert abs(orig - new) <= 1


def test_dewarp_skipped_with_too_few_lines():
    """Stage should gracefully handle a staff with fewer than 2 traceable lines."""
    img = np.full((100, 200), 255, dtype=np.uint8)
    # Only 1 line drawn
    img[50, 20:180] = 0

    staff = StaffData(
        staff_index=0,
        y_top=20,
        y_bottom=80,
        line_positions=[50],
        line_spacing=12.0,
    )

    stage = DewarpStage()
    ctx = PipelineContext(image=img.copy(), staves=[staff])
    result = stage.process(ctx)

    # Should return unchanged (not enough control points)
    assert np.array_equal(result.image, img)


def test_dewarp_updates_processed_image():
    """If processed_image is set, it should also be dewarped."""
    img = np.full((300, 600), 255, dtype=np.uint8)
    spacing = 12
    positions = _draw_curved_staff(img, 80, spacing, amplitude=10)

    staff = StaffData(
        staff_index=0,
        y_top=40,
        y_bottom=200,
        line_positions=positions,
        line_spacing=float(spacing),
    )

    stage = DewarpStage()
    ctx = PipelineContext(
        image=img.copy(),
        processed_image=img.copy(),
        staves=[staff],
        config={"dewarp_smoothing": 30},
    )
    result = stage.process(ctx)

    assert result.processed_image is not None
    assert not np.array_equal(result.processed_image, img)
