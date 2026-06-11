import re
import json
import httpx

_MCP_URL = "https://{env}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
_INCIDENT_ID_RE = re.compile(r"^[A-Z]+-\d+$")

# Cache traces per incident_id - all 12 parallel fix requests use the same incident,
# so only the first call hits Dynatrace; the rest return instantly.
_trace_cache: dict[str, list[dict]] = {}


def validate_incident_id(incident_id: str) -> None:
    if not _INCIDENT_ID_RE.match(incident_id):
        raise ValueError(f"Invalid incident_id: {incident_id!r}")


def _parse_traces(r: httpx.Response) -> list[dict]:
    content = r.json().get("result", {}).get("content", [])
    for item in reversed(content):
        text = item.get("text", "") if isinstance(item, dict) else ""
        if "Query result records:" in text:
            try:
                return json.loads(text.split("Query result records:")[-1].strip()) or []
            except Exception:
                pass
    return []


async def get_incident_traces(env: str, token: str, incident_id: str) -> list[dict]:
    """Async - non-blocking Dynatrace DQL query with per-incident caching."""
    validate_incident_id(incident_id)

    if incident_id in _trace_cache:
        return _trace_cache[incident_id]

    dql = f'fetch bizevents, from:now()-30d | filter event.type == "ripple.incident" and incident_id == "{incident_id}" | limit 1'
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                _MCP_URL.format(env=env),
                json={"jsonrpc": "2.0", "method": "tools/call",
                      "params": {"name": "execute-dql", "arguments": {"dqlQueryString": dql}}, "id": 1},
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                timeout=15,
            )
            r.raise_for_status()
            traces = _parse_traces(r)
    except Exception:
        traces = []

    _trace_cache[incident_id] = traces
    return traces
