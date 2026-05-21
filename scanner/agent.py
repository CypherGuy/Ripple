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
from opentelemetry import trace
from scanner.tools.gitlab import read_service_files

try:
    from shared.otel_setup import setup_tracer
    _tracer = setup_tracer("scanner")
except Exception:
    _tracer = trace.get_tracer("ripple.scanner")

logger = logging.getLogger(__name__)

if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return genai.Client(api_key=api_key)
    return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="us-central1")


def _default_gemini(prompt: str) -> list[dict]:
    client = _gemini_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return []


def _fetch_service_files(gitlab_namespace: str) -> dict:
    """Read Python source files from a GitLab repository for the scanner agent."""
    token = os.environ.get("GITLAB_TOKEN", "")
    return read_service_files(gitlab_namespace, token)


def call_scanner_adk(service: dict, pattern: str) -> list[dict]:
    """Scan a service for a dangerous pattern using an ADK LlmAgent with a GitLab FunctionTool.

    The agent decides whether to fetch files and how to identify hits - genuine agentic tool use.
    """
    agent = LlmAgent(
        name="ripple_scanner",
        model="gemini-2.5-flash",
        instruction=(
            "You are a code scanner hunting for dangerous patterns in a GitLab repository. "
            "You MUST call the file-reading tool first to fetch the source files before you can answer. "
            "Do not respond without calling the tool. "
            "IMPORTANT: Match the semantic risk, not the exact wording. "
            "For HTTP timeout patterns: flag ANY HTTP call (requests.get, requests.post, requests.put, "
            "requests.delete, httpx.get, httpx.post, httpx.put, urllib.request.urlopen, etc.) "
            "that does NOT pass a timeout argument. Do NOT flag calls that already have timeout=. "
            "Return a JSON array of hits. Each hit: "
            "file_path (string), matching_lines ([{line_number, content}]), confidence (float 0-1). "
            "Return [] if no hits. Respond with only the JSON array, no markdown."
        ),
        tools=[FunctionTool(_fetch_service_files)],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="ripple-scanner",
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
    )

    prompt = (
        f"Scan the GitLab repository '{service['gitlab_namespace']}' for this dangerous pattern:\n\n"
        f"{pattern}\n\n"
        "Use the file-reading tool to fetch the source files, then return all hits as a JSON array."
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
        return json.loads(text) or []
    except Exception:
        return []


def scan_service(
    service: dict,
    pattern: str,
    incident_context: dict,
    _files_override: dict | None = None,
    _gemini_fn=None,
) -> list[dict]:
    with _tracer.start_as_current_span("ripple.scanner.scan_service") as span:
        span.set_attribute("service.name", service.get("name", ""))

        if _gemini_fn is None:
            # ADK path with 25s hard cap. If ADK finds hits, return immediately.
            # If ADK times out or returns 0, fall through to direct Gemini scan.
            # Use executor without `with` - `with` calls shutdown(wait=True) on exit,
            # which blocks until the ADK thread finishes and defeats the timeout.
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                hits = ex.submit(call_scanner_adk, service,
                                 pattern).result(timeout=25)
            except Exception:
                hits = []
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
            if hits:
                span.set_attribute("files.count", -1)
                span.set_attribute("hits.count", len(hits))
                span.set_attribute("hit.found", True)
                return hits
            _gemini_fn = _default_gemini

        token = os.environ.get("GITLAB_TOKEN", "")
        files = read_service_files(
            service["gitlab_namespace"], token, _files_override=_files_override)

        if not files:
            return []

        files_text = "\n\n".join(
            f"=== {path} ===\n{content}" for path, content in files.items())

        span.set_attribute("files.count", len(files))
        hits = _scan_with_gemini(files_text, pattern, _gemini_fn)
        span.set_attribute("hits.count", len(hits))
        span.set_attribute("hit.found", len(hits) > 0)
    return hits


def _scan_with_gemini(files_text: str, pattern: str, _gemini_fn) -> list[dict]:
    prompt = f"""You are a code reviewer scanning for dangerous patterns.

PATTERN TO FIND: {pattern}

IMPORTANT: Match the semantic risk, not the exact wording. For example, "HTTP call with no timeout"
means any HTTP request (requests.get, httpx.get, urllib, etc.) that does not pass a timeout parameter.
The function does not need to be async - synchronous functions are equally dangerous.

Do NOT flag HTTP calls that already pass a timeout argument (e.g. timeout=5, timeout=DEFAULT_TIMEOUT,
timeout=(connect, read)). Only flag calls where timeout is completely absent.

FILES:
{files_text[:8000]}

Return a JSON array of hits. Each hit must have:
  "file_path": string,
  "matching_lines": [{{"line_number": int, "content": string}}],
  "confidence": float 0-1

Return [] if no hits found. Respond with only the JSON array."""

    return _gemini_fn(prompt)
