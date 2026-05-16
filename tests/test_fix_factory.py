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

MOCK_PATCH = (
    "--- a/src/clients/downstream.py\n"
    "+++ b/src/clients/downstream.py\n"
    "@@ -42,1 +42,1 @@\n"
    "-    response = requests.get(url)\n"
    "+    response = requests.get(url, timeout=5)"
)
MOCK_EXPLANATION = "Added 5s timeout to prevent thread pool exhaustion matching DT-4821 (47-min outage, £23,000)."


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
        _gemini_fn=lambda _: (MOCK_PATCH, MOCK_EXPLANATION),
    )
    assert "timeout=" in result["patch"]
    assert "DT-4821" in result["fix_explanation"]


def test_generate_fix_returns_required_keys():
    from fix_factory.agent import generate_fix
    result = generate_fix(
        AUTH_HIT,
        traces=[],
        precedents=[],
        _gemini_fn=lambda _: (MOCK_PATCH, MOCK_EXPLANATION),
    )
    assert "patch" in result
    assert "fix_explanation" in result


def test_generate_fix_works_with_empty_context():
    from fix_factory.agent import generate_fix
    hit = {**AUTH_HIT, "per_service_history": [], "incident_context": {"incident_id": "DT-4821"}}
    result = generate_fix(
        hit,
        traces=[],
        precedents=[],
        _gemini_fn=lambda _: (MOCK_PATCH, MOCK_EXPLANATION),
    )
    assert result["patch"] != ""


def test_post_fix_returns_patch_and_explanation(client):
    with patch("fix_factory.routes.fix.get_incident_traces", return_value=[]), \
         patch("fix_factory.routes.fix.get_fix_precedents", return_value=[]), \
         patch("fix_factory.routes.fix.run_with_correction", return_value={
             "patch": MOCK_PATCH,
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


def test_get_incident_traces_raises_on_bad_credentials():
    from fix_factory.tools.dynatrace_traces import get_incident_traces
    with pytest.raises(Exception):
        get_incident_traces("bad.env.com", "bad-token", "DT-4821")
