import os
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from fix_factory.tools.mongodb_outcomes import record_feedback, _get_col

router = APIRouter()


class FeedbackPayload(BaseModel):
    service: str
    mr_url: str
    outcome: str  # "merged" or "rejected"
    reason: str = ""


def get_pattern_for_mr(mr_url: str) -> str:
    """Look up the pattern from the stored outcome for this MR URL."""
    try:
        col = _get_col()
        doc = col.find_one({"mr_url": mr_url}, {"_id": 0, "pattern": 1})
        if doc:
            return doc.get("pattern", "")
    except Exception:
        pass
    return ""


@router.post("/admin/feedback")
async def submit_feedback(
    payload: FeedbackPayload,
    x_admin_secret: str | None = Header(default=None),
):
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    if payload.outcome not in ("merged", "rejected"):
        raise HTTPException(status_code=422, detail="outcome must be 'merged' or 'rejected'")

    pattern = get_pattern_for_mr(payload.mr_url)
    record_feedback(
        service=payload.service,
        mr_url=payload.mr_url,
        outcome=payload.outcome,
        pattern=pattern,
        reason=payload.reason,
    )
    return {"recorded": True, "service": payload.service, "outcome": payload.outcome}
