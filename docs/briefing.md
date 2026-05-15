# Ripple — Complete Project Briefing

*Last updated: May 15 2026. Single source of truth for onboarding any AI or collaborator.*

---

## The One-Line Pitch

> Every other code review tool asks "did this pattern appear before?" Ripple asks "did this pattern cause an outage — and where else is it hiding right now?"

## Two-Sentence Summary

Ripple detects dangerous code patterns in incoming GitLab PRs by checking whether that pattern has ever caused a real production incident in Dynatrace. When it finds a match, it fans out across every service in your codebase simultaneously and opens targeted fix MRs for all of them, each one grounded in the exact incident that proved why the pattern is dangerous.

---

## The Problem

A developer introduces a dangerous timeout configuration in a PR. The same pattern exists in 6 other services, put there by 3 different developers over 18 months. Nobody knows. Eventually one of them causes a production incident.

Ripple catches the PR, sweeps every service simultaneously, and opens fix MRs before anything reaches production.

---

## Hackathon Context

- **Competition:** Google Cloud Rapid Agent Hackathon — https://rapid-agent.devpost.com
- **Deadline:** June 11 2026
- **Track:** Dynatrace (primary MCP). Prizes: 1st $5k, 2nd $3k, 3rd $2k.
- **Repo:** CypherGuy/Ripple
- **Build:** Solo (Kabir)
- **GCP credits:** $100 applied for via Google Form (submitted May 15 2026, 1-5 business day approval)

---

## Architecture

Four microservices on **Google Cloud Run**, communicating via **A2A (Agent-to-Agent)** protocol, orchestrated by **Google ADK** with **Gemini** as the model.

```
GitLab Webhook
      │
      ▼
┌─────────────┐
│ Orchestrator │  ← receives webhook, coordinates everything,
│             │    streams status to dashboard via WebSocket
└──────┬──────┘
       │ A2A
       ▼
┌─────────────────┐
│  Intelligence   │  ← queries Dynatrace MCP, extracts semantic
│    Service      │    risk pattern, scores risk level
└──────┬──────────┘
       │ A2A (fan-out)
       ▼
┌─────────────────┐
│    Scanner      │  ← spawns one agent per service in parallel,
│    Service      │    each hunts the pattern in its service,
│                 │    streams status events back to Orchestrator
└──────┬──────────┘
       │ A2A
       ▼
┌─────────────────┐
│   Fix Factory   │  ← generates contextual fixes, runs
│                 │    self-correction loop, opens MRs via
└─────────────────┘    GitLab MCP, stores outcomes in MongoDB
```

---

## Three MCPs

| MCP | Track | Role |
|---|---|---|
| **Dynatrace** | Primary — enter this track | Incident history, pattern extraction, service maps |
| **GitLab** | Secondary | Codebase read/write, MR creation, commit history |
| **MongoDB** | Tertiary | Ripple's own institutional memory — scars, wins, patterns from past scans |

---

## What Each Service Does

**Orchestrator**
- Receives GitLab webhook on PR open/update
- Calls Intelligence via A2A, then coordinates Scanner and Fix Factory
- Streams per-agent status events to the Next.js dashboard via WebSocket

**Intelligence**
- Queries Dynatrace MCP for incident history matching the PR's code patterns
- Extracts a semantic (not syntactic) risk pattern in natural language
- Scores risk level
- Checks MongoDB for previous Ripple scans of this pattern
- Returns pattern + risk score + Dynatrace incident context to Orchestrator

**Scanner**
- Receives the natural language pattern + list of services to scan
- Spawns one agent per service/module in parallel (ParallelAgent in ADK)
- Each agent searches its assigned service for the pattern using Gemini
- Streams `agent_started` / `hit_found` / `no_hit` events to Orchestrator as they happen
- Sends all hits to Fix Factory as a single wrapper object

**Fix Factory**
- Receives hits from Scanner (incident context + file paths + matching lines)
- For each hit, spawns a fix agent with full context: Dynatrace incident traces + GitLab fix history + MongoDB scars/wins
- Evaluation agent checks whether the fix would have prevented the Dynatrace incident
- If evaluation fails, fix agent iterates (self-correction loop)
- On pass: opens fix MR via GitLab MCP with incident context in the description
- Stores outcome metadata in MongoDB

---

## A2A Message Contracts

*Full detail in `docs/a2a-contracts.md`. Summary:*

**Orchestrator → Intelligence:** PR diff + GitLab metadata

**Intelligence → Orchestrator:** Natural language pattern + risk score + Dynatrace incident context

**Orchestrator → Scanner:** Natural language pattern + list of services to scan

**Scanner → Orchestrator (streaming):** Per-agent status events as each completes — `agent_started`, `hit_found`, `no_hit`

**Scanner → Fix Factory:**
```
{
  incident_context: <Dynatrace incident context>,
  hits: [
    { service, file_path, matching_lines },
    ...
  ]
}
```

**Fix Factory → Orchestrator:** Fix MR URLs + self-correction pass/fail per hit

---

## MongoDB Institutional Memory

Ripple stores its own learning in MongoDB Atlas. Scanner agents are briefed with per-service history before they run.

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

Vector search finds similar past cases when scoring new PRs.

---

## Key Decisions

Full rationale in `docs/decisions.md`. Summaries:

- **D01** — Enter Dynatrace track. Dynatrace provides live production observability data no other MCP provides. Core insight is "what's broken in production" (Dynatrace) + "what code caused it" (GitLab).
- **D02** — GitLab as secondary MCP. GitLab alone risks judges thinking "GitLab Duo already ships this."
- **D03** — MongoDB as tertiary MCP for institutional memory. Three MCPs simultaneously is unprecedented in this hackathon.
- **D04** — Drop cross-language detection as the wow moment. Too niche (only useful during migrations).
- **D05** — Fix Factory generates real code fixes, not just warnings. Context (Dynatrace traces + GitLab fix history) is what separates it from Copilot suggestions. Self-correction loop ensures quality.
- **D06** — Four microservices via A2A, not a monolith. Architecturally impressive; ADK grand prize winner (SalesShortcut) used 5 microservices + A2A + 34 agents.
- **D07** — Autonomous action (real fix MRs), not just analysis. Agents DO something Claude can't — open MRs across 20 services simultaneously.
- **D08** — Pre-merge prevention, not incident response. Dynatrace Davis AI already does incident response. Pre-merge uses Dynatrace in a way Dynatrace itself doesn't.
- **D09** — Next.js dashboard as the hosted URL. Real-time WebSocket updates from each agent make the architecture tangible.
- **D10** — Semantic pattern detection, not syntactic. Gemini + Dynatrace trace context enables understanding of what actually broke, not just what the code looks like.

---

## Competitive Position

Every competitor lacks two things simultaneously — production observability data AND autonomous action. Ripple has both.

| Feature | ARGUS | Greptile | Semgrep | Ripple |
|---|---|---|---|---|
| Production incident data | ❌ | ❌ | ❌ | ✅ |
| Codebase-wide sweep | ❌ | ✅ | ✅ | ✅ |
| Autonomous fix MR creation | ❌ | ❌ | ❌ | ✅ |
| Self-learning over time | ✅ | ❌ | ❌ | ✅ (MongoDB) |

Closest competitor is **ARGUS** (argus.reviews) — AI code review with institutional memory. ARGUS knows what broke before (from git). Ripple knows what breaking *cost* (from Dynatrace) and fixes it across every service automatically. Full analysis in `docs/competitor-analysis.md`.

---

## The Demo Arc (3 minutes)

1. **0:00–0:20** — Dynatrace dashboard. Real incident. 47-minute outage. Here's the trace.
2. **0:20–0:40** — Developer submits a PR. Ripple fires. Same pattern detected.
3. **0:40–1:30** — Real-time dashboard. 20 agents fan out. Services lighting up green/red.
4. **1:30–2:00** — "Found in 7 services. Three different developers. The same pattern that caused the outage."
5. **2:00–2:30** — Fix MRs appear in GitLab, each with incident context embedded in the description.
6. **2:30–3:00** — "If Ripple had existed 3 weeks ago, the outage wouldn't have happened."

---

## Tech Stack

- **Orchestration:** Google ADK (Python)
- **Model:** Gemini (via Vertex AI)
- **Deployment:** Cloud Run (four services)
- **Communication:** A2A protocol between services
- **Frontend:** Next.js — real-time dashboard via WebSocket
- **Primary MCP:** Dynatrace
- **Secondary MCP:** GitLab
- **Tertiary MCP:** MongoDB Atlas

---

## Current State

Planning complete. No code written yet. Build order:

1. Orchestrator service scaffold (ADK + Cloud Run)
2. Dynatrace MCP integration test
3. GitLab MCP integration test
4. Intelligence service (pattern extraction from Dynatrace)
5. Scanner service (parallel fan-out)
6. Fix Factory (fix gen + self-correction loop)
7. MongoDB memory store
8. Next.js dashboard
9. A2A wiring between services
10. Demo environment setup
