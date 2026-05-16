import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

AUTH_FILES = {
    "src/clients/downstream.py": "import requests\n\nresponse = requests.get(url)\n"
}

GATEWAY_FILES = {
    "src/http/client.py": "import requests\n\nresponse = requests.get(url, timeout=5)\n"
}

AUTH_HIT = [
    {
        "file_path": "src/clients/downstream.py",
        "matching_lines": [{"line_number": 3, "content": "response = requests.get(url)"}],
        "confidence": 0.94,
    }
]

SCAN_PAYLOAD = {
    "pattern": "Synchronous HTTP call with no timeout in async handler.",
    "incident_context": {"incident_id": "DT-4821", "duration_minutes": 47},
    "services": [
        {"name": "auth-service", "repo": "org/auth-service", "gitlab_namespace": "org/auth-service"},
        {"name": "gateway-service", "repo": "org/gateway-service", "gitlab_namespace": "org/gateway-service"},
    ],
}


@pytest.fixture
def client():
    from scanner.main import app
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "scanner"}


def test_scan_service_finds_hit_in_auth_service():
    from scanner.agent import scan_service
    hits = scan_service(
        {"name": "auth-service", "gitlab_namespace": "org/auth-service"},
        "HTTP call with no timeout",
        {},
        _files_override=AUTH_FILES,
        _gemini_fn=lambda _: AUTH_HIT,
    )
    assert len(hits) == 1
    assert hits[0]["confidence"] > 0.8
    assert hits[0]["file_path"] == "src/clients/downstream.py"


def test_scan_service_finds_no_hit_in_gateway_service():
    from scanner.agent import scan_service
    hits = scan_service(
        {"name": "gateway-service", "gitlab_namespace": "org/gateway-service"},
        "HTTP call with no timeout",
        {},
        _files_override=GATEWAY_FILES,
        _gemini_fn=lambda _: [],
    )
    assert hits == []


def test_scan_service_returns_empty_when_no_files():
    from scanner.agent import scan_service
    hits = scan_service(
        {"name": "empty-service", "gitlab_namespace": "org/empty"},
        "HTTP call with no timeout",
        {},
        _files_override={},
        _gemini_fn=lambda _: AUTH_HIT,
    )
    assert hits == []


def test_post_scan_returns_hits_for_matching_service(client):
    def mock_scan(svc, pattern, context, _files_override=None, _gemini_fn=None):
        if svc["name"] == "auth-service":
            return AUTH_HIT
        return []

    with patch("scanner.routes.scan.scan_service", side_effect=mock_scan):
        r = client.post("/scan", json=SCAN_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert len(body["hits"]) == 1
    assert body["hits"][0]["service"] == "auth-service"
    assert "incident_context" in body


def test_post_scan_returns_empty_hits_when_no_matches(client):
    with patch("scanner.routes.scan.scan_service", return_value=[]):
        r = client.post("/scan", json=SCAN_PAYLOAD)

    assert r.status_code == 200
    assert r.json()["hits"] == []


def test_post_scan_rejects_missing_pattern(client):
    r = client.post("/scan", json={"incident_context": {}, "services": []})
    assert r.status_code == 422


def test_scan_service_prompt_excludes_already_timed_out_calls():
    from scanner.agent import scan_service
    prompts_seen = []
    def capture(prompt):
        prompts_seen.append(prompt)
        return []
    scan_service(
        {"gitlab_namespace": "org/svc"},
        "HTTP call with no timeout",
        {},
        _files_override={"src/client.py": "response = requests.get(url, timeout=5)\n"},
        _gemini_fn=capture,
    )
    assert len(prompts_seen) == 1
    assert "already" in prompts_seen[0].lower() or "do not flag" in prompts_seen[0].lower()
