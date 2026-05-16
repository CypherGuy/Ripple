import json
import os
from google import genai


def _gemini_client():
    if os.environ.get("GEMINI_API_KEY"):
        return genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="us-central1")


def _default_gemini(prompt: str) -> str:
    client = _gemini_client()
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return text


def evaluate_fix(hit: dict, patch: str, _gemini_fn=None) -> dict:
    if _gemini_fn is None:
        _gemini_fn = _default_gemini

    ctx = hit.get("incident_context", {})
    lines = hit.get("matching_lines", [])

    prompt = f"""You are a senior engineer evaluating whether a code fix would have prevented a production incident.

ORIGINAL FAILING CODE:
{lines}

PROPOSED PATCH:
{patch}

INCIDENT ROOT CAUSE:
{ctx.get("root_cause_summary", "No summary provided.")}
Incident: {ctx.get("incident_id", "unknown")} — {ctx.get("duration_minutes", "?")} min outage.

Does this patch directly fix the root cause? Return JSON:
{{"passed": true/false, "rationale": "one sentence explaining why"}}

Respond with only the JSON object."""

    raw = _gemini_fn(prompt)
    try:
        result = json.loads(raw)
        return {"passed": bool(result.get("passed")), "rationale": result.get("rationale", "")}
    except Exception:
        return {"passed": False, "rationale": "Could not parse evaluator response."}
