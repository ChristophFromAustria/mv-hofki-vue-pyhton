"""Tests for staff-relative position computation in template matching."""

from mv_hofki.services.scanner.stages.base import StaffData, SymbolData


def _compute_staff_coords(sym: SymbolData, staff: StaffData) -> SymbolData:
    """Mirror the computation from template matching for testability."""
    bottom_line_y = max(staff.line_positions)
    sym.staff_y_top = round((bottom_line_y - sym.y) / staff.line_spacing, 2)
    sym.staff_y_bottom = round(
        (bottom_line_y - (sym.y + sym.height)) / staff.line_spacing, 2
    )
    sym.staff_x_start = sym.x
    sym.staff_x_end = sym.x + sym.width
    return sym


def test_symbol_on_bottom_line():
    """Symbol whose top edge sits on the bottom staff line."""
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=50, y=180, width=30, height=40)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 0.0
    assert result.staff_y_bottom == -2.0
    assert result.staff_x_start == 50
    assert result.staff_x_end == 80


def test_symbol_one_line_above_bottom():
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=100, y=160, width=20, height=30)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 1.0
    assert result.staff_y_bottom == -0.5
    assert result.staff_x_start == 100
    assert result.staff_x_end == 120


def test_symbol_between_lines():
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=200, y=170, width=15, height=25)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 0.5
    assert result.staff_y_bottom == -0.75
    assert result.staff_x_start == 200
    assert result.staff_x_end == 215


def test_symbol_above_top_line():
    staff = StaffData(
        staff_index=0,
        y_top=100,
        y_bottom=180,
        line_positions=[100, 120, 140, 160, 180],
        line_spacing=20.0,
    )
    sym = SymbolData(staff_index=0, x=10, y=80, width=20, height=30)
    result = _compute_staff_coords(sym, staff)
    assert result.staff_y_top == 5.0
    assert result.staff_y_bottom == 3.5
