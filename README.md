# Ripple

Ripple shift-lefts your incident history into your PR review: not static analysis, but real Dynatrace traces that tell you whether this pattern has caused an outage before.

**Live dashboard:** https://ripple-dashboard-105645459605.europe-west2.run.app  
**About & competitor analysis:** https://ripple-dashboard-105645459605.europe-west2.run.app/about

---

## The Problem

The same pattern that caused your last outage is being reintroduced by AI-assisted PRs right now.

A developer (or an AI coding agent) adds an HTTP call without a timeout. It passes code review. It merges. Six months later, a slow third-party endpoint causes your service to hang, the thread pool exhausts, and the cascade begins. That's P-26051: a 47-minute outage, £23,000 in estimated cost.

The same pattern existed in seven other services, introduced by three different developers over eighteen months. Nobody knew. Nobody connected the PR that opened it to the incident that proved it was dangerous.

Every other code review tool asks _"did this pattern appear before?"_ Ripple asks _"did this pattern cause an outage, and where else is it hiding right now?"_

---

## What Ripple Does

Ripple is a multi-agent AI system that intercepts GitLab PRs, checks them against real Dynatrace production incident history, fans out across every service in your codebase simultaneously, and autonomously opens fix MRs. Each MR cites the exact incident that proved why the pattern is dangerous.

One PR fires the pipeline. Twelve services are scanned in parallel. Fix MRs appear in GitLab within minutes for every service where the pattern is found, each citing the specific Dynatrace incident ID, duration, and estimated cost. The developer does not need to know the pattern was dangerous. Ripple already does.

---

## Demo Environment

The demo runs against **PulseCheck**, a real 12-service Python monitoring platform on GitLab. The incident is **P-26051**: a 47-minute outage caused by `ssl-monitor` hanging on a slow certificate check with no HTTP timeout. Ripple finds that same pattern across 8 of the 12 services and opens fix MRs before anything reaches production — the other 4 already have timeouts configured.

**Generalisation:** Ripple's architecture is pattern-agnostic. Timeouts were chosen because they caused the demo incident, not because they are the only pattern. The same pipeline works for any incident-grounded pattern: SQL queries missing indexes, race conditions in async handlers, missing retry logic on third-party calls. Any engineering team with a monitoring platform and a git-based workflow is a potential user. Eight services fixed in one pipeline run across a 12-service codebase; the same architecture scales to 200.

---

## Architecture

Four FastAPI microservices on Google Cloud Run (London), communicating via agent-to-agent HTTP calls. Each service is powered by a Google ADK `LlmAgent` with FunctionTools that the agent calls based on its own assessment of what information it needs.

```
GitLab Webhook / Trigger Demo
        │
        ▼
┌───────────────┐
│  Orchestrator  │  FastAPI · asyncio · httpx · WebSocket broadcaster
└───────┬───────┘
        │ A2A
        ▼
┌─────────────────┐
│  Intelligence   │  ADK LlmAgent + Dynatrace FunctionTool
│    Service      │  Agent decides whether to query Dynatrace based on diff severity
└───────┬─────────┘
        │ A2A (per-hit fan-out; fixes start before scanning finishes)
        ▼
┌─────────────────┐
│    Scanner      │  ADK LlmAgent + GitLab FunctionTool
│    Service      │  Agent decides which files to fetch per service
└───────┬─────────┘
        │ A2A
        ▼
┌─────────────────┐
│   Fix Factory   │  ADK LlmAgent + GitLab history FunctionTool (fix agent)
│                 │  ADK LlmAgent + Dynatrace trace FunctionTool (eval agent)
└─────────────────┘  Self-correction loop · opens MRs · writes MongoDB outcomes
```

The pipeline overlaps scanning and fixing: the moment a service reports a hit, Fix Factory starts on it while the remaining services are still scanning. The first MR can open before the last service finishes.

---

## Three MCPs

| MCP               | Track     | Role                                                                                                                                                                                                                                                                                                                                                                        |
| ----------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dynatrace**     | Primary   | Intelligence queries `query-problems` for incident history matching the PR diff. The ADK agent decides whether the diff warrants a query; it is not called automatically. The evaluator re-fetches real traces via `execute-dql` to validate each fix against the actual failure before opening an MR. Ripple's own Gemini calls are traced in Dynatrace via OpenTelemetry. |
| **GitLab**        | Secondary | Scanner fetches source files per service. Fix Factory pulls closed MR history for fix precedents. MRs are opened with incident context embedded in the description.                                                                                                                                                                                                         |
| **MongoDB Atlas** | Tertiary  | Institutional memory: every merged fix is a Win (confidence +1), every rejected fix is a Scar (risk −2). Subsequent scans query this history. Ripple gets smarter with every developer interaction.                                                                                                                                                                         |

---

## Google ADK Integration

All four services use Google ADK `LlmAgent` with `FunctionTool`:

- **Intelligence** - `LlmAgent` with Dynatrace `FunctionTool`. The agent receives the raw PR diff and decides whether to query Dynatrace for incident history. If the diff looks benign, it skips the call. If it looks dangerous, it fetches real incident traces and grounds its risk score in them.
- **Scanner** - `LlmAgent` with GitLab `FunctionTool`. The agent decides which files to fetch from each service's repository before searching for the pattern.
- **Fix Factory (fix agent)** - `LlmAgent` with GitLab history `FunctionTool`. The agent can pull how this team has fixed similar patterns before, generating a contextual patch rather than a generic one.
- **Fix Factory (eval agent)** - `LlmAgent` with Dynatrace trace `FunctionTool`. The agent validates the proposed fix against the actual incident traces, not just in theory, but against the specific failure that proved the pattern was dangerous.

---

## OpenTelemetry to Dynatrace

Ripple ships its own telemetry to the same Dynatrace environment it uses to observe your codebase.

Every pipeline run ships spans to `jfr54188.live.dynatrace.com` via the OTLP exporter:

- `ripple.intelligence.adk_run` - latency, whether Dynatrace was queried, response length
- `ripple.scanner.scan_service` - per service: files fetched, hits found, confidence
- `ripple.fix_factory.run_with_correction` - per service: iterations taken, evaluation pass/fail, `evaluated_on: incident_context`

The `evaluated_on: incident_context` attribute on the Fix Factory span proves the fix was validated against real Dynatrace incident data, not just technical correctness.

---

## Institutional Memory

MongoDB stores every scan outcome as a Scar or Win:

```
Win  → merged fix, no incidents since → confidence_boost: +1
Scar → rejected fix, pattern was intentional → risk_adjustment: -2
```

Every subsequent scan on the same codebase queries this history. Scars lower the risk score on patterns a team has deliberately chosen not to fix. Wins raise confidence on patterns they have already addressed. Ripple gets more accurate with each run on the same codebase.

Pattern matching uses **Atlas Vector Search** with Gemini `text-embedding-004` embeddings (768 dimensions, cosine similarity). Each scar and win is stored with a semantic vector so that "HTTP call without a configured timeout" and "missing timeout on HTTP request" match correctly, regardless of wording. Falls back to regex-based keyword matching if embedding generation fails.

When accumulated scars push a risk score below the configurable `AUTO_FIX_THRESHOLD`, Ripple switches from auto-fixing to requesting approval. The developer sees **Approve / Skip** buttons on the dashboard tile rather than an automatically opened MR - the decision stays with the engineer.

---

## The Dashboard

Real-time developer tool, not an ops screen.

Five tile states: **Idle, Scanning, Hit, Clean, Approval**. The moment Intelligence returns a risk score, it appears in the incident panel. The moment a service reports a hit, the scanner and fix factory run in parallel for that service. MRs appear tile-by-tile as they open in GitLab.

Each hit tile shows:

- **Incident: P-26051** - the specific incident that grounded this fix
- **eval 1/3** - which iteration the self-correction loop passed on
- **DT trace ↗** - direct link to the Dynatrace span for this fix
- **View MR ↗** - the actual GitLab MR

The Pipeline Trace section below the grid shows a live Gantt: Intelligence duration, scan phase per service, fix generation per service. The elapsed timer counts up during the run and freezes on completion.

---

## Deployed Services

| Service      | URL                                                        |
| ------------ | ---------------------------------------------------------- |
| Dashboard    | https://ripple-dashboard-105645459605.europe-west2.run.app |
| Orchestrator | https://ripple-orchestrator-mctjeick3a-nw.a.run.app        |
| Intelligence | https://ripple-intelligence-mctjeick3a-nw.a.run.app        |
| Scanner      | https://ripple-scanner-mctjeick3a-nw.a.run.app             |
| Fix Factory  | https://ripple-fix-factory-mctjeick3a-nw.a.run.app         |

All services run on Cloud Run `europe-west2`. Secrets are managed via GCP Secret Manager. `--min-instances=1` is set on all backend services to eliminate cold-start latency.

---

## Running the Demo

### One click

Open the dashboard and click **▶ Trigger Demo**. The pipeline fires with the P-26051 incident payload, scanning all 12 PulseCheck services in real time. No terminal required.

### Risk threshold

Set `AUTO_FIX_THRESHOLD` (default `7`) on the orchestrator. Services with a risk score below threshold show **Approve / Skip** buttons on the dashboard rather than auto-opening an MR.

### curl

```bash
curl -X POST https://ripple-orchestrator-mctjeick3a-nw.a.run.app/webhook \
  -H "Content-Type: application/json" \
  -H "X-Gitlab-Token: <your-webhook-secret>" \
  -d '{
    "pr_id": "demo-run",
    "repo": "cypherguy-group/pulsecheck/ssl-monitor",
    "diff": "@@ -12 +12 @@ response = httpx.get(target_url)",
    "incident_context": {
      "incident_id": "P-26051",
      "duration_minutes": 47,
      "estimated_cost": "£23,000",
      "root_cause_summary": "PulseCheck ssl-monitor hung on slow cert check"
    }
  }' | jq .
```

---

## Local Setup

```bash
git clone https://github.com/CypherGuy/Ripple.git
cd Ripple
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```
DT_ENVIRONMENT=your-env.apps.dynatrace.com
DT_PLATFORM_TOKEN=<dynatrace-platform-token>
DT_OTEL_TOKEN=<dynatrace-otel-token>         # needs openTelemetryTrace.ingest scope
DT_EVENTS_TOKEN=<dynatrace-events-token>
GITLAB_TOKEN=<gitlab-personal-access-token>
MONGODB_URI=<mongodb-atlas-connection-string>
GEMINI_API_KEY=<gemini-api-key>
DEMO_NAMESPACE=your-gitlab-group/your-project
INTERNAL_SECRET=<secrets.token_urlsafe(32)>
ADMIN_SECRET=<secrets.token_urlsafe(32)>
GITLAB_WEBHOOK_SECRET=<secrets.token_urlsafe(32)>
```

```bash
python scripts/validate_mcps.py
.venv/bin/python -m pytest
```

Run all four services:

```bash
uvicorn orchestrator.main:app --port 8000 &
uvicorn intelligence.main:app --port 8001 &
uvicorn scanner.main:app --port 8002 &
uvicorn fix_factory.main:app --port 8003 &
cd dashboard && npm install && npm run dev
```

---

## Deploy to Cloud Run

```bash
python3 scripts/cloud_deploy.py              # all services
python3 scripts/cloud_deploy.py orchestrator # single service
```

Builds via Cloud Build, deploys to `europe-west2`. All secrets are pulled from Secret Manager at runtime.

---

## Tech Stack

| Layer           | Technology                                                 |
| --------------- | ---------------------------------------------------------- |
| Agent framework | Google ADK (`LlmAgent`, `FunctionTool`, `Runner`)          |
| Model           | Gemini 3 Flash (via ADK)                                 |
| Observability   | OpenTelemetry to Dynatrace (`jfr54188.live.dynatrace.com`) |
| Primary MCP     | Dynatrace (`query-problems`, `execute-dql`)                |
| Secondary       | GitLab REST API                                            |
| Tertiary        | MongoDB Atlas (institutional memory)                       |
| Backend         | FastAPI · Python 3.13 · asyncio · httpx                    |
| Frontend        | Next.js 14 · Tailwind CSS · WebSocket                      |
| Infrastructure  | Google Cloud Run · Cloud Build · Secret Manager            |
| Tests           | pytest · 164 tests · TDD throughout                        |

---

## License

MIT - see [LICENSE](LICENSE).
