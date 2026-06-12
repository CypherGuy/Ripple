import logging
import httpx
import base64
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_GITLAB_BASE = "https://gitlab.com/api/v4"

# Single source of truth in shared/formatting.py; aliased here so existing
# imports/tests of fix_factory.tools.gitlab_mr._format_cost keep working.
from shared.formatting import format_cost as _format_cost


def create_mr(
    gitlab_namespace: str,
    token: str,
    file_path: str,
    old_line: str,
    new_line: str,
    incident_context: dict,
    evaluated_on: str = "incident_context",
    extra_patches: list | None = None,
    base_ref: str | None = None,
) -> str | None:
    encoded = gitlab_namespace.replace("/", "%2F")
    headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
    incident_id = incident_context.get("incident_id", "unknown")
    branch = f"ripple/fix-{incident_id.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    try:
        # Get default branch
        proj = httpx.get(f"{_GITLAB_BASE}/projects/{encoded}",
                         headers=headers, timeout=30)
        proj.raise_for_status()
        default_branch = proj.json().get("default_branch", "main")

        # Shift-left: when the run was triggered by an MR, branch off and target the
        # MR's branch (base_ref) so the incoming change is fixed before it merges.
        # Otherwise fall back to the default branch (codebase-wide sweep behaviour).
        base = base_ref or default_branch

        # Create branch
        httpx.post(f"{_GITLAB_BASE}/projects/{encoded}/repository/branches",
                   json={"branch": branch, "ref": base},
                   headers=headers, timeout=30).raise_for_status()

        # Get current file content
        path_enc = file_path.replace("/", "%2F")
        file_r = httpx.get(f"{_GITLAB_BASE}/projects/{encoded}/repository/files/{path_enc}",
                           params={"ref": base}, headers=headers, timeout=30)
        file_r.raise_for_status()
        current_content = base64.b64decode(file_r.json()["content"]).decode()

        new_content = _apply_patch(current_content, old_line, new_line)
        for xold, xnew in (extra_patches or []):
            new_content = _apply_patch(new_content, xold, xnew)

        # Commit
        httpx.put(f"{_GITLAB_BASE}/projects/{encoded}/repository/files/{path_enc}",
                  json={"branch": branch, "content": new_content,
                        "commit_message": f"fix: add timeout to prevent {incident_id} pattern"},
                  headers=headers, timeout=30).raise_for_status()

        # Open MR
        duration = incident_context.get("duration_minutes", "?")
        cost = _format_cost(incident_context.get("estimated_cost", "unknown"))
        if evaluated_on == "technical_merit":
            verification_note = (
                "_Verified on technical merit - no incident root cause was available "
                "from Dynatrace at evaluation time. Fix is structurally sound._"
            )
        else:
            verification_note = (
                f"_Verified against incident root cause. "
                f"Incident: {incident_id} - {duration} min outage, {cost}._"
            )
        mr_r = httpx.post(f"{_GITLAB_BASE}/projects/{encoded}/merge_requests",
                          json={
                              "source_branch": branch,
                              "target_branch": base,
                              "title": f"fix: prevent {incident_id} pattern in {file_path}",
                              "description": (
                                  f"**Automated fix by Ripple**\n\n"
                                  f"Incident: {incident_id} - {duration} min outage, {cost}\n\n"
                                  f"This fix prevents the timeout-less HTTP call pattern "
                                  f"that caused the incident above.\n\n"
                                  f"{verification_note}"
                              ),
        },
            headers=headers, timeout=30)
        mr_r.raise_for_status()
        return mr_r.json().get("web_url")
    except Exception as e:
        logger.exception("create_mr failed for %s: %s", gitlab_namespace, e)
        return None


def _apply_patch(content: str, old_line: str, new_line: str) -> str:
    if not old_line:
        return content

    # Exact match: replace all occurrences with identical whitespace.
    if old_line in content:
        content = content.replace(old_line, new_line)

    # Strip-based pass: catches any remaining occurrences with different indentation.
    # Skips lines already patched by the replace above (stripped content would differ).
    lines = content.splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n").strip()
        if stripped == old_line.strip() and stripped != new_line.strip():
            indent = len(line) - len(line.lstrip())
            lines[i] = " " * indent + new_line.strip() + "\n"
            changed = True
    return "".join(lines) if changed else content
