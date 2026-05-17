import os
import uuid
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from orchestrator.pipeline import run_pipeline

router = APIRouter()


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
    secret = os.environ.get("GITLAB_WEBHOOK_SECRET", "")
    if secret and x_gitlab_token != secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    trace_id = str(uuid.uuid4())
    fix_results = await run_pipeline(payload.model_dump(), trace_id)
    return {"status": "accepted", "pr_id": payload.pr_id, "fix_results": fix_results}
