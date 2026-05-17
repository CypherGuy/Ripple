import os
import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from orchestrator.ws_manager import broadcast_event
from orchestrator.pipeline import _pending_approvals, fix_hit

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


@router.post("/internal/approve", status_code=202)
async def approve_service(
    request: Request,
    x_internal_secret: str | None = Header(default=None),
):
    expected = os.environ.get("INTERNAL_SECRET", "")
    if not expected or x_internal_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    body = await request.json()
    service = body.get("service", "")
    pending = _pending_approvals.pop(service, None)
    if pending is None:
        raise HTTPException(status_code=404, detail=f"No pending approval for service: {service}")

    async with httpx.AsyncClient() as client:
        result = await fix_hit(pending["hit"], pending["intel"], pending["trace_id"], client)

    return {"status": "accepted", "service": service, "result": result}
