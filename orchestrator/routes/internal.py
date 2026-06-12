import os
import asyncio
import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from orchestrator.ws_manager import broadcast_event
from orchestrator.pipeline import _pending_approvals, fix_hit
import orchestrator.pipeline as _pipeline_mod

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
    x_admin_secret: str | None = Header(default=None),
):
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    body = await request.json()
    service = body.get("service", "")
    hit = body.get("hit")
    intel = body.get("intel")
    trace_id = body.get("trace_id")

    # If the dashboard didn't send the full context, fall back to in-memory state
    if not (hit and intel and trace_id):
        pending = _pending_approvals.pop(service, None)
        if pending is None:
            raise HTTPException(
                status_code=404,
                detail=f"No pending approval for service: {service}. "
                       "The orchestrator may have restarted. Re-run the pipeline.",
            )
        hit, intel, trace_id = pending["hit"], pending["intel"], pending["trace_id"]
    else:
        _pending_approvals.pop(service, None)

    async with httpx.AsyncClient() as client:
        result = await fix_hit(hit, intel, trace_id, client)

    return {"status": "accepted", "service": service, "result": result}


@router.post("/internal/scan-event")
async def internal_scan_event(
    request: Request,
    x_internal_secret: str | None = Header(default=None),
):
    """Callback target for scanner hit/no_hit/agent_started events.
    Broadcasts to WebSocket and, for hit_found, immediately starts a fix task
    without waiting for all services to finish scanning."""
    expected = os.environ.get("INTERNAL_SECRET", "")
    if not expected or x_internal_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    await broadcast_event(data)

    if data.get("event") == "hit_found":
        state = _pipeline_mod._pipeline_state
        if state is not None:
            service = data.get("service", "")
            hit_data = data.get("data", {})
            hit = {
                "service": service,
                "file_path": hit_data.get("file_path", ""),
                "matching_lines": hit_data.get("matching_lines", []),
                "confidence": hit_data.get("confidence", 0),
                "gitlab_namespace": hit_data.get("gitlab_namespace", service),
                "ref": hit_data.get("ref"),
            }
            if service and service not in state["hits"]:
                state["hits"][service] = hit
                state["tasks"][service] = asyncio.create_task(
                    fix_hit(hit, state["intel"], state["trace_id"], state["client"])
                )

    return {"ok": True}
