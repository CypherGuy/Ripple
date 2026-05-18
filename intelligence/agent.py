import os
import re
import json
import uuid
from google import genai
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types


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


def _dt_fetch_incidents(diff: str) -> list[dict]:
    """Query Dynatrace MCP for production incidents matching the code pattern in this diff."""
    from intelligence.tools.dynatrace import fetch_incident_history
    env = os.environ.get("DT_ENVIRONMENT", "")
    token = os.environ.get("DT_PLATFORM_TOKEN", "")
    if not env or not token:
        return []
    return fetch_incident_history(env, token, diff)


def call_gemini_adk(prompt: str) -> tuple[str, int, str]:
    """Run pattern extraction via an ADK LlmAgent with a Dynatrace FunctionTool.

    The prompt contains only the raw diff. The agent decides whether to call
    _dt_fetch_incidents to retrieve Dynatrace incident history — this is genuine
    agentic tool use, not decorative. If the diff looks dangerous, the agent calls
    the tool; the tool queries the Dynatrace MCP and returns real incident records
    which the agent uses to ground its risk score and rationale.
    """
    agent = LlmAgent(
        name="ripple_pattern_extractor",
        model="gemini-2.5-flash",
        instruction=(
            "You are a code review expert that extracts dangerous semantic patterns "
            "from PR diffs, grounded in real production incident history. "
            "A Dynatrace MCP tool is available if you need to check whether this pattern "
            "has caused production incidents. "
            "Respond with a JSON object containing exactly: "
            "pattern (string describing the dangerous semantic pattern), "
            "risk_score (integer 1-10 based on pattern severity; Ripple will apply duration and cost scaling on top of your score), "
            "risk_rationale (one sentence citing the incident ID if one was found). "
            "No markdown, no extra fields."
        ),
        tools=[FunctionTool(_dt_fetch_incidents)],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="ripple-intelligence",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    session = session_service._create_session_impl(
        app_name="ripple-intelligence",
        user_id="system",
        session_id=str(uuid.uuid4()),
    )

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    text = ""
    for event in runner.run(user_id="system", session_id=session.id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text.strip()
            break

    try:
        parsed = json.loads(text)
        return parsed["pattern"], int(parsed["risk_score"]), parsed["risk_rationale"]
    except Exception:
        return text, 5, "Could not parse structured response."


def _parse_cost(cost_str: str) -> int:
    """Extract integer cost from strings like '£23,000' or '$5000'. Returns 0 if unparseable."""
    digits = re.sub(r'[^\d]', '', str(cost_str))
    return int(digits) if digits else 0


def _severity_adjustment(duration: int, cost_str: str) -> tuple[int, int]:
    """Return (floor, boost) based on incident duration and estimated cost.

    floor — minimum risk_score this incident warrants regardless of Gemini's score
    boost — additive points on top of Gemini's score
    """
    if duration >= 120:
        floor = 10
    elif duration >= 60:
        floor = 9
    elif duration >= 30:
        floor = 8
    elif duration >= 10:
        floor = 6
    else:
        floor = 0

    cost = _parse_cost(cost_str)
    if cost >= 50_000:
        boost = 3
    elif cost >= 10_000:
        boost = 2
    elif cost >= 1_000:
        boost = 1
    else:
        boost = 0

    return floor, boost


def extract_pattern(
    diff: str,
    incidents: list[dict],
    _gemini_fn=None,
) -> dict:
    if _gemini_fn is None:
        _gemini_fn = call_gemini_adk

    incident_context = incidents[0] if incidents else {}
    duration = incident_context.get("duration_minutes", 0)
    cost = incident_context.get("estimated_cost", "unknown")

    if _gemini_fn is call_gemini_adk:
        # ADK path: send only the raw diff. The LlmAgent calls _dt_fetch_incidents
        # via FunctionTool to retrieve Dynatrace incident history itself — genuine tool use.
        adk_prompt = f"Analyse this PR diff for dangerous patterns:\n\n{diff}"
        pattern, risk_score, risk_rationale = _gemini_fn(adk_prompt)
    else:
        # Non-ADK / test path: include pre-fetched incidents in the prompt.
        prompt = f"""You are a code review expert. Analyse this PR diff and the production incident history below.

PR DIFF:
{diff}

PRODUCTION INCIDENTS:
{json.dumps(incidents, indent=2)}

Return a JSON object with exactly these fields:
- pattern: a concise natural language description of the dangerous semantic pattern in the diff
- risk_score: integer 1-10 based on pattern severity (Ripple applies duration and cost scaling separately)
- risk_rationale: one sentence explaining the score referencing the incident ID

Respond with only the JSON object, no markdown."""
        pattern, risk_score, risk_rationale = _gemini_fn(prompt)

    floor, boost = _severity_adjustment(duration, cost)
    risk_score = risk_score + boost
    if floor > 0:
        risk_score = max(risk_score, floor)
    risk_score = max(1, min(10, risk_score))

    return {
        "pattern": pattern,
        "risk_score": risk_score,
        "risk_rationale": risk_rationale,
        "incident_context": incident_context,
        "previous_scans": [],
    }
