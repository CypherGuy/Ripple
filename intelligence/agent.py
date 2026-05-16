import os
import json
from google import genai


def _gemini_client():
    if os.environ.get("GEMINI_API_KEY"):
        return genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="us-central1")


def call_gemini(prompt: str) -> tuple[str, int, str]:
    client = _gemini_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = response.text.strip()
    try:
        parsed = json.loads(text)
        return parsed["pattern"], int(parsed["risk_score"]), parsed["risk_rationale"]
    except Exception:
        return text, 5, "Could not parse structured response."


def extract_pattern(
    diff: str,
    incidents: list[dict],
    _gemini_fn=None,
) -> dict:
    if _gemini_fn is None:
        _gemini_fn = call_gemini

    incident_context = incidents[0] if incidents else {}
    duration = incident_context.get("duration_minutes", 0)
    cost = incident_context.get("estimated_cost", "unknown")

    prompt = f"""You are a code review expert. Analyse this PR diff and the production incident history below.

PR DIFF:
{diff}

PRODUCTION INCIDENTS:
{json.dumps(incidents, indent=2)}

Return a JSON object with exactly these fields:
- pattern: a concise natural language description of the dangerous semantic pattern in the diff
- risk_score: integer 1-10 based on incident severity (47+ min outage = 9, cost over £20k = +1)
- risk_rationale: one sentence explaining the score referencing the incident ID

Respond with only the JSON object, no markdown."""

    pattern, risk_score, risk_rationale = _gemini_fn(prompt)

    if duration >= 47:
        risk_score = max(risk_score, 9)

    return {
        "pattern": pattern,
        "risk_score": risk_score,
        "risk_rationale": risk_rationale,
        "incident_context": incident_context,
        "previous_scans": [],
    }
