import os
from fastapi import APIRouter, Header, HTTPException, Request
from orchestrator.ws_manager import broadcast_event

router = APIRouter()


@router.post("/internal/broadcast")
async def internal_broadcast(
    request: Request,
    x_internal_secret: str | None = Header(default=None),
):
    expected = os.environ.get("INTERNAL_SECRET", "")
    if not expected or x_internal_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    data = await request.json()
    await broadcast_event(data)
    return {"ok": True}
