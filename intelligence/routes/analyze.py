import os
from fastapi import APIRouter
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from intelligence.tools.dynatrace import fetch_incident_history
from intelligence.tools.mongodb import find_similar_wins, find_similar_scars
from intelligence.agent import extract_pattern

load_dotenv()
router = APIRouter()


class AnalyzePayload(BaseModel):
    pr_id: str
    repo: str | None = None
    diff: str = Field(max_length=65536)
    incident_context: dict | None = None


@router.post("/analyze")
async def analyze(payload: AnalyzePayload):
    env = os.environ["DT_ENVIRONMENT"]
    token = os.environ["DT_PLATFORM_TOKEN"]

    incidents = fetch_incident_history(env, token, payload.diff)

    # When Dynatrace returns no incidents but the webhook supplied incident_context,
    # use it as a synthetic incident so the severity floor fires correctly.
    # Without this, a thin demo diff returns incidents=[] and the floor never applies.
    if not incidents and payload.incident_context:
        incidents = [payload.incident_context]

    result = extract_pattern(payload.diff, incidents)

    wins = find_similar_wins(result["pattern"])
    scars = find_similar_scars(result["pattern"])

    adjustment = sum(w.get("confidence_boost", 0) for w in wins)
    adjustment += sum(s.get("risk_adjustment", 0) for s in scars)
    result["risk_score"] = max(1, min(10, result["risk_score"] + adjustment))
    result["previous_scans"] = wins + scars

    return result
