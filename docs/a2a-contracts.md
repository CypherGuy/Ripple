# Ripple — A2A Message Contracts

Agreed during planning session (May 15 2026). These are the data shapes passed between services via A2A.

---

## Orchestrator → Intelligence

The PR diff and GitLab metadata for the incoming PR.

```json
{
  "pr_id": "12345",
  "pr_url": "https://gitlab.com/org/payment-service/merge_requests/12345",
  "repo": "org/payment-service",
  "branch": "feature/update-timeout-config",
  "target_branch": "main",
  "author": "dev@example.com",
  "commit_sha": "abc123def456",
  "changed_files": [
    {
      "path": "src/http/client.py",
      "patch": "@@ -12,6 +12,8 @@\n-  timeout=None\n+  timeout=5000"
    }
  ],
  "diff": "<full unified diff string>"
}
```

---

## Intelligence → Orchestrator

- **Pattern** — natural language description of the semantic risk behaviour
- **Risk score** — integer 1–10
- **Dynatrace incident context** — the incident(s) that proved this pattern is dangerous
- **Previous scans** — matching MongoDB records used for risk score adjustment

```json
{
  "pattern": "Synchronous HTTP call inside an async handler with no timeout configured, causing downstream cascade failures under load.",
  "risk_score": 9,
  "risk_rationale": "Matches incident DT-4821 — identical configuration caused a 47-minute outage on 2026-02-14.",
  "incident_context": {
    "incident_id": "DT-4821",
    "title": "Payment service cascade failure — no timeout on HTTP client",
    "duration_minutes": 47,
    "estimated_cost": "£23,000",
    "root_cause_summary": "HTTP client with no timeout caused thread pool exhaustion under load, cascading to auth-service and order-service.",
    "trace_id": "abc123xyz789",
    "affected_services": ["payment-service", "auth-service", "order-service"]
  },
  "previous_scans": [
    {
      "pattern_similarity": 0.91,
      "outcome": "merged",
      "service": "auth-service",
      "risk_adjustment": 1
    }
  ]
}
```

---

## Orchestrator → Scanner

- **Pattern** — the natural language description from Intelligence
- **Incident context** — forwarded unchanged from the Intelligence response
- **Services** — list of services to scan, sourced from Dynatrace service map (see D11)

```json
{
  "pattern": "Synchronous HTTP call inside an async handler with no timeout configured, causing downstream cascade failures under load.",
  "incident_context": {
    "incident_id": "DT-4821",
    "title": "Payment service cascade failure — no timeout on HTTP client",
    "duration_minutes": 47,
    "estimated_cost": "£23,000",
    "root_cause_summary": "HTTP client with no timeout caused thread pool exhaustion under load.",
    "trace_id": "abc123xyz789",
    "affected_services": ["payment-service", "auth-service", "order-service"]
  },
  "services": [
    {
      "name": "payment-service",
      "repo": "org/payment-service",
      "gitlab_namespace": "org/backend/payment-service"
    },
    {
      "name": "auth-service",
      "repo": "org/auth-service",
      "gitlab_namespace": "org/backend/auth-service"
    }
  ]
}
```

---

## Scanner → Orchestrator (streaming)

Per-agent status events fired as each agent completes, not as a final batch. Used to drive real-time dashboard updates via WebSocket.

Event types: `agent_started`, `hit_found`, `no_hit`. The `data` field is only present on `hit_found`.

```json
// agent_started
{
  "event": "agent_started",
  "service": "auth-service",
  "timestamp": "2026-05-15T14:32:01Z"
}

// hit_found
{
  "event": "hit_found",
  "service": "auth-service",
  "timestamp": "2026-05-15T14:32:04Z",
  "data": {
    "file_path": "src/clients/downstream.py",
    "matching_lines": [
      { "line_number": 42, "content": "response = requests.get(url)" }
    ],
    "confidence": 0.94,
    "explanation": "requests.get() called with no timeout inside an async handler — matches the cascade failure pattern."
  }
}

// no_hit
{
  "event": "no_hit",
  "service": "inventory-service",
  "timestamp": "2026-05-15T14:32:06Z"
}
```

---

## Scanner → Fix Factory

A single wrapper object sent once all scanner agents are complete — not streamed. Dynatrace incident context sits at the top level; Fix Factory applies it to every hit rather than repeating it per entry.

**Timing note:** Fix Factory is gated on complete Scanner output. Dashboard updates are driven entirely by the streaming events to Orchestrator above — Fix Factory plays no role in real-time status.

```json
{
  "incident_context": {
    "incident_id": "DT-4821",
    "title": "Payment service cascade failure — no timeout on HTTP client",
    "duration_minutes": 47,
    "estimated_cost": "£23,000",
    "root_cause_summary": "HTTP client with no timeout caused thread pool exhaustion under load.",
    "trace_id": "abc123xyz789",
    "affected_services": ["payment-service", "auth-service", "order-service"]
  },
  "hits": [
    {
      "service": "auth-service",
      "repo": "org/auth-service",
      "gitlab_namespace": "org/backend/auth-service",
      "file_path": "src/clients/downstream.py",
      "matching_lines": [
        { "line_number": 42, "content": "response = requests.get(url)" }
      ],
      "confidence": 0.94,
      "per_service_history": [
        {
          "pattern_similarity": 0.88,
          "outcome": "merged",
          "reason": "Fix accepted — added 5s timeout, no incidents since.",
          "risk_adjustment": 1
        }
      ]
    }
  ]
}
```

---

## Fix Factory → Orchestrator

One result entry per hit. `mr_url` is null if self-correction failed to produce a passable fix after the maximum iterations.

```json
{
  "results": [
    {
      "service": "auth-service",
      "file_path": "src/clients/downstream.py",
      "mr_url": "https://gitlab.com/org/auth-service/merge_requests/89",
      "self_correction_passed": true,
      "correction_iterations": 2,
      "failure_reason": null
    },
    {
      "service": "order-service",
      "file_path": "src/http/client.go",
      "mr_url": null,
      "self_correction_passed": false,
      "correction_iterations": 3,
      "failure_reason": "Eval agent could not confirm fix prevents cascade under load — timeout value unclear from context."
    }
  ]
}
```
