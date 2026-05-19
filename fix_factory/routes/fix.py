import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fix_factory.tools.dynatrace_traces import get_incident_traces
from fix_factory.tools.gitlab_history import get_fix_precedents
from fix_factory.agent import run_with_correction

load_dotenv()
router = APIRouter()

_KNOWN_SERVICES = {
    "http-monitor", "ssl-monitor", "api-monitor", "github-monitor",
    "dns-checker", "latency-monitor", "slack-notifier", "email-notifier",
    "webhook-dispatcher", "incident-manager", "metrics-collector", "report-generator",
    # ripple-demo services kept for backward compat
    "payment-service", "auth-service", "order-service", "notification-service",
    "inventory-service", "billing-service", "reporting-service", "gateway-service",
    "user-service", "search-service", "analytics-service", "recommendation-service",
    "config-service", "audit-service", "session-service", "webhook-service",
    "cache-service", "scheduler-service", "export-service", "admin-service",
}


class MatchingLine(BaseModel):
    line_number: int
    content: str


class FixPayload(BaseModel):
    service: str
    file_path: str
    matching_lines: list[MatchingLine]
    incident_context: dict
    per_service_history: list[dict] = []


DEMO_NAMESPACE = os.environ.get("DEMO_NAMESPACE", "cypherguy-group/pulsecheck")


@router.post("/fix")
async def fix(payload: FixPayload):
    if payload.service not in _KNOWN_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service: {payload.service!r}")
    env = os.environ["DT_ENVIRONMENT"]
    dt_token = os.environ["DT_PLATFORM_TOKEN"]
    gl_token = os.environ["GITLAB_TOKEN"]
    namespace = f"{DEMO_NAMESPACE}/{payload.service}"

    incident_id = payload.incident_context.get("incident_id", "")
    traces = await get_incident_traces(env, dt_token, incident_id)
    precedents = get_fix_precedents(namespace, gl_token)

    hit = payload.model_dump()
    hit["gitlab_namespace"] = namespace
    return run_with_correction(hit, traces, precedents)
