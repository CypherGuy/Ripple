"""
Live integration tests for Intelligence /analyze.
Hits the real running service with real Gemini - no mocks.

Run:
    pytest -m live -v

Excluded from normal suite:
    pytest -m "not live"

The service must be running on port 8001 before executing these tests.
"""
import pytest
import httpx

ANALYZE_URL = "http://localhost:8001/analyze"
TIMEOUT = 60  # Gemini can take a few seconds

PAYLOAD = {
    "pr_id": "live-test-1",
    "repo": "org/payment-service",
    "diff": "response = requests.get(url)",
}


@pytest.mark.live
def test_analyze_returns_200():
    r = httpx.post(ANALYZE_URL, json=PAYLOAD, timeout=TIMEOUT)
    assert r.status_code == 200


@pytest.mark.live
def test_analyze_pattern_is_non_empty_string():
    r = httpx.post(ANALYZE_URL, json=PAYLOAD, timeout=TIMEOUT)
    body = r.json()
    assert isinstance(body["pattern"], str)
    assert len(body["pattern"]) > 0


@pytest.mark.live
def test_analyze_risk_score_is_integer_in_range():
    r = httpx.post(ANALYZE_URL, json=PAYLOAD, timeout=TIMEOUT)
    score = r.json()["risk_score"]
    assert isinstance(score, int)
    assert 1 <= score <= 10


@pytest.mark.live
def test_analyze_risk_rationale_is_non_empty_string():
    r = httpx.post(ANALYZE_URL, json=PAYLOAD, timeout=TIMEOUT)
    rationale = r.json()["risk_rationale"]
    assert isinstance(rationale, str)
    assert len(rationale) > 0


@pytest.mark.live
def test_analyze_incident_context_is_dict():
    r = httpx.post(ANALYZE_URL, json=PAYLOAD, timeout=TIMEOUT)
    assert isinstance(r.json()["incident_context"], dict)


@pytest.mark.live
def test_analyze_previous_scans_is_list():
    r = httpx.post(ANALYZE_URL, json=PAYLOAD, timeout=TIMEOUT)
    assert isinstance(r.json()["previous_scans"], list)


@pytest.mark.live
def test_analyze_pattern_mentions_timeout_or_http():
    """Gemini should recognise this is an HTTP timeout pattern."""
    r = httpx.post(ANALYZE_URL, json=PAYLOAD, timeout=TIMEOUT)
    pattern = r.json()["pattern"].lower()
    assert any(word in pattern for word in [
               "timeout", "http", "request", "async", "network"])
