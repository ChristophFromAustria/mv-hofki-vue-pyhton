"""Loan API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.loan import LoanCreate, LoanRead, LoanUpdate
from mv_hofki.services import loan as loan_service

router = APIRouter(prefix="/api/v1/loans", tags=["loans"])


@router.get("", response_model=list[LoanRead])
async def list_loans(
    active: bool | None = None,
    instrument_id: int | None = None,
    musician_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await loan_service.get_list(
        db, active=active, instrument_id=instrument_id, musician_id=musician_id
    )


@router.post("", response_model=LoanRead, status_code=201)
async def create_loan(data: LoanCreate, db: AsyncSession = Depends(get_db)):
    return await loan_service.create(db, data)


@router.get("/{loan_id}", response_model=LoanRead)
async def get_loan(loan_id: int, db: AsyncSession = Depends(get_db)):
    return await loan_service.get_by_id(db, loan_id)


@router.put("/{loan_id}", response_model=LoanRead)
async def update_loan(
    loan_id: int, data: LoanUpdate, db: AsyncSession = Depends(get_db)
):
    return await loan_service.update(db, loan_id, data)


@router.put("/{loan_id}/return", response_model=LoanRead)
async def return_loan(loan_id: int, db: AsyncSession = Depends(get_db)):
    return await loan_service.return_instrument(db, loan_id)
