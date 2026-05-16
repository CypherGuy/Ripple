"""
Live end-to-end test for the full Ripple pipeline.
Requires all four services running:
    uvicorn orchestrator.main:app --port 8000
    uvicorn intelligence.main:app --port 8001
    uvicorn scanner.main:app   --port 8002
    uvicorn fix_factory.main:app --port 8003

Run:
    pytest -m live -v tests/test_e2e_live.py
"""
import pytest
import httpx

WEBHOOK_URL = "http://localhost:8000/webhook"
TIMEOUT = 300

PAYLOAD = {
    "pr_id": "e2e-live-1",
    "repo": "org/payment-service",
    "diff": "@@ -12 +12 @@ response = requests.get(url)",
}


@pytest.mark.live
def test_webhook_returns_202():
    r = httpx.post(WEBHOOK_URL, json=PAYLOAD, timeout=TIMEOUT)
    assert r.status_code == 202


@pytest.mark.live
def test_webhook_response_has_status_accepted():
    r = httpx.post(WEBHOOK_URL, json=PAYLOAD, timeout=TIMEOUT)
    assert r.json()["status"] == "accepted"


@pytest.mark.live
def test_webhook_response_has_correct_pr_id():
    r = httpx.post(WEBHOOK_URL, json=PAYLOAD, timeout=TIMEOUT)
    assert r.json()["pr_id"] == "e2e-live-1"


@pytest.mark.live
def test_webhook_response_contains_fix_results_list():
    r = httpx.post(WEBHOOK_URL, json=PAYLOAD, timeout=TIMEOUT)
    assert isinstance(r.json()["fix_results"], list)
