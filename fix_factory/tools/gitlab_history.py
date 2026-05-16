import httpx

_GITLAB_BASE = "https://gitlab.com/api/v4"


def get_fix_precedents(gitlab_namespace: str, token: str) -> list[dict]:
    encoded = gitlab_namespace.replace("/", "%2F")
    try:
        r = httpx.get(
            f"{_GITLAB_BASE}/projects/{encoded}/merge_requests",
            params={"state": "merged", "per_page": 20, "search": "timeout"},
            headers={"PRIVATE-TOKEN": token},
            timeout=10,
        )
        r.raise_for_status()
        return [{"title": mr["title"], "description": mr.get("description", "")} for mr in r.json()]
    except Exception:
        return []
