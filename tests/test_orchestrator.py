import asyncio
import pytest
from unittest.mock import patch, AsyncMock
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
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = []
        r = client.post("/webhook", json=payload)
    assert r.status_code == 202
    assert r.json()["status"] == "accepted"
    assert r.json()["pr_id"] == "12345"
    assert "fix_results" in r.json()


def test_webhook_rejects_missing_pr_id(client):
    r = client.post("/webhook", json={"repo": "org/payment-service"})
    assert r.status_code == 422


def test_websocket_accepts_connection(client):
    with client.websocket_connect("/ws"):
        pass


def test_broadcast_event_with_no_connections_does_not_raise():
    from orchestrator.ws_manager import broadcast_event
    asyncio.run(broadcast_event({"event": "test"}))


# ---------------------------------------------------------------------------
# Trigger Demo button — webhook must accept incident_context in the payload
# ---------------------------------------------------------------------------

DEMO_PAYLOAD = {
    "pr_id": "demo-run",
    "repo": "cypherguy-group/pulsecheck/ssl-monitor",
    "diff": "@@ -12 +12 @@ response = httpx.get(target_url)",
    "incident_context": {
        "incident_id": "P-26051",
        "duration_minutes": 47,
        "estimated_cost": "£23,000",
        "root_cause_summary": "PulseCheck ssl-monitor hung on slow cert check",
    },
}


def test_webhook_accepts_demo_payload_with_incident_context(client):
    """The /webhook endpoint must accept incident_context in the body (Trigger Demo button payload)."""
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = []
        r = client.post("/webhook", json=DEMO_PAYLOAD)
    assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
    assert r.json()["pr_id"] == "demo-run"


def test_webhook_forwards_incident_context_to_pipeline(client):
    """incident_context from the webhook payload is forwarded to run_pipeline."""
    captured = {}

    async def capture_pipeline(payload, trace_id, **kwargs):
        captured["payload"] = payload
        return []

    with patch("orchestrator.routes.webhook.run_pipeline", side_effect=capture_pipeline):
        client.post("/webhook", json=DEMO_PAYLOAD)

    assert "incident_context" in captured.get("payload", {}), \
        "incident_context was not forwarded to run_pipeline"
    assert captured["payload"]["incident_context"]["incident_id"] == "P-26051"


def test_pipeline_uses_webhook_incident_context_when_intel_returns_none():
    """When intel returns no incident_context, the pipeline uses the one from the webhook payload."""
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock

    intel_with_empty_context = {
        "pattern": "HTTP call without timeout",
        "risk_score": 9,
        "risk_rationale": "matches pattern",
        "incident_context": {},
        "previous_scans": [],
    }

    fix_payloads_seen = []

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = intel_with_empty_context
        elif "scan" in url:
            r.json.return_value = {
                "hits": [{
                    "service": "ssl-monitor",
                    "file_path": "monitor.py",
                    "matching_lines": [{"line_number": 12, "content": "httpx.get(url)"}],
                    "confidence": 0.9,
                }],
                "incident_context": {},
            }
        elif "fix" in url:
            fix_payloads_seen.append(kwargs.get("json", {}))
            r.json.return_value = {"mr_url": None, "self_correction_passed": True,
                                   "correction_iterations": 1, "failure_reason": None}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    payload_with_context = {
        "pr_id": "demo-run",
        "repo": "cypherguy-group/pulsecheck/ssl-monitor",
        "diff": "@@ response = httpx.get(url)",
        "incident_context": {
            "incident_id": "P-26051",
            "duration_minutes": 47,
            "root_cause_summary": "ssl-monitor hung on slow cert check",
        },
    }

    asyncio.run(run_pipeline(payload_with_context, "trace-demo", _client=mock_client))

    assert fix_payloads_seen, "Fix Factory was never called"
    fix_ctx = fix_payloads_seen[0].get("incident_context", {})
    assert fix_ctx.get("incident_id") == "P-26051", \
        f"Expected P-26051 in incident_context passed to Fix Factory, got: {fix_ctx}"
    assert fix_ctx.get("root_cause_summary") == "ssl-monitor hung on slow cert check"
