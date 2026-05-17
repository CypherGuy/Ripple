import os
import asyncio
import httpx
from fastapi import HTTPException

INTELLIGENCE_URL = os.environ.get("INTELLIGENCE_URL", "http://localhost:8001")
SCANNER_URL = os.environ.get("SCANNER_URL", "http://localhost:8002")
FIX_FACTORY_URL = os.environ.get("FIX_FACTORY_URL", "http://localhost:8003")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")

# Services awaiting user approval: {service_name: {hit, intel, trace_id}}
_pending_approvals: dict[str, dict] = {}


def get_service_list() -> list[dict]:
    namespace = os.environ.get("DEMO_NAMESPACE", "cypherguy-group/pulsecheck")
    services = [
        "http-monitor", "ssl-monitor", "api-monitor", "github-monitor",
        "dns-checker", "latency-monitor", "slack-notifier", "email-notifier",
        "webhook-dispatcher", "incident-manager", "metrics-collector", "report-generator",
    ]
    return [
        {"name": s, "repo": f"{namespace}/{s}", "gitlab_namespace": f"{namespace}/{s}"}
        for s in services
    ]


async def fetch_services_from_gitlab(
    namespace: str,
    token: str,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Discover services by listing repos in a GitLab group. Falls back to get_service_list()."""
    encoded = namespace.replace("/", "%2F")
    try:
        r = await client.get(
            f"https://gitlab.com/api/v4/groups/{encoded}/projects",
            headers={"PRIVATE-TOKEN": token},
            params={"per_page": 100, "archived": "false"},
            timeout=10,
        )
        if r.status_code != 200:
            return get_service_list()
        projects = r.json()
        return [
            {
                "name": p["path"],
                "repo": f"{namespace}/{p['path']}",
                "gitlab_namespace": f"{namespace}/{p['path']}",
            }
            for p in projects
        ]
    except Exception:
        return get_service_list()


def _safe_json(r: httpx.Response, fallback: dict) -> dict:
    try:
        return r.json()
    except Exception:
        return fallback


async def fix_hit(
    hit: dict,
    intel: dict,
    trace_id: str,
    client: httpx.AsyncClient,
) -> dict | None:
    headers = {"X-Trace-Id": trace_id}
    try:
        r = await client.post(
            f"{FIX_FACTORY_URL}/fix",
            json={**hit, "incident_context": intel.get("incident_context", {})},
            headers=headers,
            timeout=360,
        )
        result = _safe_json(r, {"service": hit.get("service"), "mr_url": None,
                                "failure_reason": "bad response", "self_correction_passed": False})
    except Exception as e:
        return {"service": hit.get("service"), "mr_url": None,
                "failure_reason": str(e), "self_correction_passed": False}

    if result.get("mr_url"):
        try:
            internal_secret = os.environ.get("INTERNAL_SECRET", "")
            await client.post(
                f"{ORCHESTRATOR_URL}/internal/broadcast",
                json={
                    "event": "mr_opened",
                    "service": hit.get("service"),
                    "mr_url": result["mr_url"],
                    "evaluated_on": result.get("evaluated_on", "technical_merit"),
                    "correction_iterations": result.get("correction_iterations", 1),
                },
                headers={"X-Internal-Secret": internal_secret},
                timeout=5,
            )
        except Exception:
            pass

    return result


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
        # Discover services dynamically from GitLab group API
        namespace = os.environ.get("DEMO_NAMESPACE", "cypherguy-group/pulsecheck")
        gitlab_token = os.environ.get("GITLAB_TOKEN", "")
        services = await fetch_services_from_gitlab(namespace, gitlab_token, _client)

        # Immediately fan out agent_started events so tiles go amber without waiting for Intelligence
        internal_secret = os.environ.get("INTERNAL_SECRET", "")
        async def _pre_broadcast():
            import datetime
            ts = datetime.datetime.now(datetime.UTC).isoformat()
            for svc in services:
                try:
                    await _client.post(
                        f"{ORCHESTRATOR_URL}/internal/broadcast",
                        json={"event": "agent_started", "service": svc["name"], "timestamp": ts},
                        headers={"X-Internal-Secret": internal_secret},
                        timeout=3,
                    )
                except Exception:
                    pass
        asyncio.create_task(_pre_broadcast())

        # Intelligence
        try:
            intel_r = await _client.post(
                f"{INTELLIGENCE_URL}/analyze",
                json={"pr_id": payload["pr_id"], "repo": payload.get("repo", ""), "diff": payload.get("diff", "")},
                headers=headers,
                timeout=120,
            )
            intel = _safe_json(intel_r, {"pattern": payload.get("diff", ""), "incident_context": {}, "previous_scans": []})
            # Merge webhook-supplied incident_context as fallback when intel returns none
            if not intel.get("incident_context") and payload.get("incident_context"):
                intel["incident_context"] = payload["incident_context"]
        except Exception as e:
            raise HTTPException(status_code=502, detail="upstream service error")

        # Normalise Intelligence's incident_context:
        # - map Dynatrace field names to Ripple's expected names
        # - remove internal event.id so Gemini can't cite it instead of the display ID
        # - fill remaining gaps from the webhook-provided incident_context
        intel_ctx = intel.get("incident_context", {})
        if intel_ctx.get("display_id") and not intel_ctx.get("incident_id"):
            intel_ctx["incident_id"] = intel_ctx["display_id"]
        if intel_ctx.get("event.description") and not intel_ctx.get("root_cause_summary"):
            intel_ctx["root_cause_summary"] = intel_ctx["event.description"][:500]
        intel_ctx.pop("event.id", None)

        _MISSING = {"", "no summary provided.", "no summary provided", "none"}
        for key, val in payload.get("incident_context", {}).items():
            current = intel_ctx.get(key, "")
            if not current or (isinstance(current, str) and current.strip().lower() in _MISSING):
                intel_ctx[key] = val
        intel["incident_context"] = intel_ctx

        if not intel.get("pattern"):
            raise HTTPException(status_code=502, detail="Intelligence returned no pattern")

        # Scanner
        try:
            scan_r = await _client.post(
                f"{SCANNER_URL}/scan",
                json={
                    "pattern": intel["pattern"],
                    "incident_context": intel.get("incident_context", {}),
                    "services": services,
                    "callback_url": f"{ORCHESTRATOR_URL}/internal/broadcast",
                },
                headers=headers,
                timeout=600,
            )
            hits = _safe_json(scan_r, {"hits": []}).get("hits", [])
            # One MR per service — keep highest-confidence hit when a service has multiple
            seen: dict[str, dict] = {}
            for h in hits:
                svc = h.get("service", "")
                if svc not in seen or h.get("confidence", 0) > seen[svc].get("confidence", 0):
                    seen[svc] = h
            hits = list(seen.values())
        except Exception as e:
            return []

        threshold = int(os.environ.get("AUTO_FIX_THRESHOLD", "7"))
        risk_score = int(intel.get("risk_score", 10))

        if risk_score < threshold:
            # Broadcast requires_approval for each hit and store for later approval
            internal_secret = os.environ.get("INTERNAL_SECRET", "")
            for hit in hits:
                svc = hit.get("service", "")
                _pending_approvals[svc] = {"hit": hit, "intel": intel, "trace_id": trace_id}
                try:
                    await _client.post(
                        f"{ORCHESTRATOR_URL}/internal/broadcast",
                        json={"event": "requires_approval", "service": svc,
                              "risk_score": risk_score, "pattern": intel.get("pattern", "")},
                        headers={"X-Internal-Secret": internal_secret},
                        timeout=5,
                    )
                except Exception:
                    pass
            return []

        # Fix Factory — one per hit, errors caught individually
        results = await asyncio.gather(*[fix_hit(h, intel, trace_id, _client) for h in hits])
        return [r for r in results if r is not None]

    finally:
        if close_client:
            await _client.aclose()
