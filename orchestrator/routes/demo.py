import uuid
from fastapi import APIRouter
from orchestrator.pipeline import run_pipeline

router = APIRouter()

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
    The webhook secret stays server-side — the dashboard button calls this
    instead of /webhook directly, so no secret is exposed in the client bundle."""
    trace_id = str(uuid.uuid4())
    fix_results = await run_pipeline(_DEMO_PAYLOAD.copy(), trace_id)
    return {"status": "accepted", "pr_id": _DEMO_PAYLOAD["pr_id"], "fix_results": fix_results}
