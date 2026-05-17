import re
import httpx

_MCP_URL = "https://{env}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
_INCIDENT_ID_RE = re.compile(r"^[A-Z]+-\d+$")


def validate_incident_id(incident_id: str) -> None:
    if not _INCIDENT_ID_RE.match(incident_id):
        raise ValueError(f"Invalid incident_id: {incident_id!r}")


def get_incident_traces(env: str, token: str, incident_id: str) -> list[dict]:
    validate_incident_id(incident_id)
    dql = f'fetch dt.davis.problems | filter display_id == "{incident_id}" | limit 1'
    r = httpx.post(
        _MCP_URL.format(env=env),
        json={"jsonrpc": "2.0", "method": "tools/call",
              "params": {"name": "execute-dql", "arguments": {"dqlQueryString": dql}}, "id": 1},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    content = r.json().get("result", {}).get("content", [])
    import json as _json
    for item in reversed(content):
        text = item.get("text", "") if isinstance(item, dict) else ""
        if "Query result records:" in text:
            try:
                return _json.loads(text.split("Query result records:")[-1].strip()) or []
            except Exception:
                pass
    return []
