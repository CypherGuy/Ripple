import os
import httpx
from fastapi import APIRouter

router = APIRouter()

_GITLAB_BASE = "https://gitlab.com/api/v4"


def close_all_ripple_mrs(namespaces: list[str], token: str) -> dict:
    headers = {"PRIVATE-TOKEN": token}
    closed = 0
    errors = 0

    for ns in namespaces:
        encoded = ns.replace("/", "%2F")
        try:
            r = httpx.get(
                f"{_GITLAB_BASE}/projects/{encoded}/merge_requests",
                params={"state": "opened", "per_page": 100},
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
            for mr in r.json():
                if not mr.get("source_branch", "").startswith("ripple/"):
                    continue
                try:
                    httpx.put(
                        f"{_GITLAB_BASE}/projects/{encoded}/merge_requests/{mr['iid']}",
                        json={"state_event": "close"},
                        headers=headers,
                        timeout=10,
                    ).raise_for_status()
                    closed += 1
                except Exception:
                    errors += 1
        except Exception:
            errors += 1

    return {"closed": closed, "errors": errors}


@router.post("/admin/close-mrs")
async def close_mrs():
    from orchestrator.pipeline import get_service_list
    token = os.environ.get("GITLAB_TOKEN", "")
    namespaces = [s["gitlab_namespace"] for s in get_service_list()]
    result = close_all_ripple_mrs(namespaces, token)
    return result
