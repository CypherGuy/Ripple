# Ripple — A2A Message Contracts

Agreed during planning session (May 15 2026). These are the data shapes passed between services via A2A.

---

## Orchestrator → Intelligence

The PR diff and GitLab metadata for the incoming PR.

---

## Intelligence → Orchestrator

- **Pattern** — natural language description of the semantic risk behaviour (e.g. "Synchronous HTTP call inside an async handler with no timeout, which caused a cascade failure in the payments service.")
- **Risk score**
- **Dynatrace incident context** — the incident(s) that proved this pattern is dangerous

---

## Orchestrator → Scanner

- **Pattern** — the natural language description from Intelligence
- **Service list** — the list of services/modules to scan

---

## Scanner → Orchestrator (streaming)

Per-agent status events fired as each agent completes, not as a final batch. Used to drive real-time dashboard updates via WebSocket.

Event types:
- `agent_started` — service X is being scanned
- `hit_found` — pattern located in service X
- `no_hit` — service X is clean

---

## Scanner → Fix Factory

A single wrapper object:

```
{
  incident_context: <Dynatrace incident context>,
  hits: [
    {
      service: <service name>,
      file_path: <path>,
      matching_lines: <the specific lines that match the pattern>
    },
    ...
  ]
}
```

Dynatrace incident context sits at the top level once — Fix Factory applies it to every fix it generates rather than repeating it per hit.

---

## Fix Factory → Orchestrator

- **MR URLs** — one per hit, as each fix MR is opened
- **Self-correction outcome** — pass or fail for each fix (whether the evaluation agent determined the fix would have prevented the Dynatrace incident)
