import os
import asyncio
import httpx
from fastapi import HTTPException

INTELLIGENCE_URL = os.environ.get("INTELLIGENCE_URL", "http://localhost:8001")
SCANNER_URL = os.environ.get("SCANNER_URL", "http://localhost:8002")
FIX_FACTORY_URL = os.environ.get("FIX_FACTORY_URL", "http://localhost:8003")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")


def get_service_list() -> list[dict]:
    namespace = os.environ.get("DEMO_NAMESPACE", "cypherguy-group/ripple-demo")
    services = [
        "payment-service", "auth-service", "order-service", "notification-service",
        "inventory-service", "billing-service", "reporting-service", "gateway-service",
        "user-service", "search-service", "analytics-service", "recommendation-service",
        "config-service", "audit-service", "session-service", "webhook-service",
        "cache-service", "scheduler-service", "export-service", "admin-service",
    ]
    return [
        {"name": s, "repo": f"{namespace}/{s}", "gitlab_namespace": f"{namespace}/{s}"}
        for s in services
    ]


def _safe_json(r: httpx.Response, fallback: dict) -> dict:
    try:
        return r.json()
    except Exception:
        return fallback


async def run_pipeline(
    payload: dict,
    trace_id: str,
    _client: httpx.AsyncClient | None = None,
) -> list[dict]:
    headers = {"X-Trace-Id": trace_id}
    close_client = _client is None

    if _client is None:
        _client = httpx.AsyncClient()

    try:
        # Intelligence
        try:
            intel_r = await _client.post(
                f"{INTELLIGENCE_URL}/analyze",
                json={"pr_id": payload["pr_id"], "repo": payload.get("repo", ""), "diff": payload.get("diff", "")},
                headers=headers,
                timeout=120,
            )
            intel = _safe_json(intel_r, {"pattern": payload.get("diff", ""), "incident_context": {}, "previous_scans": []})
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Intelligence service error: {e}")

        if not intel.get("pattern"):
            raise HTTPException(status_code=502, detail="Intelligence returned no pattern")

        # Scanner
        try:
            scan_r = await _client.post(
                f"{SCANNER_URL}/scan",
                json={
                    "pattern": intel["pattern"],
                    "incident_context": intel.get("incident_context", {}),
                    "services": get_service_list(),
                    "callback_url": f"{ORCHESTRATOR_URL}/internal/broadcast",
                },
                headers=headers,
                timeout=600,
            )
            hits = _safe_json(scan_r, {"hits": []}).get("hits", [])
        except Exception as e:
            return []

        # Fix Factory — one per hit, errors caught individually
        async def fix_one(hit: dict) -> dict | None:
            try:
                r = await _client.post(
                    f"{FIX_FACTORY_URL}/fix",
                    json={**hit, "incident_context": intel.get("incident_context", {})},
                    headers=headers,
                    timeout=360,
                )
                return _safe_json(r, {"service": hit.get("service"), "mr_url": None,
                                      "failure_reason": "bad response", "self_correction_passed": False})
            except Exception as e:
                return {"service": hit.get("service"), "mr_url": None,
                        "failure_reason": str(e), "self_correction_passed": False}

        results = await asyncio.gather(*[fix_one(h) for h in hits])
        return [r for r in results if r is not None]

    finally:
        if close_client:
            await _client.aclose()
