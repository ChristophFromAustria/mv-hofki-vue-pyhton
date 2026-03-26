"""Health check and debug endpoints."""

import logging

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.put("/debug/sql-echo")
def set_sql_echo(enabled: bool = True):
    """Toggle SQLAlchemy SQL logging at runtime."""
    sa_logger = logging.getLogger("sqlalchemy.engine")
    sa_logger.setLevel(logging.INFO if enabled else logging.WARNING)
    return {"sql_echo": enabled}
