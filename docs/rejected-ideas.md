---
name: rejected-hackathon-ideas
description: "All hackathon ideas considered and rejected during Ripple planning (May 15 2026), with rejection reasons. Reference before suggesting new ideas."
metadata:
  node_type: memory
  type: project
  originSessionId: 986e7177-6cc7-4abe-bb90-aff0881562f4
---

Ideas considered for the Google Cloud Rapid Agent Hackathon before landing on Ripple. All rejected.

## DevOps / GitLab Track Rejections

**GitFlow AI — Autonomous Engineering Manager**
Triage incoming issues, assign to developers, break epics into sub-tasks, monitor CI/CD, generate standups, write release notes.
Rejected: GitLab Duo already does all of this natively. Judges who built Duo would see through it immediately.

**Pipeline Doctor**
Detects CI/CD failures, reads logs via GitLab MCP, traces failure to a specific commit, opens fix MR.
Rejected: Same problem — Dynatrace Davis AI and GitLab Duo both do root cause analysis. "Another SRE tool."

**OSS Onboarding Guide**
Point at any public GitLab repo. Agent reads codebase, issues, contribution guides, builds a personalised onboarding plan for new contributors.
Rejected: Not impressive enough. Niche audience (OSS contributors). Hard to demo compellingly.

**Compliance Auditor**
Read entire codebase via GitLab MCP, generate GDPR/SOC2/HIPAA compliance audit report in 2 minutes.
Rejected: "Doesn't sit right." Legal/compliance domain requires domain expertise to evaluate. Boring demo. Niche audience.

**IP Guardian**
Scan repos for accidentally committed secrets, GPL-licensed code in commercial projects, copy-pasted code that could be an infringement risk.
Rejected: "Doesn't sit right." Similar to compliance — niche, dry, hard to demo excitingly.

**Autonomous Incident Response (full SRE loop)**
Detect incident via Dynatrace, read offending commit via GitLab, create fix MR, generate post-mortem. Full autonomous incident → fix → postmortem pipeline.
Rejected: Dynatrace Davis AI already does incident response and root cause analysis. Judges who built Davis AI would immediately think "we ship this." Accepted a narrower version (pre-merge prevention) as Ripple instead.

**Code Prophecy — initial version (analysis only)**
Read incoming PR via GitLab MCP, query Dynatrace incident history, output a risk score and warning.
Not outright rejected but had two problems: (1) pure analysis — agents don't DO anything, why not just ask Claude? (2) doesn't feel like 20+ agents, feels like one agent doing one task. Fixed by adding autonomous action + codebase fan-out to become Ripple.

**Technical Debt Invoice**
Read entire GitLab codebase + full Dynatrace incident history, calculate the dollar cost of each piece of technical debt line by line.
Not outright rejected but felt weaker than Code Prophecy direction. Reactive analysis rather than active prevention.

**Codebase Archaeologist**
Answer "why was this decision made?" from git history, issues, MR discussions, wiki. Institutional memory for understanding legacy code.
Rejected: Not impressive enough. Greptile does deep codebase understanding already. Not multi-agent enough.

**Ghost Contributor**
Describe a feature in plain English. Agent reads codebase via GitLab MCP, writes implementation, opens complete MR with tests and docs.
Rejected: "AI writes code" is extremely crowded (Devin, SWE-agent, GitHub Copilot workspace). Not novel. Demo risks showing broken code.

---

## MongoDB Track Rejections

**Sentinel — Competitive Intelligence Engine**
Monitor competitors across web, social, job boards, patents, news. Store in MongoDB with vector embeddings + time series. Predict competitor product launches from weak signals.
Rejected: "Why would a user use this over getting Claude to do the same thing?" Pure analysis tool — no autonomous action. Existing products (Crayon, Klue) prove the market exists but don't create differentiation.

**Personal Ops Agent (Second Brain)**
Store tasks, goals, notes, journal in MongoDB with vector embeddings. Agent surfaces relevant past context, spots patterns, helps plan and take action.
Rejected: "Doesn't sit right." Too similar to Notion AI, Mem.ai. Not multi-agent enough. Slow demo.

**Live Investigation Board**
Type any question. Visual detective corkboard builds itself in real time. Research agents store findings in MongoDB, connection agents use vector search to find non-obvious links, verdict card appears.
Rejected: "Doesn't sit right." Interesting visually but output is just an answer — no action taken in real systems.

**Skill Gap Agent**
Define career goals. Agent stores current skills and learning materials in MongoDB, identifies gaps via vector search, creates personalised roadmap, quizzes you, tracks progress.
Rejected: "Doesn't sit right." Education AI is crowded. Not large-scale enough (doesn't feel like 20+ agents).

**Full Lifecycle Job Application Agent**
Like SalesShortcut (grand prize winner) but for job seekers. Discovery → company research → fit scoring → CV tailoring → cover letter → interview prep → offer evaluation.
Rejected: User already has career-ops (a cloned tool that does most of this). Would be reinventing something they already have access to.

---

## Wow Moment Rejections (ideas about the hook, not the full product)

**Cross-language semantic detection**
"The agent finds the same risky pattern in a Go service even though it was written by a different team in a different language 8 months later."
Rejected: Only useful during or after a language migration. Most teams aren't migrating languages. Too niche to land with general judges.

**Institutional memory as the core wow ("introduced 4 times by 4 developers")**
"This pattern has been introduced, fixed, and reintroduced 4 times over 2 years."
Rejected: ARGUS (argus.reviews) already does exactly this. Not novel enough.

---

## What This Means for Future Ideas

A viable idea must pass all of:

1. Does the partner MCP already do this natively? (killer if yes)
2. Does it already exist as a product? (must search first)
3. Do the agents DO something in real systems, or just analyse? (analysis alone fails)
4. Is the wow moment universally applicable, not just in niche scenarios?
5. Does it naturally justify 20+ agents via parallelism, not padding?
