"""Global search API (the search field in the header)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.search import SearchResult
from mv_hofki.services import global_search

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("", response_model=SearchResult)
async def search(
    q: str = Query("", max_length=200),
    limit: int = Query(3, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await global_search.search(db, q, limit)
