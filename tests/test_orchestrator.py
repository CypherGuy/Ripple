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
    import os
    os.environ.pop("GITLAB_WEBHOOK_SECRET", None)
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


def test_webhook_rejects_wrong_gitlab_token(client):
    import os
    os.environ["GITLAB_WEBHOOK_SECRET"] = "correct-secret"
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock:
        mock.return_value = []
        r = client.post("/webhook",
                        json={"pr_id": "1", "diff": "x"},
                        headers={"X-Gitlab-Token": "wrong-secret"})
    assert r.status_code == 403


def test_webhook_accepts_correct_gitlab_token(client):
    import os
    os.environ["GITLAB_WEBHOOK_SECRET"] = "correct-secret"
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock:
        mock.return_value = []
        r = client.post("/webhook",
                        json={"pr_id": "1", "diff": "x"},
                        headers={"X-Gitlab-Token": "correct-secret"})
    assert r.status_code == 202


def test_webhook_passes_when_no_secret_configured(client):
    import os
    os.environ.pop("GITLAB_WEBHOOK_SECRET", None)
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock:
        mock.return_value = []
        r = client.post("/webhook", json={"pr_id": "1", "diff": "x"})
    assert r.status_code == 202


def test_websocket_accepts_connection(client):
    with client.websocket_connect("/ws"):
        pass


def test_broadcast_event_with_no_connections_does_not_raise():
    from orchestrator.ws_manager import broadcast_event
    asyncio.run(broadcast_event({"event": "test"}))


def test_demo_trigger_endpoint_exists_and_requires_no_auth(client):
    import orchestrator.routes.demo as demo_mod
    demo_mod._last_trigger_time = None  # reset rate limiter
    with patch("orchestrator.routes.demo.run_pipeline", new_callable=AsyncMock) as mock:
        mock.return_value = []
        r = client.post("/demo/trigger")
    assert r.status_code == 202


def test_demo_trigger_fires_pipeline_with_pulsecheck_payload(client):
    import orchestrator.routes.demo as demo_mod
    demo_mod._last_trigger_time = None  # reset rate limiter
    with patch("orchestrator.routes.demo.run_pipeline", new_callable=AsyncMock) as mock:
        mock.return_value = []
        client.post("/demo/trigger")
    payload_arg = mock.call_args[0][0]
    assert payload_arg["incident_context"]["incident_id"] == "P-26051"
    assert "pulsecheck" in payload_arg["repo"]
    assert payload_arg["incident_context"].get("root_cause_summary") != ""


def test_demo_trigger_rate_limits_second_request(client):
    import orchestrator.routes.demo as demo_mod
    demo_mod._last_trigger_time = None  # reset

    with patch("orchestrator.routes.demo.run_pipeline", new_callable=AsyncMock) as mock:
        mock.return_value = []
        r1 = client.post("/demo/trigger")
        r2 = client.post("/demo/trigger")  # immediate second call

    assert r1.status_code == 202
    assert r2.status_code == 429


def test_demo_trigger_allows_request_after_cooldown(client):
    import orchestrator.routes.demo as demo_mod
    import time
    demo_mod._last_trigger_time = time.time() - 61  # simulate 61s ago

    with patch("orchestrator.routes.demo.run_pipeline", new_callable=AsyncMock) as mock:
        mock.return_value = []
        r = client.post("/demo/trigger")
    assert r.status_code == 202



# ---------------------------------------------------------------------------
# Trigger Demo button - webhook must accept incident_context in the payload
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

    asyncio.run(run_pipeline(payload_with_context,
                "trace-demo", _client=mock_client))

    assert fix_payloads_seen, "Fix Factory was never called"
    fix_ctx = fix_payloads_seen[0].get("incident_context", {})
    assert fix_ctx.get("incident_id") == "P-26051", \
        f"Expected P-26051 in incident_context passed to Fix Factory, got: {fix_ctx}"
    assert fix_ctx.get(
        "root_cause_summary") == "ssl-monitor hung on slow cert check"


# ---------------------------------------------------------------------------
# Risk threshold / approval flow
# ---------------------------------------------------------------------------

def test_pipeline_does_not_fix_when_risk_below_threshold():
    """When risk_score < AUTO_FIX_THRESHOLD, Fix Factory must NOT be called."""
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock
    import os

    os.environ["AUTO_FIX_THRESHOLD"] = "7"

    low_risk_intel = {
        "pattern": "Missing retry logic",
        "risk_score": 4,
        "risk_rationale": "low risk",
        "incident_context": {"incident_id": "P-001"},
        "previous_scans": [],
    }
    fix_called = {"n": 0}

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = low_risk_intel
        elif "scan" in url:
            r.json.return_value = {
                "hits": [{"service": "ssl-monitor", "file_path": "m.py",
                          "matching_lines": [], "confidence": 0.8}],
            }
        elif "fix" in url:
            fix_called["n"] += 1
            r.json.return_value = {"mr_url": None}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(
        {"pr_id": "x", "diff": "x"}, "trace-t", _client=mock_client))
    assert fix_called["n"] == 0, "Fix Factory should not be called when risk is below threshold"


def test_pipeline_broadcasts_requires_approval_when_risk_below_threshold():
    """When risk_score < threshold, pipeline broadcasts a requires_approval event per service."""
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock
    import os

    os.environ["AUTO_FIX_THRESHOLD"] = "7"

    low_risk_intel = {
        "pattern": "Missing retry logic",
        "risk_score": 4,
        "risk_rationale": "low risk",
        "incident_context": {},
        "previous_scans": [],
    }
    broadcast_calls = []

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = low_risk_intel
        elif "scan" in url:
            r.json.return_value = {
                "hits": [{"service": "ssl-monitor", "file_path": "m.py",
                          "matching_lines": [], "confidence": 0.8}],
            }
        elif "broadcast" in url:
            broadcast_calls.append(kwargs.get("json", {}))
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(
        {"pr_id": "x", "diff": "x"}, "trace-t", _client=mock_client))
    approval_events = [c for c in broadcast_calls if c.get(
        "event") == "requires_approval"]
    assert len(approval_events) == 1
    assert approval_events[0]["service"] == "ssl-monitor"


def test_pipeline_auto_fixes_when_risk_at_or_above_threshold():
    """When risk_score >= threshold, Fix Factory is called as before."""
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock
    import os

    os.environ["AUTO_FIX_THRESHOLD"] = "7"

    high_risk_intel = {
        "pattern": "HTTP call without timeout",
        "risk_score": 9,
        "risk_rationale": "high risk",
        "incident_context": {},
        "previous_scans": [],
    }
    fix_called = {"n": 0}

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = high_risk_intel
        elif "scan" in url:
            r.json.return_value = {
                "hits": [{"service": "ssl-monitor", "file_path": "m.py",
                          "matching_lines": [], "confidence": 0.8}],
            }
        elif "fix" in url:
            fix_called["n"] += 1
            r.json.return_value = {"mr_url": None}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(
        {"pr_id": "x", "diff": "x"}, "trace-t", _client=mock_client))
    assert fix_called["n"] == 1


def test_approve_endpoint_triggers_fix_with_inline_payload(client):
    """POST /internal/approve fires fix when the dashboard sends the full hit context."""
    import os
    os.environ["ADMIN_SECRET"] = "test-admin-secret"
    os.environ["AUTO_FIX_THRESHOLD"] = "7"

    fake_hit = {"service": "ssl-monitor", "file_path": "m.py",
                "matching_lines": [], "confidence": 0.8}
    fake_intel = {"pattern": "x", "incident_context": {}}

    with patch("orchestrator.routes.internal.fix_hit", new_callable=AsyncMock) as mock_fix:
        mock_fix.return_value = {"mr_url": None, "service": "ssl-monitor"}
        r = client.post(
            "/internal/approve",
            json={"service": "ssl-monitor", "hit": fake_hit,
                  "intel": fake_intel, "trace_id": "t"},
            headers={"X-Admin-Secret": "test-admin-secret"},
        )

    assert r.status_code == 202
    mock_fix.assert_called_once()


def test_approve_endpoint_falls_back_to_pending_state(client):
    """POST /internal/approve uses _pending_approvals when no payload provided."""
    import os
    import orchestrator.pipeline as pipeline_mod
    os.environ["ADMIN_SECRET"] = "test-admin-secret"

    fake_hit = {"service": "ssl-monitor", "file_path": "m.py",
                "matching_lines": [], "confidence": 0.8}
    fake_intel = {"pattern": "x", "incident_context": {}}
    pipeline_mod._pending_approvals["ssl-monitor"] = {
        "hit": fake_hit, "intel": fake_intel, "trace_id": "t"}

    with patch("orchestrator.routes.internal.fix_hit", new_callable=AsyncMock) as mock_fix:
        mock_fix.return_value = {"mr_url": None, "service": "ssl-monitor"}
        r = client.post(
            "/internal/approve",
            json={"service": "ssl-monitor"},
            headers={"X-Admin-Secret": "test-admin-secret"},
        )

    assert r.status_code == 202
    mock_fix.assert_called_once()
    assert "ssl-monitor" not in pipeline_mod._pending_approvals


def test_approve_endpoint_returns_404_when_no_payload_and_no_pending(client):
    """POST /internal/approve returns 404 if neither payload nor pending state exists."""
    import os
    import orchestrator.pipeline as pipeline_mod
    os.environ["ADMIN_SECRET"] = "test-admin-secret"
    pipeline_mod._pending_approvals.pop("nonexistent-svc", None)

    r = client.post(
        "/internal/approve",
        json={"service": "nonexistent-svc"},
        headers={"X-Admin-Secret": "test-admin-secret"},
    )
    assert r.status_code == 404


def test_approve_endpoint_requires_admin_secret(client):
    """POST /internal/approve returns 403 without the correct admin secret."""
    import os
    os.environ["ADMIN_SECRET"] = "test-admin-secret"

    r = client.post(
        "/internal/approve",
        json={"service": "ssl-monitor"},
        headers={"X-Admin-Secret": "wrong"},
    )
    assert r.status_code == 403
