# Ripple — Decision Log

Decisions made during initial planning session (May 15 2026). Each entry records what was decided, what was considered, and why.

---

## D01 — Enter Dynatrace track, not MongoDB or GitLab

**Decision:** Primary MCP is Dynatrace. Enter the Dynatrace track on Devpost.

**Considered:**
- MongoDB (rejected multiple times — user not interested in the domain ideas it enabled)
- GitLab alone (rejected — too close to what GitLab Duo already does natively)
- Dynatrace + GitLab together

**Why Dynatrace:**
User had not worked with Dynatrace before and found it genuinely interesting. Dynatrace provides live production observability data that no other MCP in the hackathon provides. The combination of "what's broken in production" (Dynatrace) + "what code caused it" (GitLab) is the core insight that makes Ripple novel.

---

## D02 — GitLab as secondary MCP, not primary

**Decision:** Use GitLab MCP for codebase read/write and MR creation, but enter the Dynatrace track.

**Why:**
GitLab alone keeps hitting the "GitLab Duo already does this" problem. GitLab Duo has automated triage, CI/CD suggestions, custom agents. Building on top of GitLab in the GitLab track risks judges thinking "we already ship this." Dynatrace as primary avoids that entirely and the GitLab integration is additive.

---

## D03 — Add MongoDB as tertiary MCP for institutional memory

**Decision:** Wire MongoDB Atlas via MCP for Ripple's own self-learning (scars, wins, patterns).

**Why:**
Identified gap vs ARGUS (learns from reviewer reactions) and GitMem (accumulates scars/wins over sessions). MongoDB with vector search is the natural storage layer for Ripple's own institutional memory. Using three MCPs simultaneously is unprecedented in this hackathon and impresses judges from all three partner companies. The MongoDB integration is substantive (not just a database) — it drives the briefing of scanner agents and the risk score adjustments.

---

## D04 — Drop cross-language detection as the wow moment

**Decision:** Do not lead with "finds the same pattern across different languages."

**Considered:** Using semantic pattern detection across Python, Go, TypeScript etc. as a wow moment.

**Why rejected:**
Only useful during or after a language migration. Most teams aren't migrating languages most of the time. Too narrow a use case to impress general judges. Replaced by: "this pattern has been introduced, fixed, and reintroduced 4 times by 4 different developers over 2 years" — universally applicable.

---

## D05 — Drop code generation as the "fix" output, then reintroduce it

**Decision:** Fix Factory generates code fixes informed by Dynatrace incident traces + GitLab fix history, not generic Gemini suggestions.

**Considered:** Removing code generation entirely (just create GitLab issues + block MR + create Dynatrace alert).

**Why reintroduced:**
User explicitly wanted the system to write an implementation fix, not just warn. The differentiation from "just Gemini writes code" comes from the context: the fix is informed by actual incident traces (what specifically broke) and historical precedent (how the team fixed this exact pattern before). That context is what separates it from Copilot/Cursor suggestions.

**Self-correction loop added:** A separate evaluation agent checks whether the generated fix would have prevented the specific Dynatrace incident. If not, the fix agent iterates. This makes fix quality reliable and is architecturally impressive.

---

## D06 — Four microservices via A2A, not a monolithic ADK agent

**Decision:** Orchestrator, Intelligence, Scanner, Fix Factory as separate Cloud Run services communicating via A2A.

**Why:**
The ADK hackathon grand prize winner (SalesShortcut) used this architecture: 5 microservices, A2A communication, 34 agents. Judges responded strongly to this. A monolithic ADK agent is simpler to build but less impressive architecturally. A2A also provides real isolation — Scanner can scale independently from Fix Factory, services can fail independently.

---

## D07 — Autonomous action, not just analysis

**Decision:** Ripple opens real fix MRs, doesn't just comment or warn.

**Considered:** Comment on PR with warning + links to similar incidents. Simpler to build, less risky to get wrong.

**Why autonomous action:**
The core "why not just ask Claude" answer requires the agents to DO something Claude can't. Claude can analyse code. Claude cannot open MRs across 20 services simultaneously. The action at scale is the product. Every competitor in the space warns. None of them act.

---

## D08 — Abandon "autonomous SRE / incident response" as the core concept

**Decision:** Ripple is a pre-merge prevention system, not an incident response system.

**Considered at length:** Detecting live production incidents → diagnosing → creating fix MRs → generating post-mortem. Full autonomous SRE loop.

**Why rejected:**
Dynatrace's Davis AI already does root cause analysis and incident response. Judges who built Davis AI would see through it. "Another SRE tool" was the user's exact objection. Pre-merge prevention uses Dynatrace in a way Dynatrace itself doesn't — as a historical pattern database for code review, not a live incident response tool.

---

## D09 — Real-time dashboard as the hosted URL

**Decision:** Build a Next.js dashboard showing live agent status as the "hosted project" required by hackathon rules.

**Why:**
Hackathon requires a URL to a hosted project. A pure webhook service with no UI would comply but would be impossible to demo and judge effectively. The dashboard provides the visual of 20+ agents working simultaneously — the "pixel agents" energy that makes the architecture tangible. Real-time WebSocket updates from each agent are the demo.

---

## D10 — Semantic pattern detection, not syntactic

**Decision:** Ripple extracts the *behavioural* risk (e.g., "synchronous timeout in an async context that caused a cascade") not a code snippet to grep for.

**Why:**
Syntactic matching is what Semgrep does. Any team can write a Semgrep rule. The value is detecting the same behavioural antipattern even when the implementation looks different — a 5-second hardcoded timeout in Python and a `config.get("timeout", 5000)` in TypeScript are the same risk. Gemini + Dynatrace trace context enables semantic understanding of what actually broke.
