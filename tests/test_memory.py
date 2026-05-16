import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

WIN_AUTH = {
    "pattern": "HTTP call with no timeout in async context",
    "service": "auth-service",
    "outcome": "merged",
    "reason": "Added 5s timeout. No incidents since.",
    "confidence_boost": 2,
    "date": "2026-02-20",
}

SCAR_GATEWAY = {
    "pattern": "HTTP call with no timeout in async context",
    "service": "gateway-service",
    "outcome": "rejected",
    "reason": "Timeout intentionally absent — internal sidecar.",
    "risk_adjustment": -3,
    "date": "2026-01-12",
}

BASE_EXTRACT = {
    "pattern": "HTTP call with no timeout in async context",
    "risk_score": 7,
    "risk_rationale": "Matches DT-4821.",
    "incident_context": {"incident_id": "DT-4821", "duration_minutes": 47},
    "previous_scans": [],
}

SAMPLE_DIFF = "@@ -12 +12 @@ response = requests.get(url)"


@pytest.fixture
def client():
    from intelligence.main import app
    return TestClient(app)


def test_find_similar_wins_returns_matching_docs():
    from intelligence.tools.mongodb import find_similar_wins
    col = MagicMock()
    col.find.return_value = [WIN_AUTH]
    result = find_similar_wins("HTTP call with no timeout", _col=col)
    assert len(result) == 1
    assert result[0]["service"] == "auth-service"
    assert result[0]["confidence_boost"] == 2


def test_find_similar_scars_returns_matching_docs():
    from intelligence.tools.mongodb import find_similar_scars
    col = MagicMock()
    col.find.return_value = [SCAR_GATEWAY]
    result = find_similar_scars("HTTP call with no timeout", _col=col)
    assert len(result) == 1
    assert result[0]["service"] == "gateway-service"


def test_find_similar_wins_returns_empty_when_no_match():
    from intelligence.tools.mongodb import find_similar_wins
    col = MagicMock()
    col.find.return_value = []
    result = find_similar_wins("totally unrelated pattern", _col=col)
    assert result == []


def test_analyze_boosts_risk_score_by_win_confidence(client):
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=[BASE_EXTRACT["incident_context"]]), \
         patch("intelligence.routes.analyze.extract_pattern", return_value=BASE_EXTRACT.copy()), \
         patch("intelligence.routes.analyze.find_similar_wins", return_value=[WIN_AUTH]), \
         patch("intelligence.routes.analyze.find_similar_scars", return_value=[]):
        r = client.post("/analyze", json={"pr_id": "1", "repo": "x", "diff": SAMPLE_DIFF})

    assert r.status_code == 200
    body = r.json()
    assert body["risk_score"] == 9  # 7 + 2 from auth-service win
    assert any(s["service"] == "auth-service" for s in body["previous_scans"])


def test_analyze_adjusts_risk_score_by_scar(client):
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=[BASE_EXTRACT["incident_context"]]), \
         patch("intelligence.routes.analyze.extract_pattern", return_value=BASE_EXTRACT.copy()), \
         patch("intelligence.routes.analyze.find_similar_wins", return_value=[]), \
         patch("intelligence.routes.analyze.find_similar_scars", return_value=[SCAR_GATEWAY]):
        r = client.post("/analyze", json={"pr_id": "1", "repo": "x", "diff": SAMPLE_DIFF})

    body = r.json()
    assert body["risk_score"] == 4  # 7 + (-3) from gateway-service scar
    assert any(s["service"] == "gateway-service" for s in body["previous_scans"])


def test_analyze_clamps_risk_score_to_minimum_of_1(client):
    large_scar = {**SCAR_GATEWAY, "risk_adjustment": -10}
    with patch("intelligence.routes.analyze.fetch_incident_history", return_value=[BASE_EXTRACT["incident_context"]]), \
         patch("intelligence.routes.analyze.extract_pattern", return_value=BASE_EXTRACT.copy()), \
         patch("intelligence.routes.analyze.find_similar_wins", return_value=[]), \
         patch("intelligence.routes.analyze.find_similar_scars", return_value=[large_scar]):
        r = client.post("/analyze", json={"pr_id": "1", "repo": "x", "diff": SAMPLE_DIFF})

    assert r.json()["risk_score"] >= 1
