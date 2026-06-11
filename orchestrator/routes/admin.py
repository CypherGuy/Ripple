import os
import httpx
from fastapi import APIRouter, Header, HTTPException

router = APIRouter()

_GITLAB_BASE = "https://gitlab.com/api/v4"


def _should_close(branch: str) -> bool:
    return branch.startswith("ripple/") or branch.startswith("feature/ssl-expiry-")


def close_all_ripple_mrs(namespaces: list[str], token: str) -> dict:
    headers = {"PRIVATE-TOKEN": token}
    closed = 0
    errors = 0

    # Collect unique group prefixes to sweep at group level (catches backup_trigger branches)
    groups: set[str] = set()
    for ns in namespaces:
        parts = ns.split("/")
        if len(parts) >= 2:
            groups.add("/".join(parts[:-1]))

    for group in groups:
        encoded = group.replace("/", "%2F")
        try:
            r = httpx.get(
                f"{_GITLAB_BASE}/groups/{encoded}/merge_requests",
                params={"state": "opened", "per_page": 100},
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            for mr in r.json():
                if not _should_close(mr.get("source_branch", "")):
                    continue
                project_id = mr.get("project_id")
                iid = mr.get("iid")
                try:
                    httpx.put(
                        f"{_GITLAB_BASE}/projects/{project_id}/merge_requests/{iid}",
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


@router.post("/admin/cancel")
async def cancel_pipeline_route(x_admin_secret: str | None = Header(default=None)):
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    from orchestrator.pipeline import cancel_pipeline
    return cancel_pipeline()


@router.post("/admin/close-mrs")
async def close_mrs(x_admin_secret: str | None = Header(default=None)):
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    from orchestrator.pipeline import get_service_list
    token = os.environ.get("GITLAB_TOKEN", "")
    namespaces = [s["gitlab_namespace"] for s in get_service_list()]
    result = close_all_ripple_mrs(namespaces, token)
    return result
