import os
import time
import uuid
from fastapi import APIRouter, Header, HTTPException
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
