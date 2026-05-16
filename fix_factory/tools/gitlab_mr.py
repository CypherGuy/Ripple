import httpx
import base64
from datetime import datetime, timezone

_GITLAB_BASE = "https://gitlab.com/api/v4"


def create_mr(
    gitlab_namespace: str,
    token: str,
    file_path: str,
    patch: str,
    incident_context: dict,
) -> str | None:
    encoded = gitlab_namespace.replace("/", "%2F")
    headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
    incident_id = incident_context.get("incident_id", "unknown")
    branch = f"ripple/fix-{incident_id.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    try:
        # Get default branch
        proj = httpx.get(f"{_GITLAB_BASE}/projects/{encoded}", headers=headers, timeout=10)
        proj.raise_for_status()
        default_branch = proj.json().get("default_branch", "main")

        # Create branch
        httpx.post(f"{_GITLAB_BASE}/projects/{encoded}/repository/branches",
                   json={"branch": branch, "ref": default_branch},
                   headers=headers, timeout=10).raise_for_status()

        # Get current file content
        path_enc = file_path.replace("/", "%2F")
        file_r = httpx.get(f"{_GITLAB_BASE}/projects/{encoded}/repository/files/{path_enc}",
                           params={"ref": default_branch}, headers=headers, timeout=10)
        file_r.raise_for_status()
        current_content = base64.b64decode(file_r.json()["content"]).decode()

        # Apply patch (simple line replacement from unified diff)
        new_content = _apply_patch(current_content, patch)

        # Commit
        httpx.put(f"{_GITLAB_BASE}/projects/{encoded}/repository/files/{path_enc}",
                  json={"branch": branch, "content": new_content,
                        "commit_message": f"fix: add timeout to prevent {incident_id} pattern"},
                  headers=headers, timeout=10).raise_for_status()

        # Open MR
        duration = incident_context.get("duration_minutes", "?")
        cost = incident_context.get("estimated_cost", "unknown")
        mr_r = httpx.post(f"{_GITLAB_BASE}/projects/{encoded}/merge_requests",
                          json={
                              "source_branch": branch,
                              "target_branch": default_branch,
                              "title": f"fix: prevent {incident_id} pattern in {file_path}",
                              "description": (
                                  f"**Automated fix by Ripple**\n\n"
                                  f"Incident: {incident_id} — {duration} min outage, {cost}\n\n"
                                  f"This fix prevents the pattern that caused the incident above."
                              ),
                          },
                          headers=headers, timeout=10)
        mr_r.raise_for_status()
        return mr_r.json().get("web_url")
    except Exception:
        return None


def _apply_patch(content: str, patch: str) -> str:
    lines = content.splitlines(keepends=True)
    for line in patch.splitlines():
        if line.startswith("-    ") or line.startswith("-  "):
            old = line[1:].rstrip("\n")
            for i, l in enumerate(lines):
                if l.rstrip("\n") == old:
                    lines[i] = ""
                    break
        elif line.startswith("+    ") or line.startswith("+  "):
            new = line[1:]
            for i, l in enumerate(lines):
                if l == "":
                    lines[i] = new if new.endswith("\n") else new + "\n"
                    break
    return "".join(l for l in lines if l != "")
