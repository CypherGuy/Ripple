"""Tests for per-hit Fix Factory triggering via /internal/scan-event."""
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_pipeline_state():
    import orchestrator.pipeline as pm
    pm._pipeline_state = None
    yield
    pm._pipeline_state = None


@pytest.fixture
def client():
    os.environ["INTERNAL_SECRET"] = "test-secret"
    from orchestrator.main import app
    return TestClient(app)


FAKE_INTEL = {
    "pattern": "HTTP call without timeout",
    "risk_score": 9,
    "incident_context": {"incident_id": "P-26053"},
}

HIT_EVENT = {
    "event": "hit_found",
    "service": "ssl-monitor",
    "data": {
        "file_path": "main.py",
        "matching_lines": [{"line_number": 12, "content": "httpx.get(url)"}],
        "confidence": 0.9,
    },
    "timestamp": "2026-05-18T00:00:00Z",
}


def test_scan_event_rejects_wrong_secret(client):
    r = client.post("/internal/scan-event", json=HIT_EVENT,
                    headers={"X-Internal-Secret": "wrong"})
    assert r.status_code == 403


def test_scan_event_accepts_correct_secret(client):
    with patch("orchestrator.routes.internal.broadcast_event", new_callable=AsyncMock):
        r = client.post("/internal/scan-event", json=HIT_EVENT,
                        headers={"X-Internal-Secret": "test-secret"})
    assert r.status_code == 200


def test_scan_event_always_broadcasts_any_event(client):
    broadcasted = []

    async def capture(data):
        broadcasted.append(data)

    with patch("orchestrator.routes.internal.broadcast_event", side_effect=capture):
        client.post("/internal/scan-event",
                    json={"event": "agent_started",
                          "service": "ssl-monitor", "timestamp": "t"},
                    headers={"X-Internal-Secret": "test-secret"})

    assert len(broadcasted) == 1
    assert broadcasted[0]["event"] == "agent_started"


def test_scan_event_hit_with_no_active_pipeline_does_not_create_task(client):
    import orchestrator.pipeline as pm
    assert pm._pipeline_state is None

    with patch("orchestrator.routes.internal.broadcast_event", new_callable=AsyncMock), \
            patch("orchestrator.routes.internal.fix_hit", new_callable=AsyncMock) as mock_fix:
        client.post("/internal/scan-event", json=HIT_EVENT,
                    headers={"X-Internal-Secret": "test-secret"})

    mock_fix.assert_not_called()


def test_scan_event_hit_found_starts_fix_task(client):
    import orchestrator.pipeline as pm

    mock_client = AsyncMock()
    pm._pipeline_state = {
        "intel": FAKE_INTEL,
        "trace_id": "trace-123",
        "client": mock_client,
        "tasks": {},
        "hits": {},
    }

    with patch("orchestrator.routes.internal.broadcast_event", new_callable=AsyncMock), \
            patch("orchestrator.routes.internal.fix_hit", new_callable=AsyncMock) as mock_fix:
        mock_fix.return_value = {"mr_url": None, "service": "ssl-monitor"}
        client.post("/internal/scan-event", json=HIT_EVENT,
                    headers={"X-Internal-Secret": "test-secret"})

    assert "ssl-monitor" in pm._pipeline_state["tasks"]


def test_scan_event_hit_deduplicates_same_service(client):
    import orchestrator.pipeline as pm

    pm._pipeline_state = {
        "intel": FAKE_INTEL,
        "trace_id": "trace-123",
        "client": AsyncMock(),
        "tasks": {},
        "hits": {},
    }

    with patch("orchestrator.routes.internal.broadcast_event", new_callable=AsyncMock), \
            patch("orchestrator.routes.internal.fix_hit", new_callable=AsyncMock) as mock_fix:
        mock_fix.return_value = {"mr_url": None}
        client.post("/internal/scan-event", json=HIT_EVENT,
                    headers={"X-Internal-Secret": "test-secret"})
        client.post("/internal/scan-event", json=HIT_EVENT,
                    headers={"X-Internal-Secret": "test-secret"})

    assert len(pm._pipeline_state["tasks"]) == 1


def test_run_pipeline_uses_scan_event_callback_url():
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock

    scan_payloads = []

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = {**FAKE_INTEL, "previous_scans": []}
        elif "scan" in url:
            scan_payloads.append(kwargs.get("json", {}))
            r.json.return_value = {"hits": []}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = [{"path": "ssl-monitor",
                                "namespace": {"full_path": "org/proj"}}]
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.get = mock_get

    asyncio.run(run_pipeline(
        {"pr_id": "x", "diff": "x"}, "trace-t", _client=mock_client))

    assert len(scan_payloads) == 1
    assert "/internal/scan-event" in scan_payloads[0].get("callback_url", "")


def test_pipeline_state_is_none_after_pipeline_completes():
    import orchestrator.pipeline as pm
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = {**FAKE_INTEL, "previous_scans": []}
        elif "scan" in url:
            r.json.return_value = {"hits": []}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = []
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.get = mock_get

    asyncio.run(run_pipeline(
        {"pr_id": "x", "diff": "x"}, "trace-t", _client=mock_client))
    assert pm._pipeline_state is None


def test_pipeline_fallback_starts_fix_for_hit_not_received_via_callback():
    """Hits in scanner response but not via callback still get fixed (fallback path)."""
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock

    fix_calls = {"n": 0}

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = {**FAKE_INTEL, "previous_scans": []}
        elif "scan" in url:
            r.json.return_value = {
                "hits": [{"service": "ssl-monitor", "file_path": "main.py",
                          "matching_lines": [], "confidence": 0.9}]
            }
        elif "fix" in url:
            fix_calls["n"] += 1
            r.json.return_value = {"mr_url": None, "self_correction_passed": True,
                                   "correction_iterations": 1, "failure_reason": None}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = []
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.get = mock_get

    asyncio.run(run_pipeline(
        {"pr_id": "x", "diff": "x"}, "trace-t", _client=mock_client))
    assert fix_calls["n"] == 1


def test_pipeline_does_not_double_fix_when_callback_already_started_task():
    """If a callback already started a fix task, the fallback path must not start another."""
    import orchestrator.pipeline as pm
    from orchestrator.pipeline import run_pipeline
    from unittest.mock import MagicMock

    fix_calls = {"n": 0}

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = {**FAKE_INTEL, "previous_scans": []}
        elif "scan" in url:
            # Simulate: callback already ran and put a task in state
            if pm._pipeline_state is not None:
                async def already_done():
                    return {"mr_url": None, "service": "ssl-monitor",
                            "self_correction_passed": True, "correction_iterations": 1}
                pm._pipeline_state["tasks"]["ssl-monitor"] = asyncio.ensure_future(
                    already_done())
                pm._pipeline_state["hits"]["ssl-monitor"] = {}
            r.json.return_value = {
                "hits": [{"service": "ssl-monitor", "file_path": "main.py",
                          "matching_lines": [], "confidence": 0.9}]
            }
        elif "fix" in url:
            fix_calls["n"] += 1
            r.json.return_value = {"mr_url": None}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = []
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.get = mock_get

    asyncio.run(run_pipeline(
        {"pr_id": "x", "diff": "x"}, "trace-t", _client=mock_client))
    assert fix_calls["n"] == 0
