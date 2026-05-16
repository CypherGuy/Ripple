import os
from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from intelligence.tools.dynatrace import fetch_incident_history
from intelligence.tools.mongodb import find_similar_wins, find_similar_scars
from intelligence.agent import extract_pattern

load_dotenv()
router = APIRouter()


class AnalyzePayload(BaseModel):
    pr_id: str
    repo: str | None = None
    diff: str


@router.post("/analyze")
async def analyze(payload: AnalyzePayload):
    env = os.environ["DT_ENVIRONMENT"]
    token = os.environ["DT_PLATFORM_TOKEN"]

    incidents = fetch_incident_history(env, token, payload.diff)
    result = extract_pattern(payload.diff, incidents)

    wins = find_similar_wins(result["pattern"])
    scars = find_similar_scars(result["pattern"])

    adjustment = sum(w.get("confidence_boost", 0) for w in wins)
    adjustment += sum(s.get("risk_adjustment", 0) for s in scars)
    result["risk_score"] = max(1, min(10, result["risk_score"] + adjustment))
    result["previous_scans"] = wins + scars

    return result
