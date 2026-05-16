import os
from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv
from fix_factory.tools.dynatrace_traces import get_incident_traces
from fix_factory.tools.gitlab_history import get_fix_precedents
from fix_factory.agent import generate_fix

load_dotenv()
router = APIRouter()


class MatchingLine(BaseModel):
    line_number: int
    content: str


class FixPayload(BaseModel):
    service: str
    file_path: str
    matching_lines: list[MatchingLine]
    incident_context: dict
    per_service_history: list[dict] = []


@router.post("/fix")
async def fix(payload: FixPayload):
    env = os.environ["DT_ENVIRONMENT"]
    dt_token = os.environ["DT_PLATFORM_TOKEN"]
    gl_token = os.environ["GITLAB_TOKEN"]

    incident_id = payload.incident_context.get("incident_id", "")
    traces = get_incident_traces(env, dt_token, incident_id)
    precedents = get_fix_precedents(payload.service, gl_token)

    return generate_fix(payload.model_dump(), traces, precedents)
