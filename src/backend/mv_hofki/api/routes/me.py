"""Current user endpoint — reads identity from Cloudflare Access headers."""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me")
async def get_current_user(request: Request):
    email = request.headers.get("Cf-Access-Authenticated-User-Email")
    return {"email": email}
