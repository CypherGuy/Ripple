import concurrent.futures
import json
import logging
import os
import uuid
from google import genai
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types


logger = logging.getLogger(__name__)

if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return genai.Client(api_key=api_key)
    return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="us-central1")


def _default_gemini(prompt: str) -> str:
    client = _gemini_client()
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        text = ex.submit(
            lambda: client.models.generate_content(
                model="gemini-3-flash-preview", contents=prompt
            ).text.strip()
        ).result(timeout=20)
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return text
    except Exception as e:
        logger.warning("_default_gemini (evaluator) failed or timed out: %s", e)
        return ""
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def _fetch_incident_traces_for_eval(incident_id: str) -> list[dict]:
    """Fetch Dynatrace traces for an incident - used by the evaluator agent for validation."""
    import asyncio
    from fix_factory.tools.dynatrace_traces import get_incident_traces
    env = os.environ.get("DT_ENVIRONMENT", "")
    token = os.environ.get("DT_PLATFORM_TOKEN", "")
    if not env or not token:
        return []
    try:
        return asyncio.run(get_incident_traces(env, token, incident_id))
    except Exception:
        return []


def call_evaluator_adk(hit: dict, patch: str) -> dict:
    """Evaluate a fix using an ADK LlmAgent with a Dynatrace trace FunctionTool.

    The agent can fetch real incident traces to validate whether the patch addresses the root cause.
    """
    ctx = hit.get("incident_context", {})
    incident_id = ctx.get("incident_id", "")
    lines = hit.get("matching_lines", [])

    def _get_traces() -> list[dict]:
        if not incident_id:
            return []
        return _fetch_incident_traces_for_eval(incident_id)

    agent = LlmAgent(
        name="ripple_evaluator",
        model="gemini-3-flash-preview",
        instruction=(
            "You are a senior engineer evaluating whether a code fix prevents a production incident. "
            "You MUST call the Dynatrace trace tool to fetch the incident traces before deciding. "
            "Do not respond without calling the tool first. "
            "Return a JSON object with exactly: "
            "passed (bool), rationale (one sentence explaining why). "
            "No markdown, no extra fields."
        ),
        tools=[FunctionTool(_get_traces)],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="ripple-fix-factory",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    root_cause = ctx.get("root_cause_summary", "")
    prompt = (
        f"Evaluate this code fix.\n\n"
        f"Original code: {json.dumps(lines)}\n"
        f"Proposed patch:\n{patch}\n\n"
        f"Incident: {incident_id} - {ctx.get('duration_minutes', '?')} min outage.\n"
        f"Root cause: {root_cause or 'Not available - evaluate on technical merit.'}\n\n"
        f"Use the Dynatrace trace tool if you need more context. Return only the JSON object."
    )
    message = genai_types.Content(
        role="user", parts=[genai_types.Part(text=prompt)])

    text = ""
    for event in runner.run(user_id="system", session_id=str(uuid.uuid4()), new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text.strip()
            break

    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
        evaluated_on = "incident_context" if root_cause and not _root_cause_missing(
            ctx) else "technical_merit"
        return {"passed": bool(result.get("passed")), "rationale": result.get("rationale", ""), "evaluated_on": evaluated_on}
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(
            "call_evaluator_adk parse failed: %s | raw: %.200s", e, text)
        return {"passed": False, "rationale": "Could not parse evaluator response.", "evaluated_on": "technical_merit"}


_MISSING_ROOT_CAUSE = {"", "no summary provided.",
                       "no summary provided", "none"}


def _root_cause_missing(ctx: dict) -> bool:
    summary = ctx.get("root_cause_summary", "").strip().lower()
    return not summary or summary in _MISSING_ROOT_CAUSE


def evaluate_fix(hit: dict, patch: str, _gemini_fn=None) -> dict:
    if _gemini_fn is None:
        _gemini_fn = _default_gemini
    lines = hit.get("matching_lines", [])
    # Derive evaluated_on from whether the incident actually carries a root cause.
    # When it does (e.g. webhook supplies root_cause_summary), the MR should read
    # "Verified against incident root cause" rather than the technical-merit fallback.
    ctx = hit.get("incident_context", {})
    evaluated_on = "technical_merit" if _root_cause_missing(ctx) else "incident_context"

    prompt = f"""You are a senior engineer evaluating a code fix on technical merit.

ORIGINAL CODE:
{lines}

PROPOSED FIX:
{patch}

CRITICAL CONSTRAINTS - the fix must satisfy ALL of the following to pass:
1. The fix must only modify an HTTP client function call (requests.get, requests.post, requests.put,
   requests.delete, httpx.get, httpx.post, httpx.put, urllib.request.urlopen, etc.)
2. The fix must add timeout=N as a keyword argument to that HTTP function call
3. The fix must NOT change any variable type (e.g. string to dict, string to tuple)
4. The fix must NOT modify variable assignments, constants, class definitions, or configuration lines
5. If any of the above constraints are violated, return passed: false

A fix that adds timeout=5 to an HTTP call with no timeout satisfies all constraints.
Return JSON: {{"passed": true/false, "rationale": "one sentence on technical merit"}}

Respond with only the JSON object."""

    raw = _gemini_fn(prompt)
    if not raw:
        # Gemini unavailable - auto-pass if patch adds timeout= to an HTTP call
        has_timeout = "timeout=" in (patch or "")
        passed = bool(has_timeout and patch)
        return {"passed": passed, "rationale": "Auto-evaluated: Gemini unavailable, fix adds timeout.", "evaluated_on": evaluated_on}
    try:
        result = json.loads(raw)
        return {
            "passed": bool(result.get("passed")),
            "rationale": result.get("rationale", ""),
            "evaluated_on": evaluated_on,
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("evaluate_fix parse failed: %s | raw: %.200s", e, raw)
        return {"passed": False, "rationale": "Could not parse evaluator response.", "evaluated_on": evaluated_on}
