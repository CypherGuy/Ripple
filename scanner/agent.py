import json
import os
from google import genai
from scanner.tools.gitlab import read_service_files


def _gemini_client():
    if os.environ.get("GEMINI_API_KEY"):
        return genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location="us-central1")


def _default_gemini(prompt: str) -> list[dict]:
    client = _gemini_client()
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return []


def scan_service(
    service: dict,
    pattern: str,
    incident_context: dict,
    _files_override: dict | None = None,
    _gemini_fn=None,
) -> list[dict]:
    if _gemini_fn is None:
        _gemini_fn = _default_gemini

    token = os.environ.get("GITLAB_TOKEN", "")
    files = read_service_files(service["gitlab_namespace"], token, _files_override=_files_override)

    if not files:
        return []

    files_text = "\n\n".join(f"=== {path} ===\n{content}" for path, content in files.items())

    prompt = f"""You are a code reviewer scanning for dangerous patterns.

PATTERN TO FIND: {pattern}

IMPORTANT: Match the semantic risk, not the exact wording. For example, "HTTP call with no timeout"
means any HTTP request (requests.get, httpx.get, urllib, etc.) that does not pass a timeout parameter.
The function does not need to be async — synchronous functions are equally dangerous.

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
