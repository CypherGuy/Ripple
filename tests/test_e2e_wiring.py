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
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = [MOCK_FIX]
        r = client.post("/webhook", json=WEBHOOK_PAYLOAD)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "accepted"
    assert body["pr_id"] == "12345"
    assert isinstance(body["fix_results"], list)


def test_webhook_passes_payload_to_pipeline(client):
    with patch("orchestrator.routes.webhook.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = []
        client.post("/webhook", json=WEBHOOK_PAYLOAD)
    call_kwargs = mock_pipeline.call_args
    payload_arg = call_kwargs[0][0]
    assert payload_arg["pr_id"] == "12345"
    assert payload_arg["diff"] == WEBHOOK_PAYLOAD["diff"]


def test_webhook_propagates_trace_id_to_pipeline(client):
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
        r.json.return_value = {"hits": MOCK_SCAN_HITS, "incident_context": MOCK_INTEL["incident_context"]}
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

    results = asyncio.run(run_pipeline(WEBHOOK_PAYLOAD, "trace-123", _client=mock_client))
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

    asyncio.run(run_pipeline(WEBHOOK_PAYLOAD, "trace-123", _client=mock_client))
    assert fix_call_count["n"] == 2


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
                    {**MOCK_SCAN_HITS[0], "service": "order-service", "confidence": 0.8},
                ],
                "incident_context": {},
            }
        elif "fix" in url:
            fix_call_count["n"] += 1
            r.json.return_value = MOCK_FIX
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(WEBHOOK_PAYLOAD, "trace-123", _client=mock_client))
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

    results = asyncio.run(run_pipeline(WEBHOOK_PAYLOAD, "trace-123", _client=mock_client))
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
            r.json.return_value = {**MOCK_FIX, "mr_url": "https://gitlab.com/org/auth-service/-/merge_requests/1"}
        elif "broadcast" in url:
            broadcast_calls.append(kwargs.get("json", {}))
            r.json.return_value = {"ok": True}
        return r

    mock_client = AsyncMock()
    mock_client.post = mock_post

    asyncio.run(run_pipeline(WEBHOOK_PAYLOAD, "trace-123", _client=mock_client))

    mr_events = [c for c in broadcast_calls if c.get("event") == "mr_opened"]
    assert len(mr_events) == 1
    assert mr_events[0]["service"] == "auth-service"
    assert "merge_requests" in mr_events[0]["mr_url"]
