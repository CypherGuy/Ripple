import logging
import os
from fastapi import APIRouter
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from intelligence.tools.dynatrace import fetch_incident_history
from intelligence.tools.mongodb import find_similar_wins, find_similar_scars
from intelligence.agent import extract_pattern

load_dotenv()
router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzePayload(BaseModel):
    pr_id: str
    repo: str | None = None
    diff: str = Field(max_length=65536)
    incident_context: dict | None = None


@router.post("/analyze")
async def analyze(payload: AnalyzePayload):
    env = os.environ["DT_ENVIRONMENT"]
    token = os.environ["DT_PLATFORM_TOKEN"]

    try:
        incidents = fetch_incident_history(env, token, payload.diff)
    except Exception as e:
        logger.error("fetch_incident_history failed (env=%s): %s", env, e, exc_info=True)
        incidents = []

    result = extract_pattern(payload.diff, incidents)

    wins = find_similar_wins(result["pattern"])
    scars = find_similar_scars(result["pattern"])

    adjustment = sum(w.get("confidence_boost", 0) for w in wins)
    adjustment += sum(s.get("risk_adjustment", 0) for s in scars)
    result["risk_score"] = max(1, min(10, result["risk_score"] + adjustment))
    result["previous_scans"] = wins + scars

    return result
