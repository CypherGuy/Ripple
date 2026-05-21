import os
import time
import uuid
from fastapi import APIRouter, HTTPException
from orchestrator.pipeline import run_pipeline

router = APIRouter()

_COOLDOWN_SECONDS = 60
_last_trigger_time: float | None = None

_DEMO_PAYLOAD = {
    "pr_id": "demo-run",
    "repo": "cypherguy-group/pulsecheck/ssl-monitor",
    "diff": "@@ -12 +12 @@ response = httpx.get(target_url)",
    "incident_context": {
        "incident_id": "P-26051",
        "duration_minutes": 47,
        "estimated_cost": "£23,000",
        "root_cause_summary": "PulseCheck ssl-monitor hung on slow cert check",
    },
}


@router.post("/demo/trigger", status_code=202)
async def trigger_demo():
    """Intentionally public endpoint that fires the PulseCheck demo pipeline.
    Rate-limited to one trigger per 60 seconds to prevent cost abuse.
    The webhook secret stays server-side - no secret is exposed in the client bundle."""
    global _last_trigger_time
    now = time.time()
    if _last_trigger_time is not None and (now - _last_trigger_time) < _COOLDOWN_SECONDS:
        remaining = int(_COOLDOWN_SECONDS - (now - _last_trigger_time))
        raise HTTPException(
            status_code=429,
            detail=f"Demo cooldown active. Try again in {remaining}s.",
        )
    _last_trigger_time = now
    trace_id = str(uuid.uuid4())
    fix_results = await run_pipeline(_DEMO_PAYLOAD.copy(), trace_id)
    return {"status": "accepted", "pr_id": _DEMO_PAYLOAD["pr_id"], "fix_results": fix_results}


async def close_all_mrs() -> None:
    """Close all open Ripple MRs before firing the pipeline.
    Ensures a judge always sees a fresh run without stale MRs from a previous demo."""
    from orchestrator.routes.admin import close_all_ripple_mrs
    from orchestrator.pipeline import get_service_list
    import asyncio
    token = os.environ.get("GITLAB_TOKEN", "")
    if not token:
        return
    try:
        services = get_service_list()
        namespaces = [s["gitlab_namespace"] for s in services]
        await asyncio.to_thread(close_all_ripple_mrs, namespaces, token)
    except Exception:
        pass  # Never block the demo over a close failure
