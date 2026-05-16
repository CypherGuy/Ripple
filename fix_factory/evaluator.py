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


_MISSING_ROOT_CAUSE = {"", "no summary provided.", "no summary provided", "none"}


def _root_cause_missing(ctx: dict) -> bool:
    summary = ctx.get("root_cause_summary", "").strip().lower()
    return not summary or summary in _MISSING_ROOT_CAUSE


def evaluate_fix(hit: dict, patch: str, _gemini_fn=None) -> dict:
    if _gemini_fn is None:
        _gemini_fn = _default_gemini

    ctx = hit.get("incident_context", {})
    lines = hit.get("matching_lines", [])

    if _root_cause_missing(ctx):
        prompt = f"""You are a senior engineer evaluating a code fix on technical merit.
No incident root cause is available.

ORIGINAL CODE:
{lines}

PROPOSED FIX:
{patch}

CRITICAL CONSTRAINTS — the fix must satisfy ALL of the following to pass:
1. The fix must only modify an HTTP client function call (requests.get, requests.post, requests.put,
   requests.delete, httpx.get, httpx.post, httpx.put, urllib.request.urlopen, etc.)
2. The fix must add timeout=N as a keyword argument to that HTTP function call
3. The fix must NOT change any variable type (e.g. string to dict, string to tuple)
4. The fix must NOT modify variable assignments, constants, class definitions, or configuration lines
5. If any of the above constraints are violated, return passed: false

A fix that adds timeout=5 to an HTTP call with no timeout satisfies all constraints.
Return JSON: {{"passed": true/false, "rationale": "one sentence on technical merit"}}

Respond with only the JSON object."""
        evaluated_on = "technical_merit"
    else:
        prompt = f"""You are a senior engineer evaluating whether a code fix would have prevented a production incident.

ORIGINAL FAILING CODE:
{lines}

PROPOSED PATCH:
{patch}

INCIDENT ROOT CAUSE:
{ctx.get("root_cause_summary")}
Incident: {ctx.get("incident_id", "unknown")} — {ctx.get("duration_minutes", "?")} min outage.

Does this patch directly fix the root cause? Return JSON:
{{"passed": true/false, "rationale": "one sentence explaining why"}}

Respond with only the JSON object."""
        evaluated_on = "incident_context"

    raw = _gemini_fn(prompt)
    try:
        result = json.loads(raw)
        return {
            "passed": bool(result.get("passed")),
            "rationale": result.get("rationale", ""),
            "evaluated_on": evaluated_on,
        }
    except Exception:
        return {"passed": False, "rationale": "Could not parse evaluator response.", "evaluated_on": evaluated_on}
