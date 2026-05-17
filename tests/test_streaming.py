import os
import pytest
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

CALLBACK_URL = "http://localhost:8000/internal/broadcast"
ORCHESTRATOR_URL = "http://localhost:8000"

HIT = {
    "file_path": "src/clients/downstream.py",
    "matching_lines": [{"line_number": 42, "content": "response = requests.get(url)"}],
    "confidence": 0.94,
}

SCAN_PAYLOAD = {
    "pattern": "HTTP call with no timeout",
    "incident_context": {"incident_id": "DT-4821"},
    "services": [{"name": "auth-service", "gitlab_namespace": "org/auth-service"}],
    "callback_url": CALLBACK_URL,
}


@pytest.fixture
def scanner_client():
    from scanner.main import app
    return TestClient(app)


@pytest.fixture
def orchestrator_client():
    from orchestrator.main import app
    return TestClient(app)


# --- emit_event unit tests ---

def test_emit_event_posts_to_callback_url():
    from scanner.streaming import emit_event
    with patch.dict(os.environ, {"ORCHESTRATOR_URL": ORCHESTRATOR_URL}), \
         patch("scanner.streaming.httpx.post") as mock_post:
        emit_event(CALLBACK_URL, {"event": "agent_started", "service": "auth-service"})
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == CALLBACK_URL
    assert kwargs["json"]["event"] == "agent_started"


def test_emit_event_ignores_failures():
    from scanner.streaming import emit_event
    with patch.dict(os.environ, {"ORCHESTRATOR_URL": ORCHESTRATOR_URL}), \
         patch("scanner.streaming.httpx.post", side_effect=Exception("connection refused")):
        emit_event(CALLBACK_URL, {"event": "test"})  # must not raise


def test_emit_event_does_nothing_when_no_callback_url():
    from scanner.streaming import emit_event
    with patch("scanner.streaming.httpx.post") as mock_post:
        emit_event(None, {"event": "test"})
    mock_post.assert_not_called()


def test_validate_callback_url_accepts_orchestrator_host():
    from scanner.streaming import validate_callback_url
    with patch.dict(os.environ, {"ORCHESTRATOR_URL": ORCHESTRATOR_URL}):
        validate_callback_url(CALLBACK_URL)  # must not raise


def test_validate_callback_url_rejects_gcp_metadata():
    from scanner.streaming import validate_callback_url
    with patch.dict(os.environ, {"ORCHESTRATOR_URL": ORCHESTRATOR_URL}), \
         pytest.raises(ValueError):
        validate_callback_url("http://169.254.169.254/latest/meta-data/")


def test_validate_callback_url_rejects_arbitrary_external_url():
    from scanner.streaming import validate_callback_url
    with patch.dict(os.environ, {"ORCHESTRATOR_URL": ORCHESTRATOR_URL}), \
         pytest.raises(ValueError):
        validate_callback_url("http://evil.example.com/steal-tokens")


def test_emit_event_silently_skips_disallowed_url():
    from scanner.streaming import emit_event
    with patch.dict(os.environ, {"ORCHESTRATOR_URL": ORCHESTRATOR_URL}), \
         patch("scanner.streaming.httpx.post") as mock_post:
        emit_event("http://169.254.169.254/meta-data/", {"event": "agent_started"})
    mock_post.assert_not_called()


# --- scanner streaming integration tests ---

def test_scan_emits_agent_started_before_result(scanner_client):
    emitted = []

    def capture_emit(url, data):
        emitted.append(data)

    with patch("scanner.routes.scan.scan_service", return_value=[]), \
         patch("scanner.routes.scan.emit_event", side_effect=capture_emit):
        scanner_client.post("/scan", json=SCAN_PAYLOAD)

    assert emitted[0]["event"] == "agent_started"
    assert emitted[0]["service"] == "auth-service"


def test_scan_emits_hit_found_when_hits_exist(scanner_client):
    emitted = []

    with patch("scanner.routes.scan.scan_service", return_value=[HIT]), \
         patch("scanner.routes.scan.emit_event", side_effect=lambda url, d: emitted.append(d)):
        scanner_client.post("/scan", json=SCAN_PAYLOAD)

    events = [e["event"] for e in emitted]
    assert "agent_started" in events
    assert "hit_found" in events
    assert "no_hit" not in events


def test_scan_emits_no_hit_when_empty(scanner_client):
    emitted = []

    with patch("scanner.routes.scan.scan_service", return_value=[]), \
         patch("scanner.routes.scan.emit_event", side_effect=lambda url, d: emitted.append(d)):
        scanner_client.post("/scan", json=SCAN_PAYLOAD)

    events = [e["event"] for e in emitted]
    assert "no_hit" in events
    assert "hit_found" not in events


def test_hit_found_event_contains_data_field(scanner_client):
    emitted = []

    with patch("scanner.routes.scan.scan_service", return_value=[HIT]), \
         patch("scanner.routes.scan.emit_event", side_effect=lambda url, d: emitted.append(d)):
        scanner_client.post("/scan", json=SCAN_PAYLOAD)

    hit_events = [e for e in emitted if e["event"] == "hit_found"]
    assert len(hit_events) == 1
    assert hit_events[0]["data"]["file_path"] == HIT["file_path"]
    assert hit_events[0]["data"]["confidence"] == HIT["confidence"]


# --- Orchestrator /internal/broadcast ---

def test_internal_broadcast_calls_broadcast_event(orchestrator_client):
    with patch.dict(os.environ, {"INTERNAL_SECRET": "test-secret"}), \
         patch("orchestrator.routes.internal.broadcast_event") as mock_bcast:
        r = orchestrator_client.post(
            "/internal/broadcast",
            json={"event": "agent_started", "service": "auth-service"},
            headers={"X-Internal-Secret": "test-secret"},
        )
    assert r.status_code == 200
    mock_bcast.assert_called_once()


def test_internal_broadcast_rejects_missing_secret(orchestrator_client):
    with patch.dict(os.environ, {"INTERNAL_SECRET": "test-secret"}), \
         patch("orchestrator.routes.internal.broadcast_event") as mock_bcast:
        r = orchestrator_client.post(
            "/internal/broadcast",
            json={"event": "agent_started", "service": "auth-service"},
        )
    assert r.status_code == 403
    mock_bcast.assert_not_called()


def test_internal_broadcast_rejects_wrong_secret(orchestrator_client):
    with patch.dict(os.environ, {"INTERNAL_SECRET": "test-secret"}), \
         patch("orchestrator.routes.internal.broadcast_event") as mock_bcast:
        r = orchestrator_client.post(
            "/internal/broadcast",
            json={"event": "agent_started", "service": "auth-service"},
            headers={"X-Internal-Secret": "wrong-secret"},
        )
    assert r.status_code == 403
    mock_bcast.assert_not_called()
