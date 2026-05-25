import os
import time
import uuid
import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from orchestrator.pipeline import run_pipeline

router = APIRouter()

_COOLDOWN_SECONDS = 30
_last_webhook_time: float | None = None


class WebhookPayload(BaseModel):
    pr_id: str
    repo: str | None = None
    diff: str | None = None
    incident_context: dict | None = None


@router.post("/webhook", status_code=202)
async def webhook(
    payload: WebhookPayload,
    x_gitlab_token: str | None = Header(default=None),
):
    global _last_webhook_time
    secret = os.environ.get("GITLAB_WEBHOOK_SECRET", "")
    if secret and x_gitlab_token != secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    now = time.time()
    if _last_webhook_time is not None and (now - _last_webhook_time) < _COOLDOWN_SECONDS:
        remaining = int(_COOLDOWN_SECONDS - (now - _last_webhook_time))
        raise HTTPException(status_code=429, detail=f"Rate limited. Try again in {remaining}s.")
    _last_webhook_time = now

    trace_id = str(uuid.uuid4())
    fix_results = await run_pipeline(payload.model_dump(), trace_id)
    return {"status": "accepted", "pr_id": payload.pr_id, "fix_results": fix_results}


@router.post("/webhook/gitlab", status_code=202)
async def webhook_gitlab(
    request: Request,
    x_gitlab_token: str | None = Header(default=None),
    x_gitlab_event: str | None = Header(default=None),
):
    global _last_webhook_time

    secret = os.environ.get("GITLAB_WEBHOOK_SECRET", "")
    if secret and x_gitlab_token != secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    if x_gitlab_event != "Merge Request Hook":
        return {"status": "ignored", "reason": "not an MR event"}

    body = await request.json()
    attrs = body.get("object_attributes", {})

    if attrs.get("action") != "open":
        return {"status": "ignored", "reason": f"action={attrs.get('action')}"}

    now = time.time()
    if _last_webhook_time is not None and (now - _last_webhook_time) < _COOLDOWN_SECONDS:
        remaining = int(_COOLDOWN_SECONDS - (now - _last_webhook_time))
        raise HTTPException(status_code=429, detail=f"Rate limited. Try again in {remaining}s.")
    _last_webhook_time = now

    mr_iid = str(attrs.get("iid", "unknown"))
    project = body.get("project", {})
    repo = project.get("path_with_namespace", "")

    diff = None
    token = os.environ.get("GITLAB_TOKEN", "")
    project_id = project.get("id")
    if token and project_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/diffs",
                    headers={"PRIVATE-TOKEN": token},
                )
                if resp.status_code == 200:
                    diffs = resp.json()
                    diff = "\n".join(
                        d.get("diff", "") for d in diffs if d.get("diff")
                    )[:8000]
        except Exception:
            pass

    trace_id = str(uuid.uuid4())
    payload = {
        "pr_id": mr_iid,
        "repo": repo,
        "diff": diff,
        "incident_context": {
            "incident_id": "P-26051",
            "duration_minutes": 47,
            "estimated_cost": "£23,000",
            "root_cause_summary": "PulseCheck ssl-monitor hung on slow cert check",
        },
    }
    fix_results = await run_pipeline(payload, trace_id)
    return {"status": "accepted", "mr_iid": mr_iid, "fix_results": fix_results}
