import os
import httpx

_GITLAB_BASE = "https://gitlab.com/api/v4"


def read_service_files(
    gitlab_namespace: str,
    token: str,
    _files_override: dict | None = None,
) -> dict[str, str]:
    if _files_override is not None:
        return _files_override

    headers = {"PRIVATE-TOKEN": token}
    encoded = gitlab_namespace.replace("/", "%2F")

    try:
        tree_r = httpx.get(
            f"{_GITLAB_BASE}/projects/{encoded}/repository/tree",
            params={"recursive": "true", "per_page": 100},
            headers=headers,
            timeout=10,
        )
        tree_r.raise_for_status()
        files = {}
        for item in tree_r.json():
            if item.get("type") == "blob" and item["path"].endswith(".py"):
                path_enc = item["path"].replace("/", "%2F")
                content_r = httpx.get(
                    f"{_GITLAB_BASE}/projects/{encoded}/repository/files/{path_enc}/raw",
                    params={"ref": "main"},
                    headers=headers,
                    timeout=10,
                )
                if content_r.status_code == 200:
                    files[item["path"]] = content_r.text
        return files
    except Exception:
        return {}
