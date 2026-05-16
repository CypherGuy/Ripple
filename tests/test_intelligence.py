import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

DT4821_INCIDENTS = [
    {
        "incident_id": "DT-4821",
        "title": "Payment service cascade failure — no timeout on HTTP client",
        "duration_minutes": 47,
        "estimated_cost": "£23,000",
        "root_cause_summary": "HTTP client with no timeout caused thread pool exhaustion under load.",
        "affected_services": ["payment-service", "auth-service", "order-service"],
    }
]

SAMPLE_DIFF = "@@ -12,6 +12,8 @@\n-  timeout=None\n+  response = requests.get(url)"


@pytest.fixture
def client():
    from intelligence.main import app
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "intelligence"}


def test_analyze_returns_pattern_and_risk_score(client):
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=DT4821_INCIDENTS), \
         patch("intelligence.routes.analyze.extract_pattern", return_value={
             "pattern": "Synchronous HTTP call with no timeout configured.",
             "risk_score": 9,
             "risk_rationale": "Matches DT-4821 — 47-minute outage.",
             "incident_context": DT4821_INCIDENTS[0],
             "previous_scans": [],
         }):
        r = client.post("/analyze", json={
            "pr_id": "12345",
            "repo": "org/payment-service",
            "diff": SAMPLE_DIFF,
        })
    assert r.status_code == 200
    body = r.json()
    assert body["pattern"] != ""
    assert body["risk_score"] == 9


def test_analyze_pattern_is_non_empty_string(client):
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=DT4821_INCIDENTS), \
         patch("intelligence.routes.analyze.extract_pattern", return_value={
             "pattern": "Synchronous HTTP call with no timeout configured.",
             "risk_score": 9,
             "risk_rationale": "Matches DT-4821.",
             "incident_context": DT4821_INCIDENTS[0],
             "previous_scans": [],
         }):
        r = client.post("/analyze", json={
            "pr_id": "1",
            "repo": "org/svc",
            "diff": SAMPLE_DIFF,
        })
    assert isinstance(r.json()["pattern"], str)
    assert len(r.json()["pattern"]) > 0


def test_analyze_rejects_missing_diff(client):
    r = client.post("/analyze", json={"pr_id": "1", "repo": "org/svc"})
    assert r.status_code == 422


def test_fetch_incident_history_raises_on_bad_token():
    from intelligence.tools.dynatrace import fetch_incident_history
    with pytest.raises(Exception):
        fetch_incident_history("bad.env.com", "bad-token", SAMPLE_DIFF)


def test_extract_pattern_returns_required_keys():
    from intelligence.agent import extract_pattern
    with patch("intelligence.agent.call_gemini", return_value=(
        "HTTP call with no timeout.", 9, "Matches DT-4821."
    )):
        result = extract_pattern(SAMPLE_DIFF, DT4821_INCIDENTS)
    assert "pattern" in result
    assert "risk_score" in result
    assert "risk_rationale" in result
    assert "incident_context" in result
    assert "previous_scans" in result
