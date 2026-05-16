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

| What we call           | Dynatrace MCP tool |
| ---------------------- | ------------------ |
| Fetch incident history | `query-problems`   |
| Fetch span traces      | `execute-dql`      |
| Look up services       | `get-entity-id`    |

`fetch_incident_history()` calls `query-problems` with a 60-day lookback. `extract_pattern()` passes the incidents and PR diff to Gemini, which returns a natural-language description of the behavioural risk and a score. If the matched incident had a duration ≥ 47 minutes, the score is floored at 9.

All tests mock the Dynatrace MCP — no live calls in the test suite.

### Phase 4 — MongoDB Institutional Memory

Ripple learns from past scans. Two MongoDB collections in the `ripple` database store the outcomes of previous fix MR decisions, with the aim of modifying the risk score based on previous experiences:

- **`scars`** — patterns that were flagged but the fix MR was rejected (e.g. timeout intentionally absent). Each scar carries a `risk_adjustment` that lowers the score for that service.
- **`wins`** — patterns where the fix MR was accepted and no incidents followed. Each win carries a `confidence_boost` that raises the score.

`find_similar_wins()` and `find_similar_scars()` in `intelligence/tools/mongodb.py` query these collections by pattern string. The results are applied to the risk score from Phase 3 before returning from `/analyze`, and appear in `previous_scans` in the response.

```bash
python scripts/seed_mongodb.py
# Inserted scar: gateway-service
# Inserted scar: config-service
# Inserted win: auth-service
# Inserted win: session-service
```

### Phase 5 — Scanner Service

FastAPI service on port 8002. `POST /scan` receives the pattern from Intelligence and a list of services to check, then scans all of them in parallel using `asyncio.gather()` — one Gemini call per service.

`read_service_files()` in `scanner/tools/gitlab.py` fetches Python source files from a GitLab repo via the REST API. `scan_service()` passes those files to Gemini with the natural-language pattern and gets back a list of hits with file path, matching lines, and a confidence score. Services with no matching files skip the Gemini call entirely.

The response includes the incident context forwarded from Intelligence and a flat hits array tagged with the service name.

### Phase 6 — Scanner Streaming Events

Phase 5's scanner was silent — it scanned everything then returned one big result. Phase 6 makes it talk as it goes.

`scanner/streaming.py` adds `emit_event()`, which fires a POST to the Orchestrator for each service the moment it finishes — before the full fan-out is done. Three event types match the contract in `docs/a2a-contracts.md`: `agent_started` fires when a service begins, `hit_found` fires with the matched lines if a pattern is found, `no_hit` fires otherwise.

The Orchestrator receives these at `POST /internal/broadcast` and immediately fans them out to all connected WebSocket clients via `broadcast_event()`. This is what will drive the real-time dashboard in Phase 9.

### Phase 7 — Fix Factory: Fix Generation

FastAPI service on port 8003. `POST /fix` accepts a single hit from the Scanner and returns a unified diff patch plus a one-sentence explanation.

Three sources of context are gathered before Gemini writes the fix: Dynatrace span traces for the incident (via `execute-dql`), closed GitLab MRs in the target repo that mention "timeout" (prior fix precedents), and per-service history from MongoDB. All three are passed to Gemini in a single prompt, which is what separates this from a generic Copilot suggestion — the fix is grounded in what specifically broke and how the team has fixed it before.

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
