"""Loan API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mv_hofki.api.deps import get_db
from mv_hofki.schemas.inventory_item import ItemRead, format_display_nr
from mv_hofki.schemas.loan import LoanCreate, LoanRead, LoanReturn, LoanUpdate
from mv_hofki.services import loan as loan_service

router = APIRouter(prefix="/api/v1/loans", tags=["loans"])


def _loan_to_read(loan) -> LoanRead:
    """Convert a Loan ORM object to LoanRead, adding display_nr to the item."""
    item = loan.item
    item_read = ItemRead(
        id=item.id,
        category=item.category,
        inventory_nr=item.inventory_nr,
        display_nr=format_display_nr(item.category, item.inventory_nr),
        label=item.label,
        manufacturer=item.manufacturer,
        acquisition_date=item.acquisition_date,
        acquisition_cost=item.acquisition_cost,
        currency_id=item.currency_id,
        owner=item.owner,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        currency=item.currency,
    )
    return LoanRead(
        id=loan.id,
        item_id=loan.item_id,
        musician_id=loan.musician_id,
        start_date=loan.start_date,
        end_date=loan.end_date,
        created_at=loan.created_at,
        item=item_read,
        musician=loan.musician,
    )


@router.get("", response_model=list[LoanRead])
async def list_loans(
    active: bool | None = None,
    item_id: int | None = None,
    musician_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    loans = await loan_service.get_list(
        db, active=active, item_id=item_id, musician_id=musician_id
    )
    return [_loan_to_read(loan) for loan in loans]


@router.post("", response_model=LoanRead, status_code=201)
async def create_loan(data: LoanCreate, db: AsyncSession = Depends(get_db)):
    return _loan_to_read(await loan_service.create(db, data))


@router.get("/{loan_id}", response_model=LoanRead)
async def get_loan(loan_id: int, db: AsyncSession = Depends(get_db)):
    return _loan_to_read(await loan_service.get_by_id(db, loan_id))


@router.put("/{loan_id}", response_model=LoanRead)
async def update_loan(
    loan_id: int, data: LoanUpdate, db: AsyncSession = Depends(get_db)
):
    return _loan_to_read(await loan_service.update(db, loan_id, data))


@router.put("/{loan_id}/return", response_model=LoanRead)
async def return_loan(
    loan_id: int, data: LoanReturn | None = None, db: AsyncSession = Depends(get_db)
):
    end_date = data.end_date if data else None
    return _loan_to_read(await loan_service.return_item(db, loan_id, end_date=end_date))
