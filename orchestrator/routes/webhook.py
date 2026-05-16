from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class WebhookPayload(BaseModel):
    pr_id: str
    repo: str | None = None
    diff: str | None = None


@router.post("/webhook", status_code=202)
async def webhook(payload: WebhookPayload):
    return {"status": "accepted", "pr_id": payload.pr_id}
