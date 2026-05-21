import os
import asyncio
import logging
import httpx
from fastapi import HTTPException
from fix_factory.tools.mongodb_outcomes import record_feedback

logger = logging.getLogger(__name__)


def parse_mr_url(mr_url: str) -> tuple[str, str]:
    """Return (namespace, iid) from a GitLab MR URL."""
    parts = mr_url.split("/-/merge_requests/")
    namespace = parts[0].replace("https://gitlab.com/", "")
    iid = parts[1].split("/")[0]
    return namespace, iid


async def poll_mr_status(
    mr_url: str,
    service: str,
    pattern: str,
    gitlab_token: str,
    client: httpx.AsyncClient | None = None,
    poll_interval: int = 60,
    max_polls: int = 1440,  # 24 hours at 60s intervals
) -> None:
    namespace, iid = parse_mr_url(mr_url)
    encoded = namespace.replace("/", "%2F")
    api_url = f"https://gitlab.com/api/v4/projects/{encoded}/merge_requests/{iid}"
    internal_secret = os.environ.get("INTERNAL_SECRET", "")

    # Use injected client (tests) or create a fresh one (production)
    # A fresh client is needed because the pipeline client closes when run_pipeline finishes
    close_own = client is None
    poll_client = client if client is not None else httpx.AsyncClient()
    try:
        for i in range(max_polls):
            if poll_interval > 0 and i > 0:
                await asyncio.sleep(poll_interval)
            try:
                r = await poll_client.get(
                    api_url,
                    headers={"PRIVATE-TOKEN": gitlab_token},
                    timeout=10,
                )
                if r.status_code != 200:
                    continue
                state = r.json().get("state", "opened")
                if state in ("merged", "closed"):
                    record_feedback(
                        service=service,
                        mr_url=mr_url,
                        outcome=state,
                        pattern=pattern,
                        reason=f"Auto-detected from GitLab: {state}",
                    )
                    try:
                        await poll_client.post(
                            f"{ORCHESTRATOR_URL}/internal/broadcast",
                            json={"event": "feedback_recorded", "service": service,
                                  "outcome": state, "mr_url": mr_url},
                            headers={"X-Internal-Secret": internal_secret},
                            timeout=5,
                        )
                    except Exception:
                        pass
                    return
            except Exception:
                continue
    finally:
        if close_own:
            await poll_client.aclose()

INTELLIGENCE_URL = os.environ.get("INTELLIGENCE_URL", "http://localhost:8001")
SCANNER_URL = os.environ.get("SCANNER_URL", "http://localhost:8002")
FIX_FACTORY_URL = os.environ.get("FIX_FACTORY_URL", "http://localhost:8003")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")

# Services awaiting user approval: {service_name: {hit, intel, trace_id}}
_pending_approvals: dict[str, dict] = {}

# Active pipeline context - set while scanner is running so /internal/scan-event
# can trigger fix_hit per-hit without waiting for all scans to finish.
_pipeline_state: dict | None = None


def get_service_list() -> list[dict]:
    namespace = os.environ.get("DEMO_NAMESPACE", "cypherguy-group/pulsecheck")
    services = [
        "http-monitor", "ssl-monitor", "api-monitor", "github-monitor",
        "dns-checker", "latency-monitor", "slack-notifier", "email-notifier",
        "webhook-dispatcher", "incident-manager", "metrics-collector", "report-generator",
    ]
    return [
        {"name": s, "repo": f"{namespace}/{s}",
            "gitlab_namespace": f"{namespace}/{s}"}
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
            json={
                **hit, "incident_context": intel.get("incident_context", {})},
            headers=headers,
            timeout=360,
        )
        result = _safe_json(r, {"service": hit.get("service"), "mr_url": None,
                                "failure_reason": "bad response", "self_correction_passed": False})
    except Exception as e:
        return {"service": hit.get("service"), "mr_url": None,
                "failure_reason": str(e), "self_correction_passed": False}

    if result.get("mr_url"):
        gitlab_token = os.environ.get("GITLAB_TOKEN", "")
        pattern = intel.get("pattern", "")
        asyncio.create_task(poll_mr_status(
            mr_url=result["mr_url"],
            service=hit.get("service", ""),
            pattern=pattern,
            gitlab_token=gitlab_token,
        ))
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
                    "incident_id": intel.get("incident_context", {}).get("incident_id"),
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
        namespace = os.environ.get(
            "DEMO_NAMESPACE", "cypherguy-group/pulsecheck")
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
                        json={"event": "agent_started",
                              "service": svc["name"], "timestamp": ts},
                        headers={"X-Internal-Secret": internal_secret},
                        timeout=3,
                    )
                except Exception:
                    pass
        asyncio.create_task(_pre_broadcast())

        # Intelligence - fall back to diff-as-pattern on any failure so the pipeline
        # continues scanning even when Gemini is temporarily unavailable.
        fallback_intel = {
            "pattern": payload.get("diff", "HTTP call without timeout"),
            "risk_score": 8,
            "rationale": "Intelligence service unavailable; using raw diff as pattern.",
            "incident_context": payload.get("incident_context", {}),
            "previous_scans": [],
        }
        try:
            intel_r = await _client.post(
                f"{INTELLIGENCE_URL}/analyze",
                json={
                    "pr_id": payload["pr_id"],
                    "repo": payload.get("repo", ""),
                    "diff": payload.get("diff", ""),
                    "incident_context": payload.get("incident_context"),
                },
                headers=headers,
                timeout=120,
            )
            intel = _safe_json(intel_r, fallback_intel)
            if not intel.get("pattern"):
                logger.warning(
                    "Intelligence returned empty pattern; using diff fallback")
                intel = fallback_intel
            # Merge webhook-supplied incident_context as fallback when intel returns none
            if not intel.get("incident_context") and payload.get("incident_context"):
                intel["incident_context"] = payload["incident_context"]
        except Exception:
            logger.exception(
                "Intelligence service error - continuing with diff fallback")
            intel = fallback_intel

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
            logger.warning(
                "Pattern still empty after fallback; using raw diff")
            intel["pattern"] = payload.get("diff", "HTTP call without timeout")

        threshold = int(os.environ.get("AUTO_FIX_THRESHOLD", "7"))
        risk_score = int(intel.get("risk_score", 10))

        # Broadcast risk score so the dashboard incident panel can display it
        try:
            await _client.post(
                f"{ORCHESTRATOR_URL}/internal/broadcast",
                json={"event": "risk_scored", "risk_score": risk_score,
                      "pattern": intel.get("pattern", "")},
                headers={"X-Internal-Secret": internal_secret},
                timeout=5,
            )
        except Exception:
            pass

        # Set pipeline state so /internal/scan-event can start fix tasks per-hit
        # as scanning progresses, without waiting for all services to finish.
        # Only set for high-risk path - low-risk uses approval flow instead.
        global _pipeline_state
        if risk_score >= threshold:
            _pipeline_state = {
                "intel": intel,
                "trace_id": trace_id,
                "client": _client,
                "tasks": {},
                "hits": {},
            }

        # Scanner
        try:
            scan_r = await _client.post(
                f"{SCANNER_URL}/scan",
                json={
                    "pattern": intel["pattern"],
                    "incident_context": intel.get("incident_context", {}),
                    "services": services,
                    "callback_url": f"{ORCHESTRATOR_URL}/internal/scan-event",
                },
                headers=headers,
                timeout=600,
            )
            hits = _safe_json(scan_r, {"hits": []}).get("hits", [])
            # One MR per service - keep highest-confidence hit when a service has multiple
            seen: dict[str, dict] = {}
            for h in hits:
                svc = h.get("service", "")
                if svc not in seen or h.get("confidence", 0) > seen[svc].get("confidence", 0):
                    seen[svc] = h
            hits = list(seen.values())
        except Exception:
            # Scanner HTTP call failed but hit callbacks may still arrive via
            # /internal/scan-event - keep _pipeline_state alive so fix_hit fires.
            logger.exception(
                "Scanner call failed; keeping pipeline state for callbacks")
            hits = []

        if risk_score < threshold:
            _pipeline_state = None
            internal_secret = os.environ.get("INTERNAL_SECRET", "")
            for hit in hits:
                svc = hit.get("service", "")
                _pending_approvals[svc] = {
                    "hit": hit, "intel": intel, "trace_id": trace_id}
                try:
                    await _client.post(
                        f"{ORCHESTRATOR_URL}/internal/broadcast",
                        json={"event": "requires_approval", "service": svc,
                              "risk_score": risk_score, "pattern": intel.get("pattern", ""),
                              "file_path": hit.get("file_path", ""),
                              "confidence": hit.get("confidence", 0),
                              "gitlab_namespace": hit.get("gitlab_namespace", svc),
                              "approval_payload": {"hit": hit, "intel": intel, "trace_id": trace_id}},
                        headers={"X-Internal-Secret": internal_secret},
                        timeout=5,
                    )
                except Exception:
                    pass
            return []

        # Fallback: start fix tasks for any hits not already started via callback
        try:
            for h in hits:
                svc = h.get("service", "")
                if svc and svc not in _pipeline_state["hits"]:
                    _pipeline_state["hits"][svc] = h
                    _pipeline_state["tasks"][svc] = asyncio.create_task(
                        fix_hit(h, intel, trace_id, _client)
                    )

            if _pipeline_state["tasks"]:
                task_results = await asyncio.gather(
                    *_pipeline_state["tasks"].values(), return_exceptions=True
                )
                return [r for r in task_results if isinstance(r, dict)]
            return []
        finally:
            _pipeline_state = None

    except Exception:
        # Broadcast no_hit for all services so tiles don't get stuck on SCANNING
        logger.exception(
            "Pipeline crashed - broadcasting no_hit to unstick tiles")
        internal_secret = os.environ.get("INTERNAL_SECRET", "")
        try:
            svcs = await fetch_services_from_gitlab(
                os.environ.get("DEMO_NAMESPACE", "cypherguy-group/pulsecheck"),
                os.environ.get("GITLAB_TOKEN", ""), _client,
            )
            for svc in svcs:
                try:
                    await _client.post(
                        f"{ORCHESTRATOR_URL}/internal/broadcast",
                        json={"event": "no_hit", "service": svc["name"]},
                        headers={"X-Internal-Secret": internal_secret},
                        timeout=3,
                    )
                except Exception:
                    pass
        except Exception:
            pass
        return []
    finally:
        if close_client:
            await _client.aclose()
