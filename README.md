# Ripple

> Every other code review tool asks "did this pattern appear before?" Ripple asks "did this pattern cause an outage — and where else is it hiding right now?"

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com) — Dynatrace track.

**Live dashboard:** https://ripple-dashboard-105645459605.europe-west2.run.app

---

## What it does

Ripple detects dangerous code patterns in incoming GitLab PRs by checking whether that pattern has ever caused a real production incident in Dynatrace. When it finds a match, it fans out across every service in your codebase simultaneously and opens targeted fix MRs — each grounded in the exact incident that proved why the pattern is dangerous.

The demo runs against **PulseCheck** — a real 12-service Python monitoring platform hosted on GitLab. The incident it's grounded in is **P-26051**: a 47-minute outage caused by `ssl-monitor` hanging on a slow certificate check with no HTTP timeout. Ripple finds that same pattern across all 12 services and opens fix MRs before anything reaches production.

---

## Architecture

Four FastAPI microservices on Google Cloud Run (London), coordinated via A2A protocol with Gemini as the model and Google ADK for agentic tool use.

```
GitLab Webhook
      │
      ▼
┌─────────────┐
│ Orchestrator │  FastAPI · asyncio · httpx
└──────┬──────┘
       │ A2A
       ▼
┌─────────────────┐
│  Intelligence   │  LlmAgent (Google ADK) + Dynatrace FunctionTool
│    Service      │  extracts semantic risk pattern from PR diff
└──────┬──────────┘
       │ A2A (fan-out)
       ▼
┌─────────────────┐
│    Scanner      │  asyncio.gather() — one Gemini call per service
│    Service      │  reads code via GitLab REST API
└──────┬──────────┘
       │ A2A
       ▼
┌─────────────────┐
│   Fix Factory   │  fix agent + eval agent per hit
│                 │  self-correction loop (up to 3 iterations)
└─────────────────┘  opens fix MRs via GitLab REST API
```

See [`architecture.html`](architecture.html) for the full interactive diagram.

---

## Three MCPs

| MCP               | Track     | Role                                                                                                                                                                                                                  |
| ----------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dynatrace**     | Primary   | Incident history via `query-problems`, span traces via `execute-dql`. The Intelligence LlmAgent calls this as a FunctionTool — it decides whether the diff looks dangerous enough to query, genuine agentic tool use. |
| **GitLab**        | Secondary | Codebase read (source files per service), MR creation, closed MR history for fix precedents. Used via REST API.                                                                                                       |
| **MongoDB Atlas** | Tertiary  | Institutional memory — scars (rejected fixes, risk −2) and wins (merged fixes, confidence +1). Vector search finds similar past cases on new PRs.                                                                     |

---

## Deployed services

| Service      | URL                                                        |
| ------------ | ---------------------------------------------------------- |
| Dashboard    | https://ripple-dashboard-105645459605.europe-west2.run.app |
| Orchestrator | https://ripple-orchestrator-mctjeick3a-nw.a.run.app        |
| Intelligence | https://ripple-intelligence-mctjeick3a-nw.a.run.app        |
| Scanner      | https://ripple-scanner-mctjeick3a-nw.a.run.app             |
| Fix Factory  | https://ripple-fix-factory-mctjeick3a-nw.a.run.app         |

All services run on Cloud Run `europe-west2`. Secrets managed via GCP Secret Manager.

---

## Running a demo scan

### One-click (dashboard)

Open the dashboard and click **Trigger Demo**. The pipeline fires with the P-26051 incident payload, scanning all 12 PulseCheck services in real time.

### curl

```bash
curl -X POST https://ripple-orchestrator-mctjeick3a-nw.a.run.app/webhook \
  -H "Content-Type: application/json" \
  -H "X-Gitlab-Token: $GITLAB_WEBHOOK_SECRET" \
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

### Risk threshold

Set `AUTO_FIX_THRESHOLD` (default `7`) on the orchestrator. Services with a risk score below threshold show **Approve / Skip** buttons on the dashboard instead of auto-fixing — keeping you in control.

---

## Local setup

```bash
git clone https://github.com/CypherGuy/Ripple.git
cd Ripple
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```
DT_ENVIRONMENT=your-env.apps.dynatrace.com
DT_PLATFORM_TOKEN=dt0s16.xxx
DT_OTEL_TOKEN=dt0s16.xxx
DT_EVENTS_TOKEN=dt0s16.xxx
GITLAB_TOKEN=glpat-xxx
MONGODB_URI=mongodb+srv://...
GEMINI_API_KEY=AIza...
DEMO_NAMESPACE=cypherguy-group/pulsecheck
INTERNAL_SECRET=generate-with-secrets.token_urlsafe-32
ADMIN_SECRET=generate-with-secrets.token_urlsafe-32
GITLAB_WEBHOOK_SECRET=generate-with-secrets.token_urlsafe-32
```

```bash
python scripts/validate_mcps.py   # confirm Dynatrace + GitLab connectivity
pytest                             # 117 tests, all green
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
# Deploy all services
python3 scripts/cloud_deploy.py

# Deploy a single service
python3 scripts/cloud_deploy.py orchestrator
```

Requires `gcloud` authenticated to project `ripple-496422`. Builds via Cloud Build, deploys to `europe-west2`. All secrets are pulled from Secret Manager at runtime — no credentials in the image.

---

## What's built

### Phase 1 — MCP validation

`scripts/validate_mcps.py` confirms live connectivity to Dynatrace and GitLab before any service runs.

### Phase 2 — Orchestrator

Webhook receiver (`POST /webhook` with `X-Gitlab-Token` signature check), pipeline coordinator, WebSocket broadcaster (`/ws`), rate-limited demo trigger (`POST /demo/trigger`, 60s cooldown), admin close-MRs endpoint, risk-threshold approval endpoint (`POST /internal/approve`).

### Phase 3 — Intelligence Service

`POST /analyze` — extracts a semantic risk pattern from the PR diff using a Google ADK `LlmAgent` with a Dynatrace `FunctionTool`. The agent decides whether to call Dynatrace based on how dangerous the diff looks. If it does, it gets real incident history (P-26051: 47 min, £23k). Risk score is floored at 9 for incidents ≥ 47 minutes.

### Phase 4 — MongoDB Institutional Memory

`ripple.scars` and `ripple.wins` collections store every scan outcome. Wins boost confidence; scars lower risk for services that intentionally skip patterns. `find_similar_wins()` / `find_similar_scars()` query by pattern similarity before scoring.

### Phase 5–6 — Scanner Service

`POST /scan` fans out across all 12 PulseCheck services with `asyncio.gather()`. Each service gets a Gemini call that reads its source files from GitLab and hunts the semantic pattern. Streaming events (`agent_started`, `hit_found`, `no_hit`) fire to the dashboard in real time via `/internal/broadcast` callbacks. One fix MR per service — highest-confidence hit when a service has multiple matches.

### Phase 7–8 — Fix Factory

`POST /fix` runs a self-correction loop (up to 3 iterations): fix agent generates a patch, eval agent checks whether it addresses the root cause, rationale feeds back if it fails. On pass, `create_mr()` opens a GitLab MR with the incident ID, duration, and cost embedded in the description. Service tiles show a **DT-grounded** badge when the eval used real Dynatrace incident data.

### Phase 9 — Next.js Dashboard

Real-time 12-tile grid. Five states per tile: **Idle** (grey) → **Scanning** (amber pulse) → **Hit** (red glow + View MR) / **Clean** (green) / **Approval** (indigo, Approve/Skip buttons). Incident panel shows P-26051 context across the top. Summary bar tracks scanned / hits / clean / MRs opened.

### Phase 10 — End-to-end A2A wiring

`X-Trace-Id` (uuid4) propagated through all downstream calls. Full pipeline: webhook → Intelligence → Scanner → Fix Factory → MR. 117 tests covering every service, route, and integration point.

### Phase 11 — PulseCheck target environment

12 real GitLab repos under `cypherguy-group/pulsecheck` with genuine Python monitoring code. `scripts/setup_pulsecheck.py` creates and populates them. Dynatrace problem P-26051 pushed via Events API and wired into the pipeline.

### Phase 12 — Security hardening & deployment

15 documented bugs fixed (see [`BUGS.md`](BUGS.md)). Hardening includes: DQL injection validation, SSRF allowlist on scanner callbacks, diff size cap (64 KB), `X-Internal-Secret` on internal routes, `X-Admin-Secret` on admin routes, service name allowlist on `/fix`, open-redirect fix on MR URLs, `GITLAB_WEBHOOK_SECRET` enforced on incoming webhooks.

---

## Security notes (services are live)

- Incoming webhooks validated via `X-Gitlab-Token` against `GITLAB_WEBHOOK_SECRET` in Secret Manager
- Internal broadcast endpoint requires `X-Internal-Secret`
- Admin close-MRs endpoint requires `X-Admin-Secret`
- Fix Factory rejects unknown service names (allowlist of 32 known services)
- Scanner callback URL validated against `ORCHESTRATOR_URL` allowlist (SSRF protection)
- Orchestrator runs at `--max-instances=1` so the in-memory rate limiter on `/demo/trigger` is effective

---

## About page

The dashboard's `/about` page has a full competitor analysis (ARGUS, GitMem, CodeRabbit, Semgrep, SonarQube), a feature comparison matrix, and architecture narrative for judges.

---

## License

MIT — see [LICENSE](LICENSE).
