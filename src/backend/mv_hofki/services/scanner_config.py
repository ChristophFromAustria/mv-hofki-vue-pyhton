"""Scanner config service — CRUD for row-based config entries."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.models.scanner_config_entry import ScannerConfigEntry
from mv_hofki.services.scanner_config_registry import _cast_value, _serialize_value


async def get_config_entries(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(ScannerConfigEntry))
    rows = result.scalars().all()
    return [_row_to_dict(row) for row in rows]


async def update_config_values(session: AsyncSession, values: dict) -> list[dict]:
    result = await session.execute(select(ScannerConfigEntry))
    entries = {row.key: row for row in result.scalars().all()}
    for key, value in values.items():
        if key not in entries:
            raise ValueError(f"Unknown config key: {key}")
        row = entries[key]
        _validate_value(row, value)
        row.value = _serialize_value(value, row.type)
    await session.flush()
    return [_row_to_dict(row) for row in entries.values()]


async def reset_config_keys(session: AsyncSession, keys: list[str]) -> list[dict]:
    result = await session.execute(select(ScannerConfigEntry))
    rows = result.scalars().all()
    for row in rows:
        if not keys or row.key in keys:
            row.value = row.default_value
    await session.flush()
    return [_row_to_dict(row) for row in rows]


async def get_effective_config(session: AsyncSession) -> dict:
    result = await session.execute(select(ScannerConfigEntry))
    rows = result.scalars().all()
    return {
        row.key: _cast_value(
            row.value, row.type, step=row.step, min_val=row.min, max_val=row.max
        )
        for row in rows
    }


def _row_to_dict(row: ScannerConfigEntry) -> dict:
    value = _cast_value(
        row.value, row.type, step=row.step, min_val=row.min, max_val=row.max
    )
    default = _cast_value(
        row.default_value, row.type, step=row.step, min_val=row.min, max_val=row.max
    )
    options = json.loads(row.options) if row.options else None
    return {
        "key": row.key,
        "value": value,
        "default_value": default,
        "is_modified": row.value != row.default_value,
        "type": row.type,
        "label": row.label,
        "group_path": row.group_path,
        "min": row.min,
        "max": row.max,
        "step": row.step,
        "options": options,
        "sort_order": row.sort_order,
    }


def _validate_value(row: ScannerConfigEntry, value) -> None:
    if row.type == "toggle":
        if not isinstance(value, bool):
            raise ValueError(f"{row.key}: expected bool, got {type(value).__name__}")
    elif row.type == "number":
        if not isinstance(value, int | float):
            raise ValueError(f"{row.key}: expected number, got {type(value).__name__}")
        if row.min is not None and value < row.min:
            raise ValueError(f"{row.key}: {value} out of range [{row.min}, {row.max}]")
        if row.max is not None and value > row.max:
            raise ValueError(f"{row.key}: {value} out of range [{row.min}, {row.max}]")
    elif row.type == "select":
        options = json.loads(row.options) if row.options else []
        valid = {o["value"] for o in options}
        if value not in valid:
            raise ValueError(
                f"{row.key}: '{value}' not a valid option (valid: {valid})"
            )
