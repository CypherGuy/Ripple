---
name: project-ripple
description: Ripple — hackathon project for Google Cloud Rapid Agent Hackathon (June 11 2026 deadline). Multi-agent code review system using Dynatrace + GitLab + MongoDB MCPs.
metadata:
  node_type: memory
  type: project
  originSessionId: 986e7177-6cc7-4abe-bb90-aff0881562f4
---

Ripple is a multi-agent ADK system entering the **Dynatrace track** of the Google Cloud Rapid Agent Hackathon (deadline: June 11 2026, ~27 days from May 15 2026).

**Why:** The competition is at https://rapid-agent.devpost.com. $60k in prizes split across 6 partner tracks. Dynatrace track: 1st $5k, 2nd $3k, 3rd $2k.

**What it does:** Detects risky code patterns in incoming GitLab PRs (grounded in real Dynatrace production incident history), fans out across the entire codebase with one agent per service in parallel, generates context-informed fix MRs for all affected services, and stores its own learnings in MongoDB Atlas.

**Repo:** /Users/kabirghai/ghq/github.com/CypherGuy/Ripple

**Architecture:** 4 microservices (Orchestrator, Intelligence, Scanner, Fix Factory) communicating via A2A on Cloud Run, orchestrated by Google ADK with Gemini.

**Three MCPs:** Dynatrace (primary — incident history), GitLab (secondary — codebase read/write + MR creation), MongoDB (tertiary — Ripple's own institutional memory: scars/wins/patterns).

**Key competitors:** ARGUS (argus.reviews), GitMem (gitmem.ai). Full analysis at Ripple/docs/competitor-analysis.md.

**Why:** Building this to try to win the hackathon. User is optimising for winning, not portfolio. Solo build.

**How to apply:** Need to apply for $100 GCP credits via https://forms.gle/xfv9vQzfRfNCCVbG7. Apply early (1-5 business day approval).
