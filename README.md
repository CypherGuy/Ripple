# Ripple

> Every other code review tool asks "did this pattern appear before?" Ripple asks "did this pattern cause an outage — and where else is it hiding right now?"

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com) — Dynatrace track.

---

## What it does

Ripple detects dangerous code patterns in incoming GitLab PRs by checking whether that pattern has ever caused a real production incident in Dynatrace. When it finds a match, it fans out across every service in your codebase simultaneously and opens targeted fix MRs — each grounded in the exact incident that proved why the pattern is dangerous.

---

## What's built

### Phase 1 — Environment & MCP Validation

`scripts/validate_mcps.py` confirms live connectivity to both Dynatrace and GitLab before any service code runs.

```bash
python scripts/validate_mcps.py
# {"dynatrace": "ok", "gitlab": "ok"}
```

Dynatrace is reached via the MCP gateway using a Platform Token. GitLab is reached via the REST API. Either failure is captured independently and reported without crashing.

### Phase 2 — Orchestrator Service

FastAPI service on port 8000 with three endpoints:

- `GET /health` — liveness check
- `POST /webhook` — receives GitLab MR webhook events, validates `pr_id` via Pydantic (returns 422 if missing), returns HTTP 202
- `WebSocket /ws` — accepts dashboard connections; `broadcast_event()` in `ws_manager.py` fans JSON events to all connected clients, dropping stale connections silently

### Phase 3 — Intelligence Service

FastAPI service on port 8001. `POST /analyze` accepts a PR diff and returns a semantic risk pattern with a 1–10 score.

The two Dynatrace MCP tools used (actual tool names discovered by querying `tools/list` against the live gateway):

| What we call | Dynatrace MCP tool |
|---|---|
| Fetch incident history | `query-problems` |
| Fetch span traces | `execute-dql` |
| Look up services | `get-entity-id` |

`fetch_incident_history()` calls `query-problems` with a 60-day lookback. `extract_pattern()` passes the incidents and PR diff to Gemini, which returns a natural-language description of the behavioural risk and a score. If the matched incident had a duration ≥ 47 minutes, the score is floored at 9.

All tests mock the Dynatrace MCP — no live calls in the test suite.

---

## Setup

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
GITLAB_TOKEN=glpat-xxx
MONGODB_URI=mongodb+srv://...
GOOGLE_CLOUD_PROJECT=your-project-id
```

```bash
python scripts/validate_mcps.py   # confirm connectivity
pytest                             # 15 tests, all green
```

---

## License

MIT — see [LICENSE](LICENSE).
