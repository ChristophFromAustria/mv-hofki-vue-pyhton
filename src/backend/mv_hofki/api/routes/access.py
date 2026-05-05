"""Routes for Cloudflare Access email management."""

from __future__ import annotations

from fastapi import APIRouter

from mv_hofki.schemas.access import EmailAdd, EmailList
from mv_hofki.services import access as access_service

router = APIRouter(prefix="/api/v1/access", tags=["access"])


@router.get("/emails", response_model=EmailList)
async def list_emails():
    emails = await access_service.get_emails()
    return EmailList(emails=emails)


@router.post("/emails", response_model=EmailList, status_code=201)
async def add_email(data: EmailAdd):
    emails = await access_service.add_email(data.email)
    return EmailList(emails=emails)


@router.delete("/emails/{email:path}", response_model=EmailList)
async def remove_email(email: str):
    emails = await access_service.remove_email(email)
    return EmailList(emails=emails)
