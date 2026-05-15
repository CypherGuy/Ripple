# Ripple — Project Context for Claude Code

## What This Is

Ripple is a multi-agent AI system built for the **Google Cloud Rapid Agent Hackathon** (deadline: June 11 2026). It enters the **Dynatrace track** with GitLab and MongoDB as secondary MCPs.

URL: https://rapid-agent.devpost.com

Ripple detects risky code patterns in incoming GitLab PRs, fans out across the entire codebase to find every instance of that pattern, and autonomously opens fix MRs for all affected services — all grounded in real Dynatrace production incident history.

## The One-Line Pitch

> Every other code review tool asks "did this pattern appear before?" Ripple asks "did this pattern cause an outage — and where else is it hiding right now?"

## The Problem

A developer introduces a dangerous timeout configuration in a PR. The same pattern exists in 6 other services, put there by 3 different developers over 18 months. Nobody knows. Eventually one of them causes a production incident.

Ripple catches the PR, sweeps every service simultaneously, and opens fix MRs before anything reaches production.

## Architecture

Four microservices communicating via **A2A (Agent-to-Agent)** protocol, each deployed on **Cloud Run**, orchestrated by **Google ADK** with **Gemini** as the model.

```
GitLab Webhook
      │
      ▼
┌─────────────┐
│ Orchestrator │  ← receives webhook, coordinates everything
└──────┬──────┘
       │ A2A
       ▼
┌─────────────────┐
│  Intelligence   │  ← queries Dynatrace MCP, extracts risk pattern,
│    Service      │    validates against incident history
└──────┬──────────┘
       │ A2A (fan-out)
       ▼
┌─────────────────┐
│    Scanner      │  ← spawns one agent per service in parallel
│    Service      │    each agent hunts the pattern in its service
└──────┬──────────┘
       │ A2A
       ▼
┌─────────────────┐
│   Fix Factory   │  ← generates contextual fixes (informed by Dynatrace
│                 │    incident data + GitLab fix history), runs
│                 │    self-correction loop, opens MRs, stores
└─────────────────┘    outcomes in MongoDB
```

## Three MCPs

| MCP           | Track                      | Role                                                                      |
| ------------- | -------------------------- | ------------------------------------------------------------------------- |
| **Dynatrace** | Primary (enter this track) | Incident history, pattern extraction, service maps, real failure replay   |
| **GitLab**    | Secondary                  | Codebase read/write, MR creation, commit history, fix precedent           |
| **MongoDB**   | Tertiary                   | Ripple's own institutional memory — scars, wins, patterns from past scans |

## What Each Agent Does

**Orchestrator service:**

- Receives GitLab webhook on PR open/update
- Calls Intelligence service via A2A
- Coordinates the full pipeline
- Exposes WebSocket endpoint for real-time dashboard updates

**Intelligence service:**

- Queries Dynatrace MCP for incident history matching the PR's code patterns
- Extracts the specific risk pattern (semantic, not syntactic)
- Scores risk level with production cost quantification ("47min outage, £23k")
- Checks MongoDB for previous Ripple scans of this pattern (has it flagged this before? Was the fix accepted?)
- Returns pattern + risk score + incident context to Orchestrator

**Scanner service:**

- Receives pattern from Orchestrator
- Reads codebase structure via GitLab MCP
- Spawns one agent per service/module in parallel (ParallelAgent in ADK)
- Each agent searches its assigned service for the pattern
- Returns all hits with file paths and confidence scores

**Fix Factory:**

- Receives all hits from Scanner
- For each hit, spawns a fix agent with full context:
  - The specific Dynatrace incident traces (what exactly broke)
  - How the team fixed this pattern before (GitLab MR history)
  - What Ripple learned from previous fix MRs (MongoDB scars/wins)
- Fix agent generates a targeted fix
- Evaluation agent checks whether fix would have prevented the Dynatrace incident
- If evaluation fails, fix agent iterates (self-correction loop)
- On pass: opens fix MR via GitLab MCP
- Stores outcome metadata in MongoDB (pending — will update to scar/win once developer reacts)

## MongoDB Institutional Memory

Ripple stores its own learning in MongoDB Atlas:

```
Scar: {
  pattern: "...",
  service: "payment-service",
  outcome: "rejected",
  reason: "timeout is intentional for external API",
  risk_adjustment: -2
}

Win: {
  pattern: "...",
  service: "auth-service",
  outcome: "merged",
  no_incidents_since: true,
  confidence_boost: +1
}
```

Vector search finds similar past cases when scoring new PRs. Scanner agents are briefed with per-service history before they run.

## The Demo Arc (3 minutes)

1. **0:00–0:20** — Dynatrace dashboard. Real incident. 47-minute outage. Here's the trace.
2. **0:20–0:40** — Developer submits a PR. Ripple fires. Same pattern detected.
3. **0:40–1:30** — Real-time dashboard. 20 agents fan out. Services lighting up green/red.
4. **1:30–2:00** — "Found in 7 services. Three different developers. The same pattern that caused the outage."
5. **2:00–2:30** — Fix MRs appear in GitLab, each with incident context embedded in description.
6. **2:30–3:00** — "If Ripple had existed 3 weeks ago, the outage wouldn't have happened."

## Hackathon Requirements Checklist

- [ ] Built with Google Cloud Agent Builder / ADK ✅ (ADK orchestration)
- [ ] Uses Gemini as the model ✅
- [ ] Integrates Dynatrace MCP meaningfully ✅ (primary data source)
- [ ] Hosted project URL ← web dashboard on Cloud Run
- [ ] Public GitHub repo with open source licence ← this repo
- [ ] ~3 minute demo video ← record after build
- [ ] Select Dynatrace track on Devpost

## Key Competitors

See `docs/competitor-analysis.md` for full breakdown.

- **ARGUS** (argus.reviews) — closest conceptual overlap. Ripple's moat: production data, codebase-wide sweep, autonomous action.
- **GitMem** (gitmem.ai) — different layer (developer agent memory). Ripple borrows the scar/win/pattern concept for its own institutional memory.
- **Dynatrace's own GitHub Copilot agent** — handles CVEs/security, not behavioural incident patterns. Different scope.

## Tech Stack

- **Orchestration:** Google ADK (Python)
- **Model:** Gemini (via Vertex AI)
- **Deployment:** Cloud Run (four services)
- **Communication:** A2A protocol between services
- **Primary MCP:** Dynatrace
- **Secondary MCP:** GitLab
- **Tertiary MCP:** MongoDB Atlas (institutional memory)
- **Frontend:** Next.js (real-time dashboard via WebSocket)
- **Streaming:** SSE/WebSocket for live agent status updates

## What "Not Started Yet" Means

The competitor analysis and architecture are designed. Code not yet written. Start with:

1. Orchestrator service scaffold (ADK + Cloud Run)
2. Dynatrace MCP integration test
3. GitLab MCP integration test
4. Intelligence service (pattern extraction from Dynatrace)
5. Scanner service (parallel fan-out)
6. Fix Factory (fix gen + self-correction)
7. MongoDB memory store
8. Next.js dashboard
9. A2A wiring between services
10. Demo environment setup
