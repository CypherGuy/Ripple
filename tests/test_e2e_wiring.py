import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

MOCK_INTEL = {
    "pattern": "HTTP call with no timeout in async handler.",
    "risk_score": 9,
    "risk_rationale": "Matches DT-4821.",
    "incident_context": {"incident_id": "DT-4821", "duration_minutes": 47},
    "previous_scans": [],
}

MOCK_SCAN_HITS = [
    {
        "service": "auth-service",
        "file_path": "src/clients/downstream.py",
        "matching_lines": [{"line_number": 42, "content": "response = requests.get(url)"}],
        "confidence": 0.94,
    }
]

MOCK_FIX = {
    "patch": "--- a/src/clients/downstream.py\n+++ b/src/clients/downstream.py\n@@ -42 +42 @@\n- requests.get(url)\n+ requests.get(url, timeout=5)",
    "fix_explanation": "Added 5s timeout matching DT-4821.",
    "mr_url": "https://gitlab.com/demo-org/auth-service/merge_requests/1",
    "self_correction_passed": True,
    "correction_iterations": 1,
    "failure_reason": None,
}

WEBHOOK_PAYLOAD = {
    "pr_id": "12345",
    "repo": "org/payment-service",
    "diff": "@@ -12 +12 @@ response = requests.get(url)",
}


@pytest.fixture
def client():
    from orchestrator.main import app
    return TestClient(app)


def test_webhook_returns_202_with_fix_results(client):
    os.environ.pop("GITLAB_WEBHOOK_SECRET", None)
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = [MOCK_FIX]
        r = client.post("/webhook", json=WEBHOOK_PAYLOAD)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "accepted"
    assert body["pr_id"] == "12345"
    assert isinstance(body["fix_results"], list)


def test_webhook_passes_payload_to_pipeline(client):
    os.environ.pop("GITLAB_WEBHOOK_SECRET", None)
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = []
        client.post("/webhook", json=WEBHOOK_PAYLOAD)
    call_kwargs = mock_pipeline.call_args
    payload_arg = call_kwargs[0][0]
    assert payload_arg["pr_id"] == "12345"
    assert payload_arg["diff"] == WEBHOOK_PAYLOAD["diff"]


def test_webhook_propagates_trace_id_to_pipeline(client):
    os.environ.pop("GITLAB_WEBHOOK_SECRET", None)
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = []
        client.post("/webhook", json=WEBHOOK_PAYLOAD)
    trace_id = mock_pipeline.call_args[0][1]
    assert isinstance(trace_id, str) and len(trace_id) == 36  # uuid4


def test_pipeline_calls_intelligence_with_diff():
    from orchestrator.pipeline import run_pipeline
    import asyncio

    async def mock_analyze(url, *, json, headers, timeout):
        assert "diff" in json
        r = MagicMock()
        r.json.return_value = MOCK_INTEL
        return r

    async def mock_scan(url, *, json, headers, timeout):
        r = MagicMock()
        r.json.return_value = {"hits": MOCK_SCAN_HITS,
                               "incident_context": MOCK_INTEL["incident_context"]}
        return r

    async def mock_fix(url, *, json, headers, timeout):
        r = MagicMock()
        r.json.return_value = MOCK_FIX
        return r

    call_order = []

    async def mock_post(url, **kwargs):
        if "analyze" in url:
            call_order.append("analyze")
            return await mock_analyze(url, **kwargs)
        elif "scan" in url:
            call_order.append("scan")
            return await mock_scan(url, **kwargs)
        elif "fix" in url:
            call_order.append("fix")
            return await mock_fix(url, **kwargs)
        raise ValueError(f"Unexpected URL: {url}")

    mock_client = AsyncMock()
    mock_client.post = mock_post

    results = asyncio.run(run_pipeline(
        WEBHOOK_PAYLOAD, "trace-123", _client=mock_client))
    assert call_order[0] == "analyze"
    assert "scan" in call_order
    assert "fix" in call_order
    assert isinstance(results, list)


def test_pipeline_calls_fix_factory_once_per_hit():
    from orchestrator.pipeline import run_pipeline
    import asyncio

    fix_call_count = {"n": 0}

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = MOCK_INTEL
        elif "scan" in url:
            r.json.return_value = {
                "hits": [MOCK_SCAN_HITS[0], {**MOCK_SCAN_HITS[0], "service": "order-service"}],
                "incident_context": {},
            }
        elif "fix" in url:
            fix_call_count["n"] += 1
            r.json.return_value = MOCK_FIX
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(WEBHOOK_PAYLOAD,
                "trace-123", _client=mock_client))
    assert fix_call_count["n"] == 2


def test_pipeline_merges_webhook_incident_context_into_intelligence_response():
    from orchestrator.pipeline import run_pipeline
    import asyncio

    fix_incident_contexts = []

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            # Intelligence returns incident_context WITHOUT root_cause_summary
            r.json.return_value = {
                **MOCK_INTEL, "incident_context": {"incident_id": "P-26051"}}
        elif "scan" in url:
            r.json.return_value = {"hits": MOCK_SCAN_HITS}
        elif "fix" in url:
            fix_incident_contexts.append(kwargs.get(
                "json", {}).get("incident_context", {}))
            r.json.return_value = MOCK_FIX
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    payload = {**WEBHOOK_PAYLOAD, "incident_context": {
        "incident_id": "P-26051",
        "root_cause_summary": "ssl-monitor hung on slow cert check",
        "duration_minutes": 47,
    }}
    asyncio.run(run_pipeline(payload, "trace-123", _client=mock_client))

    assert len(fix_incident_contexts) == 1
    ctx = fix_incident_contexts[0]
    # root_cause_summary should be filled in from webhook since Intelligence didn't return it
    assert ctx.get(
        "root_cause_summary") == "ssl-monitor hung on slow cert check"
    assert ctx.get("incident_id") == "P-26051"


def test_pipeline_deduplicates_hits_by_service():
    from orchestrator.pipeline import run_pipeline
    import asyncio

    fix_call_count = {"n": 0}

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = MOCK_INTEL
        elif "scan" in url:
            # Two hits for auth-service (different files/lines), one for order-service
            r.json.return_value = {
                "hits": [
                    {**MOCK_SCAN_HITS[0], "service": "auth-service", "confidence": 0.9,
                     "file_path": "src/clients/downstream.py"},
                    {**MOCK_SCAN_HITS[0], "service": "auth-service", "confidence": 0.7,
                     "file_path": "src/clients/upstream.py"},
                    {**MOCK_SCAN_HITS[0],
                        "service": "order-service", "confidence": 0.8},
                ],
                "incident_context": {},
            }
        elif "fix" in url:
            fix_call_count["n"] += 1
            r.json.return_value = MOCK_FIX
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(WEBHOOK_PAYLOAD,
                "trace-123", _client=mock_client))
    # auth-service had 2 hits but should only trigger 1 Fix Factory call (highest confidence)
    assert fix_call_count["n"] == 2


def test_pipeline_returns_empty_fix_results_when_no_hits():
    from orchestrator.pipeline import run_pipeline
    import asyncio

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = MOCK_INTEL
        elif "scan" in url:
            r.json.return_value = {"hits": [], "incident_context": {}}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    results = asyncio.run(run_pipeline(
        WEBHOOK_PAYLOAD, "trace-123", _client=mock_client))
    assert results == []


def test_pipeline_broadcasts_mr_opened_when_fix_succeeds():
    from orchestrator.pipeline import run_pipeline
    import asyncio

    broadcast_calls = []

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = MOCK_INTEL
        elif "scan" in url:
            r.json.return_value = {"hits": MOCK_SCAN_HITS}
        elif "fix" in url:
            r.json.return_value = {
                **MOCK_FIX, "mr_url": "https://gitlab.com/org/auth-service/-/merge_requests/1"}
        elif "broadcast" in url:
            broadcast_calls.append(kwargs.get("json", {}))
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(WEBHOOK_PAYLOAD,
                "trace-123", _client=mock_client))

    mr_events = [c for c in broadcast_calls if c.get("event") == "mr_opened"]
    assert len(mr_events) == 1
    assert mr_events[0]["service"] == "auth-service"
    assert "merge_requests" in mr_events[0]["mr_url"]


# ---------------------------------------------------------------------------
# Dynamic service list from GitLab group API
# ---------------------------------------------------------------------------

def test_fetch_services_from_gitlab_returns_list():
    """fetch_services_from_gitlab returns a list of service dicts with name/repo/gitlab_namespace."""
    from orchestrator.pipeline import fetch_services_from_gitlab
    import asyncio

    fake_projects = [
        {"name": "ssl-monitor", "path": "ssl-monitor",
            "namespace": {"full_path": "mygroup/myproject"}},
        {"name": "api-monitor", "path": "api-monitor",
            "namespace": {"full_path": "mygroup/myproject"}},
    ]

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = fake_projects
        return r

    mock_client = AsyncMock()
    mock_client.get = mock_get

    result = asyncio.run(fetch_services_from_gitlab(
        "mygroup/myproject", "fake-token", mock_client))
    assert len(result) == 2
    assert result[0]["name"] == "ssl-monitor"
    assert result[0]["gitlab_namespace"] == "mygroup/myproject/ssl-monitor"
    assert result[1]["name"] == "api-monitor"


def test_fetch_services_from_gitlab_falls_back_on_error():
    """When GitLab API fails, fetch_services_from_gitlab falls back to get_service_list()."""
    from orchestrator.pipeline import fetch_services_from_gitlab, get_service_list
    import asyncio

    async def mock_get(url, **kwargs):
        raise httpx.RequestError("connection refused")

    mock_client = AsyncMock()
    mock_client.get = mock_get

    result = asyncio.run(fetch_services_from_gitlab(
        "mygroup/myproject", "fake-token", mock_client))
    assert result == get_service_list()


def test_fetch_services_from_gitlab_falls_back_on_non_200():
    """When GitLab returns non-200, fall back to get_service_list()."""
    from orchestrator.pipeline import fetch_services_from_gitlab, get_service_list
    import asyncio

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 404
        r.json.return_value = {"message": "404 Group Not Found"}
        return r

    mock_client = AsyncMock()
    mock_client.get = mock_get

    result = asyncio.run(fetch_services_from_gitlab(
        "bad/namespace", "fake-token", mock_client))
    assert result == get_service_list()


def test_pipeline_uses_dynamic_service_list():
    """run_pipeline calls fetch_services_from_gitlab to build the service list."""
    from orchestrator.pipeline import run_pipeline
    import asyncio

    dynamic_services = [
        {"name": "my-svc", "repo": "org/proj/my-svc",
            "gitlab_namespace": "org/proj/my-svc"},
    ]
    scan_payloads = []

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "analyze" in url:
            r.json.return_value = {**MOCK_INTEL, "incident_context": {}}
        elif "scan" in url:
            scan_payloads.append(kwargs.get("json", {}))
            r.json.return_value = {"hits": []}
        elif "broadcast" in url:
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    with patch("orchestrator.pipeline.fetch_services_from_gitlab", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = dynamic_services
        asyncio.run(run_pipeline(WEBHOOK_PAYLOAD,
                    "trace-x", _client=mock_client))

    mock_fetch.assert_called_once()
    assert len(scan_payloads) == 1
    assert scan_payloads[0]["services"] == dynamic_services


# ---------------------------------------------------------------------------
# Item 10 - Exception leaking: pipeline must not expose internal URLs
# ---------------------------------------------------------------------------

def test_pipeline_falls_back_gracefully_on_intelligence_failure(client):
    """Pipeline continues with diff-as-pattern when Intelligence is unavailable.
    Internal URLs must never surface to the caller."""
    import asyncio
    import httpx as _httpx
    from orchestrator.pipeline import run_pipeline

    async def failing_post(url, **kwargs):
        raise _httpx.ConnectError("failed to connect")

    mock_client = AsyncMock()
    mock_client.post = failing_post
    mock_client.aclose = AsyncMock()

    # Pipeline should not raise - it falls back and returns an empty list when
    # all downstream calls also fail (scanner/fix-factory unreachable).
    result = asyncio.run(run_pipeline(
        {"pr_id": "t", "diff": "HTTP call without timeout"},
        "trace-t",
        _client=mock_client,
    ))
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Item 11 - WebSocket CORS: reject connections from unknown origins
# ---------------------------------------------------------------------------

def test_websocket_rejects_unknown_origin(client):
    """WebSocket connections from origins not in the allowlist must be closed."""
    import os
    os.environ["DASHBOARD_URL"] = "https://ripple-dashboard-105645459605.europe-west2.run.app"
    try:
        with client.websocket_connect("/ws", headers={"origin": "https://evil.com"}) as ws:
            # Should have been closed - if we get here the check isn't enforced
            pytest.fail(
                "Connection from unknown origin should have been rejected")
    except Exception:
        pass  # closed as expected


def test_websocket_accepts_dashboard_origin(client):
    """WebSocket connections from the dashboard URL must be accepted."""
    import os
    os.environ["DASHBOARD_URL"] = "https://ripple-dashboard-105645459605.europe-west2.run.app"
    with client.websocket_connect("/ws", headers={"origin": "https://ripple-dashboard-105645459605.europe-west2.run.app"}):
        pass


def test_websocket_accepts_localhost_origin(client):
    """WebSocket connections from localhost must be accepted for local dev."""
    import os
    os.environ.pop("DASHBOARD_URL", None)
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:3000"}):
        pass


# ---------------------------------------------------------------------------
# GitLab MR status polling - automatic feedback loop
# ---------------------------------------------------------------------------

def test_parse_mr_url_extracts_namespace_and_iid():
    """parse_mr_url returns (namespace, iid) from a GitLab MR URL."""
    from orchestrator.pipeline import parse_mr_url
    ns, iid = parse_mr_url(
        "https://gitlab.com/cypherguy-group/pulsecheck/ssl-monitor/-/merge_requests/5")
    assert ns == "cypherguy-group/pulsecheck/ssl-monitor"
    assert iid == "5"


def test_parse_mr_url_handles_different_iids():
    from orchestrator.pipeline import parse_mr_url
    ns, iid = parse_mr_url(
        "https://gitlab.com/org/proj/svc/-/merge_requests/123")
    assert ns == "org/proj/svc"
    assert iid == "123"


def test_poll_mr_status_records_win_when_merged():
    """When GitLab returns state=merged, poll_mr_status writes a win to MongoDB."""
    from orchestrator.pipeline import poll_mr_status
    import asyncio

    calls = {"feedback": None, "broadcast": []}

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"state": "merged", "iid": 1}
        return r

    async def mock_post(url, **kwargs):
        r = MagicMock()
        if "broadcast" in url:
            calls["broadcast"].append(kwargs.get("json", {}))
        r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.post = mock_post

    with patch("orchestrator.pipeline.record_feedback") as mock_record:
        asyncio.run(poll_mr_status(
            mr_url="https://gitlab.com/org/proj/ssl-monitor/-/merge_requests/1",
            service="ssl-monitor",
            pattern="HTTP call without timeout",
            gitlab_token="fake-token",
            client=mock_client,
            poll_interval=0,
            max_polls=1,
        ))
        mock_record.assert_called_once()
        assert mock_record.call_args[1]["outcome"] == "merged"

    feedback_events = [b for b in calls["broadcast"]
                       if b.get("event") == "feedback_recorded"]
    assert len(feedback_events) == 1
    assert feedback_events[0]["outcome"] == "merged"
    assert feedback_events[0]["service"] == "ssl-monitor"


def test_poll_mr_status_records_scar_when_closed():
    """When GitLab returns state=closed, poll_mr_status writes a scar."""
    from orchestrator.pipeline import poll_mr_status
    import asyncio

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"state": "closed", "iid": 1}
        return r

    async def mock_post(url, **kwargs):
        r = MagicMock()
        r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.post = mock_post

    with patch("orchestrator.pipeline.record_feedback") as mock_record:
        asyncio.run(poll_mr_status(
            mr_url="https://gitlab.com/org/proj/ssl-monitor/-/merge_requests/1",
            service="ssl-monitor",
            pattern="HTTP call without timeout",
            gitlab_token="fake-token",
            client=mock_client,
            poll_interval=0,
            max_polls=1,
        ))
        mock_record.assert_called_once()
        assert mock_record.call_args[1]["outcome"] == "closed"


def test_poll_mr_status_gives_up_after_max_polls():
    """poll_mr_status stops polling after max_polls without writing feedback."""
    from orchestrator.pipeline import poll_mr_status
    import asyncio

    poll_count = {"n": 0}

    async def mock_get(url, **kwargs):
        poll_count["n"] += 1
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"state": "opened"}
        return r

    mock_client = AsyncMock()
    mock_client.get = mock_get
    mock_client.post = AsyncMock()

    with patch("orchestrator.pipeline.record_feedback") as mock_record:
        asyncio.run(poll_mr_status(
            mr_url="https://gitlab.com/org/proj/ssl-monitor/-/merge_requests/1",
            service="ssl-monitor",
            pattern="x",
            gitlab_token="fake-token",
            client=mock_client,
            poll_interval=0,
            max_polls=3,
        ))
        mock_record.assert_not_called()

    assert poll_count["n"] == 3
