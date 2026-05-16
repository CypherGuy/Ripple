import httpx

_MCP_URL_TEMPLATE = "https://{env}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"


def _call_tool(env: str, token: str, tool: str, arguments: dict) -> dict:
    r = httpx.post(
        _MCP_URL_TEMPLATE.format(env=env),
        json={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool, "arguments": arguments}, "id": 1},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _parse_records(content: list) -> list[dict]:
    """Extract the JSON records array from the MCP text response."""
    import json as _json
    for item in reversed(content):
        text = item.get("text", "") if isinstance(item, dict) else ""
        if "Query result records:" in text:
            raw = text.split("Query result records:")[-1].strip()
            try:
                records = _json.loads(raw)
                return records if isinstance(records, list) else []
            except Exception:
                pass
    return []


def fetch_incident_history(env: str, token: str, diff: str) -> list[dict]:
    data = _call_tool(env, token, "query-problems", {"history": "60d"})
    content = data.get("result", {}).get("content", [])
    return _parse_records(content)


def execute_dql(env: str, token: str, dql_query: str) -> list[dict]:
    data = _call_tool(env, token, "execute-dql", {"dqlQueryString": dql_query})
    content = data.get("result", {}).get("content", [])
    return _parse_records(content)


def get_entity_id(env: str, token: str, entity_type: str, name_filter: str) -> list[dict]:
    data = _call_tool(env, token, "get-entity-id", {"entityType": entity_type, "entityNameFilter": name_filter})
    content = data.get("result", {}).get("content", [])
    return [c for c in content if isinstance(c, dict)]
