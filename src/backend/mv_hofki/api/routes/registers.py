"""Register API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.register import RegisterCreate, RegisterRead, RegisterUpdate
from mv_hofki.services import register as register_service

router = APIRouter(prefix="/api/v1/registers", tags=["registers"])


@router.get("", response_model=list[RegisterRead])
async def list_registers(db: AsyncSession = Depends(get_db)):
    return await register_service.get_all(db)


@router.post("", response_model=RegisterRead, status_code=201)
async def create_register(data: RegisterCreate, db: AsyncSession = Depends(get_db)):
    return await register_service.create(db, data)


@router.get("/{register_id}", response_model=RegisterRead)
async def get_register(register_id: int, db: AsyncSession = Depends(get_db)):
    return await register_service.get_by_id(db, register_id)


@router.put("/{register_id}", response_model=RegisterRead)
async def update_register(
    register_id: int, data: RegisterUpdate, db: AsyncSession = Depends(get_db)
):
    return await register_service.update(db, register_id, data)


@router.delete("/{register_id}", status_code=204)
async def delete_register(register_id: int, db: AsyncSession = Depends(get_db)):
    await register_service.delete(db, register_id)
    return Response(status_code=204)
