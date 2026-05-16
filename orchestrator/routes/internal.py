from fastapi import APIRouter, Request
from orchestrator.ws_manager import broadcast_event

router = APIRouter()


@router.post("/internal/broadcast")
async def internal_broadcast(request: Request):
    data = await request.json()
    await broadcast_event(data)
    return {"ok": True}
