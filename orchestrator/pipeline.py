import os
import asyncio
import httpx

INTELLIGENCE_URL = os.environ.get("INTELLIGENCE_URL", "http://localhost:8001")
SCANNER_URL = os.environ.get("SCANNER_URL", "http://localhost:8002")
FIX_FACTORY_URL = os.environ.get("FIX_FACTORY_URL", "http://localhost:8003")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")


def get_service_list() -> list[dict]:
    services = [
        "payment-service", "auth-service", "order-service", "notification-service",
        "inventory-service", "billing-service", "reporting-service", "gateway-service",
        "user-service", "search-service", "analytics-service", "recommendation-service",
        "config-service", "audit-service", "session-service", "webhook-service",
        "cache-service", "scheduler-service", "export-service", "admin-service",
    ]
    return [
        {"name": s, "repo": f"ripple-demo/{s}", "gitlab_namespace": f"ripple-demo/{s}"}
        for s in services
    ]


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
        intel_r = await _client.post(
            f"{INTELLIGENCE_URL}/analyze",
            json={"pr_id": payload["pr_id"], "repo": payload.get("repo", ""), "diff": payload.get("diff", "")},
            headers=headers,
            timeout=60,
        )
        intel = intel_r.json()

        scan_r = await _client.post(
            f"{SCANNER_URL}/scan",
            json={
                "pattern": intel["pattern"],
                "incident_context": intel.get("incident_context", {}),
                "services": get_service_list(),
                "callback_url": f"{ORCHESTRATOR_URL}/internal/broadcast",
            },
            headers=headers,
            timeout=300,
        )
        hits = scan_r.json().get("hits", [])

        async def fix_one(hit: dict) -> dict:
            r = await _client.post(
                f"{FIX_FACTORY_URL}/fix",
                json={**hit, "incident_context": intel.get("incident_context", {})},
                headers=headers,
                timeout=120,
            )
            return r.json()

        return list(await asyncio.gather(*[fix_one(h) for h in hits]))

    finally:
        if close_client:
            await _client.aclose()
