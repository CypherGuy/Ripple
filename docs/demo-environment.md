# Ripple — Demo Environment Specification

*Must be set up before Scanner development begins (step 5 in build order).*

---

## The Canonical Incident

All demo tooling is built around a single incident. The "47-minute outage" shown in the demo at 0:00–0:20 is this incident.

| Field | Value |
|---|---|
| Incident ID | DT-4821 |
| Title | Payment service cascade failure — no timeout on HTTP client |
| Duration | 47 minutes |
| Estimated cost | £23,000 |
| Root cause | `requests.get()` called with no timeout inside async handler; thread pool exhaustion cascaded to auth-service and order-service |
| Trace ID | *(replace with real Dynatrace trace ID once MCP integration is validated in step 1)* |

---

## GitLab Demo Group

20 services in a single GitLab group (`demo-org/backend`). Scanner spawns one agent per service = 20 agents in the fan-out.

### Services With the Hit (7) — light up red

These repos contain the dangerous pattern and are the ones Ripple opens fix MRs against.

| Service | File | Matching line |
|---|---|---|
| `payment-service` | `src/http/client.py` | `response = requests.get(f"{BASE_URL}/charge", headers=auth_headers)` |
| `auth-service` | `src/clients/downstream.py` | `response = requests.get(url)` |
| `order-service` | `src/http/external.py` | `result = httpx.get(endpoint)` |
| `notification-service` | `src/senders/email.py` | `r = requests.post(url, data=payload)` |
| `inventory-service` | `src/sync/upstream.py` | `data = requests.get(url, headers=headers)` |
| `billing-service` | `src/integrations/stripe.py` | `resp = http_client.get(path)` |
| `reporting-service` | `src/fetch/warehouse.py` | `rows = requests.get(url, params=filters)` |

### Services Without the Hit (13) — light up green

These repos already use timeouts. They show green on the dashboard and are part of the visual impact.

`gateway-service`, `user-service`, `search-service`, `analytics-service`, `recommendation-service`, `config-service`, `audit-service`, `session-service`, `webhook-service`, `cache-service`, `scheduler-service`, `export-service`, `admin-service`

---

## MongoDB Seed Data

Pre-seeded before the demo. Without this, the institutional memory feature has nothing to show on first run.

This data is what appears in the "previous scans" field of the Intelligence response and in the per-service briefings passed to Scanner agents.

### Scars (rejected fixes — pattern was flagged but fix MR was turned down)

```json
[
  {
    "pattern": "HTTP call with no timeout in async context",
    "service": "gateway-service",
    "outcome": "rejected",
    "reason": "Timeout intentionally absent — call is to an internal sidecar with sub-millisecond guaranteed response time. Risk suppressed for this service.",
    "risk_adjustment": -3,
    "date": "2026-01-12"
  },
  {
    "pattern": "HTTP call with no timeout in async context",
    "service": "config-service",
    "outcome": "rejected",
    "reason": "Config fetch runs at startup only — blocking is intentional, service does not start until config is loaded.",
    "risk_adjustment": -2,
    "date": "2026-03-08"
  }
]
```

### Wins (accepted fixes — fix MR merged, no incidents since)

```json
[
  {
    "pattern": "HTTP call with no timeout in async context",
    "service": "auth-service",
    "outcome": "merged",
    "reason": "Added 5s timeout to downstream call. No incidents in auth-service in the 83 days since fix merged.",
    "confidence_boost": 2,
    "date": "2026-02-20"
  },
  {
    "pattern": "HTTP call with no timeout in async context",
    "service": "session-service",
    "outcome": "merged",
    "reason": "Added 3s timeout. PR merged without modification by the service owner.",
    "confidence_boost": 1,
    "date": "2026-04-01"
  }
]
```

**What this enables in the demo:** Intelligence can say "Ripple has seen this pattern before — accepted in auth-service and session-service, intentionally suppressed in gateway-service and config-service." The institutional memory is tangible rather than hypothetical.

---

## The Triggering PR

A developer submits a PR to `payment-service` that introduces (or preserves) a timeout-less HTTP call. This is the PR that fires the Orchestrator webhook at 0:20 in the demo.

```python
# payment-service: src/http/client.py  — the change in the PR
response = requests.get(f"{BASE_URL}/charge", headers=auth_headers)
```

Orchestrator receives the GitLab webhook → Intelligence matches it to DT-4821 → Scanner fans out to all 20 services.

---

## Demo Flow Mapping

| Time | What the viewer sees | What is actually happening |
|---|---|---|
| 0:00–0:20 | Dynatrace dashboard — DT-4821, 47 min outage, trace visible | Real Dynatrace incident open in browser |
| 0:20–0:40 | Developer submits PR, Ripple fires | GitLab webhook → Orchestrator → Intelligence → Orchestrator |
| 0:40–1:30 | 20 agents fan out on dashboard, services light up green/red in real time | Scanner streaming `agent_started`/`hit_found`/`no_hit` events via WebSocket |
| 1:30–2:00 | "Found in 7 services. Three different developers. The same pattern." | Dashboard summary after all Scanner agents complete |
| 2:00–2:30 | Fix MRs appear in GitLab with incident context in each description | Fix Factory has opened 7 MRs |
| 2:30–3:00 | "If Ripple had existed 3 weeks ago, the outage wouldn't have happened." | Verbal close — no new UI needed |

---

## Setup Checklist

- [ ] Create `demo-org` GitLab group with 20 repos
- [ ] Add the timeout-less HTTP calls to the 7 hit services (exact lines above)
- [ ] Ensure the 13 clean services have timeout-guarded HTTP clients
- [ ] Seed MongoDB with the scars and wins above
- [ ] Confirm DT-4821 (or equivalent) exists in the Dynatrace instance with a real accessible trace
- [ ] Record the real Dynatrace trace ID and update `incident_context.trace_id` in the seed data
- [ ] Configure the GitLab webhook on `payment-service` to point at the deployed Orchestrator endpoint
- [ ] Run one full end-to-end test with a dummy PR before recording the demo video
