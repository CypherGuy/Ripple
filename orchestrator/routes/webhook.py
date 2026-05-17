import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from orchestrator.pipeline import run_pipeline

router = APIRouter()


class WebhookPayload(BaseModel):
    pr_id: str
    repo: str | None = None
    diff: str | None = None
    incident_context: dict | None = None


@router.post("/webhook", status_code=202)
async def webhook(payload: WebhookPayload):
    trace_id = str(uuid.uuid4())
    fix_results = await run_pipeline(payload.model_dump(), trace_id)
    return {"status": "accepted", "pr_id": payload.pr_id, "fix_results": fix_results}
