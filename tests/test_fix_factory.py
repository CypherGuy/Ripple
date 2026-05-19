import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

AUTH_HIT = {
    "service": "auth-service",
    "file_path": "src/clients/downstream.py",
    "matching_lines": [{"line_number": 42, "content": "response = requests.get(url)"}],
    "incident_context": {
        "incident_id": "DT-4821",
        "duration_minutes": 47,
        "estimated_cost": "£23,000",
        "root_cause_summary": "No timeout on HTTP client caused thread pool exhaustion.",
    },
    "per_service_history": [],
}

MOCK_OLD_LINE = "    response = requests.get(url)"
MOCK_NEW_LINE = "    response = requests.get(url, timeout=5)"
MOCK_EXPLANATION = "Added 5s timeout to prevent thread pool exhaustion matching DT-4821 (47-min outage, £23,000)."
MOCK_PATCH = f"-{MOCK_OLD_LINE}\n+{MOCK_NEW_LINE}"


@pytest.fixture
def client():
    from fix_factory.main import app
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "fix_factory"}


def test_generate_fix_returns_patch_with_timeout():
    from fix_factory.agent import generate_fix
    result = generate_fix(
        AUTH_HIT,
        traces=[],
        precedents=[],
        _gemini_fn=lambda _: (MOCK_OLD_LINE, MOCK_NEW_LINE, MOCK_EXPLANATION),
    )
    assert "timeout=" in result["patch"]
    assert "DT-4821" in result["fix_explanation"]


def test_generate_fix_returns_required_keys():
    from fix_factory.agent import generate_fix
    result = generate_fix(
        AUTH_HIT,
        traces=[],
        precedents=[],
        _gemini_fn=lambda _: (MOCK_OLD_LINE, MOCK_NEW_LINE, MOCK_EXPLANATION),
    )
    assert "patch" in result
    assert "old_line" in result
    assert "new_line" in result
    assert "fix_explanation" in result


def test_generate_fix_works_with_empty_context():
    from fix_factory.agent import generate_fix
    hit = {**AUTH_HIT, "per_service_history": [], "incident_context": {"incident_id": "DT-4821"}}
    result = generate_fix(
        hit,
        traces=[],
        precedents=[],
        _gemini_fn=lambda _: (MOCK_OLD_LINE, MOCK_NEW_LINE, MOCK_EXPLANATION),
    )
    assert result["old_line"] != ""
    assert result["new_line"] != ""


def test_post_fix_returns_patch_and_explanation(client):
    with patch("fix_factory.routes.fix.get_incident_traces", return_value=[]), \
         patch("fix_factory.routes.fix.get_fix_precedents", return_value=[]), \
         patch("fix_factory.routes.fix.run_with_correction", return_value={
             "patch": MOCK_PATCH,
             "old_line": MOCK_OLD_LINE,
             "new_line": MOCK_NEW_LINE,
             "fix_explanation": MOCK_EXPLANATION,
             "mr_url": None,
             "self_correction_passed": True,
             "correction_iterations": 1,
             "failure_reason": None,
         }):
        r = client.post("/fix", json=AUTH_HIT)

    assert r.status_code == 200
    body = r.json()
    assert "timeout=" in body["patch"]
    assert "DT-4821" in body["fix_explanation"]


def test_post_fix_rejects_missing_file_path(client):
    bad = {k: v for k, v in AUTH_HIT.items() if k != "file_path"}
    r = client.post("/fix", json=bad)
    assert r.status_code == 422


def test_generate_fix_prompt_uses_incident_id_not_trace_ids():
    from fix_factory.agent import generate_fix
    prompts_seen = []
    def capture(prompt):
        prompts_seen.append(prompt)
        return (MOCK_OLD_LINE, MOCK_NEW_LINE, MOCK_EXPLANATION)
    hit = {**AUTH_HIT, "incident_context": {"incident_id": "P-26051", "root_cause_summary": "ssl-monitor hung"}}
    generate_fix(hit, traces=[], precedents=[], _gemini_fn=capture)
    assert "P-26051" in prompts_seen[0]
    assert "always use the incident ID" in prompts_seen[0].lower() or "incident_id" in prompts_seen[0].lower()


def test_post_fix_rejects_unknown_service(client):
    bad = {**AUTH_HIT, "service": "../../etc/passwd"}
    with patch("fix_factory.routes.fix.get_incident_traces", return_value=[]), \
         patch("fix_factory.routes.fix.get_fix_precedents", return_value=[]):
        r = client.post("/fix", json=bad)
    assert r.status_code == 400


def test_post_fix_accepts_known_service(client):
    with patch("fix_factory.routes.fix.get_incident_traces", return_value=[]), \
         patch("fix_factory.routes.fix.get_fix_precedents", return_value=[]), \
         patch("fix_factory.routes.fix.run_with_correction", return_value={
             "patch": MOCK_PATCH, "old_line": MOCK_OLD_LINE, "new_line": MOCK_NEW_LINE,
             "fix_explanation": MOCK_EXPLANATION, "mr_url": None,
             "self_correction_passed": True, "correction_iterations": 1, "failure_reason": None,
         }):
        r = client.post("/fix", json={**AUTH_HIT, "service": "http-monitor"})
    assert r.status_code == 200


def test_get_incident_traces_returns_empty_on_bad_credentials():
    import asyncio
    import fix_factory.tools.dynatrace_traces as dt_mod
    dt_mod._trace_cache.clear()
    from fix_factory.tools.dynatrace_traces import get_incident_traces
    # Async version catches exceptions and returns [] rather than raising
    result = asyncio.run(get_incident_traces("bad.env.com", "bad-token", "DT-9999"))
    assert result == []


def test_validate_incident_id_accepts_valid_ids():
    from fix_factory.tools.dynatrace_traces import validate_incident_id
    validate_incident_id("DT-4821")
    validate_incident_id("P-12345")
    validate_incident_id("PROB-1")


def test_validate_incident_id_rejects_injection_payload():
    from fix_factory.tools.dynatrace_traces import validate_incident_id
    with pytest.raises(ValueError):
        validate_incident_id('" | fetch logs | limit 100 //')


def test_validate_incident_id_rejects_empty_string():
    from fix_factory.tools.dynatrace_traces import validate_incident_id
    with pytest.raises(ValueError):
        validate_incident_id("")


def test_validate_incident_id_rejects_spaces():
    from fix_factory.tools.dynatrace_traces import validate_incident_id
    with pytest.raises(ValueError):
        validate_incident_id("DT 4821")


def test_get_incident_traces_rejects_invalid_incident_id():
    import asyncio
    from fix_factory.tools.dynatrace_traces import get_incident_traces
    with pytest.raises(ValueError):
        asyncio.run(get_incident_traces("env.example.com", "token", '" | fetch logs'))


# --- _apply_patch unit tests ---

def test_apply_patch_exact_match():
    from fix_factory.tools.gitlab_mr import _apply_patch
    content = "import requests\n\ndef get_data(url):\n    response = requests.get(url)\n    return response\n"
    result = _apply_patch(content, "    response = requests.get(url)", "    response = requests.get(url, timeout=5)")
    assert "timeout=5" in result
    assert "requests.get(url)\n" not in result


def test_apply_patch_strip_based_fallback():
    from fix_factory.tools.gitlab_mr import _apply_patch
    # File uses 2-space indent, Gemini assumed 4-space
    content = "def get(url):\n  response = requests.get(url)\n  return response\n"
    result = _apply_patch(content, "    response = requests.get(url)", "    response = requests.get(url, timeout=5)")
    assert "timeout=5" in result


def test_apply_patch_returns_unchanged_when_no_match():
    from fix_factory.tools.gitlab_mr import _apply_patch
    content = "x = 1\ny = 2\n"
    result = _apply_patch(content, "z = 3", "z = 4")
    assert result == content
