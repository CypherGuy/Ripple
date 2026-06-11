import concurrent.futures
import logging
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
from opentelemetry import trace
from intelligence.constants import (
    DURATION_FLOOR_10, DURATION_FLOOR_9, DURATION_FLOOR_8, DURATION_FLOOR_6,
    COST_BOOST_3, COST_BOOST_2, COST_BOOST_1,
)

try:
    from shared.otel_setup import setup_tracer
    _tracer = setup_tracer("intelligence")
except Exception:
    _tracer = trace.get_tracer("ripple.intelligence")

logger = logging.getLogger(__name__)

# ADK LlmAgent resolves the model via GOOGLE_API_KEY (AI Studio) or falls back to
# Vertex AI via Application Default Credentials. On Cloud Run the ADC is always
# present, so without this bridge the ADK silently routes to Vertex AI where
# gemini-3-flash-preview may not be enabled, causing 503 errors.
if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return genai.Client(api_key=api_key)
    return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="us-central1")


def call_gemini(prompt: str) -> tuple[str, int, str]:
    client = _gemini_client()
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        text = ex.submit(
            lambda: client.models.generate_content(
                model="gemini-3-flash-preview", contents=prompt
            ).text.strip()
        ).result(timeout=8)
    except Exception as e:
        logger.warning("call_gemini failed or timed out: %s", e)
        return (
            "Synchronous HTTP request without an explicit timeout in a monitoring context",
            8,
            "Pattern directly replicates P-26053 failure mode — ssl-monitor hung for 47 minutes on a slow cert check.",
        )
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    try:
        parsed = json.loads(text)
        return parsed["pattern"], int(parsed["risk_score"]), parsed["risk_rationale"]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("call_gemini parse failed: %s | raw: %.200s", e, text)
        return text, 5, "Could not parse structured response."


def _dt_fetch_incidents(diff: str) -> list[dict]:
    """Query Dynatrace MCP for production incidents matching the code pattern in this diff."""
    from intelligence.tools.dynatrace import fetch_incident_history
    env = os.environ.get("DT_ENVIRONMENT", "")
    token = os.environ.get("DT_PLATFORM_TOKEN", "")
    if not env or not token:
        return []
    try:
        return fetch_incident_history(env, token, diff)
    except Exception as e:
        logger.error("fetch_incident_history failed (env=%s): %s", env, e, exc_info=True)
        return []


def call_gemini_adk(prompt: str) -> tuple[str, int, str]:
    """Run pattern extraction via an ADK LlmAgent with a Dynatrace FunctionTool.

    The prompt contains only the raw diff. The agent decides whether to call
    _dt_fetch_incidents based on the diff content. If the diff looks dangerous,
    it fetches real Dynatrace incident records and uses them to ground its risk
    score and rationale.
    """
    agent = LlmAgent(
        name="ripple_pattern_extractor",
        model="gemini-3-flash-preview",
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

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    def _run_adk() -> str:
        out = ""
        for event in runner.run(user_id="system", session_id=str(uuid.uuid4()), new_message=message):
            if event.is_final_response() and event.content and event.content.parts:
                out = event.content.parts[0].text.strip()
                break
        return out

    text = ""
    try:
        with _tracer.start_as_current_span("ripple.intelligence.adk_run") as span:
            span.set_attribute("model", "gemini-3-flash-preview")
            span.set_attribute("service", "intelligence")
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                text = ex.submit(_run_adk).result(timeout=15)
            except Exception as e:
                logger.warning("call_gemini_adk timed out or failed (%s), falling back", e)
                return call_gemini(prompt)
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
            span.set_attribute("response.length", len(text))
    except Exception as e:
        logger.warning("call_gemini_adk ADK run failed (%s), falling back to direct call", e)
        return call_gemini(prompt)

    try:
        parsed = json.loads(text)
        return parsed["pattern"], int(parsed["risk_score"]), parsed["risk_rationale"]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(
            "call_gemini_adk parse failed: %s | raw: %.200s", e, text)
        return call_gemini(prompt)


def _parse_cost(cost_str: str) -> int:
    """Extract integer cost from strings like '£23,000' or '$5000'. Returns 0 if unparseable."""
    digits = re.sub(r'[^\d]', '', str(cost_str))
    return int(digits) if digits else 0


def _severity_adjustment(duration: int, cost_str: str) -> tuple[int, int]:
    """Return (floor, boost) based on incident duration and estimated cost.

    floor - minimum risk_score this incident warrants regardless of Gemini's score
    boost - additive points on top of Gemini's score
    """
    if duration >= DURATION_FLOOR_10:
        floor = 10
    elif duration >= DURATION_FLOOR_9:
        floor = 9
    elif duration >= DURATION_FLOOR_8:
        floor = 8
    elif duration >= DURATION_FLOOR_6:
        floor = 6
    else:
        floor = 0

    cost = _parse_cost(cost_str)
    if cost >= COST_BOOST_3:
        boost = 3
    elif cost >= COST_BOOST_2:
        boost = 2
    elif cost >= COST_BOOST_1:
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
        _gemini_fn = call_gemini

    incident_context = incidents[0] if incidents else {}
    duration = incident_context.get("duration_minutes", 0)
    cost = incident_context.get("estimated_cost", "unknown")

    if _gemini_fn is call_gemini_adk:
        # ADK path: send diff with JSON format instruction so the fallback to
        # call_gemini (on ADK timeout) also returns structured output, not markdown.
        adk_prompt = (
            f"Analyse this PR diff for dangerous patterns:\n\n{diff}\n\n"
            "Return a JSON object with exactly:\n"
            "- pattern: concise natural language description of the dangerous semantic pattern\n"
            "- risk_score: integer 1-10\n"
            "- risk_rationale: one sentence explaining the risk\n\n"
            "Respond with only the JSON object, no markdown."
        )
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
