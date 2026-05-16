import os
from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from intelligence.tools.dynatrace import fetch_incident_history
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
    return result
