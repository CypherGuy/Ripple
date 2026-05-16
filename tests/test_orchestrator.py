import asyncio
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from orchestrator.main import app
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "orchestrator"}


def test_webhook_accepts_valid_payload(client):
    payload = {
        "pr_id": "12345",
        "repo": "org/payment-service",
        "diff": "@@ -12 +12 @@ timeout=None",
    }
    r = client.post("/webhook", json=payload)
    assert r.status_code == 202
    assert r.json() == {"status": "accepted", "pr_id": "12345"}


def test_webhook_rejects_missing_pr_id(client):
    r = client.post("/webhook", json={"repo": "org/payment-service"})
    assert r.status_code == 422


def test_websocket_accepts_connection(client):
    with client.websocket_connect("/ws"):
        pass


def test_broadcast_event_with_no_connections_does_not_raise():
    from orchestrator.ws_manager import broadcast_event
    asyncio.run(broadcast_event({"event": "test"}))
