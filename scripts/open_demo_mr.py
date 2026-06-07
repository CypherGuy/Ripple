#!/usr/bin/env python3
"""
Open a fresh demo trigger MR on ssl-monitor.

What this does:
  1. Reverts ssl-monitor/main.py on main to the clean state (no check_expiry)
  2. Deletes the old feature branch if it exists
  3. Creates a fresh feature/ssl-expiry-demo branch with the bad httpx.get() endpoint
  4. Opens a non-draft MR — this fires the GitLab webhook and triggers Ripple

Usage:
  python3 scripts/open_demo_mr.py
"""

import os
import sys
import json
import subprocess
from dotenv import load_dotenv

load_dotenv()

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
if not GITLAB_TOKEN:
    print("ERROR: GITLAB_TOKEN not set")
    sys.exit(1)

PROJECT_ID = 82256532  # cypherguy-group/pulsecheck/ssl-monitor
BRANCH = "feature/ssl-expiry-demo"
BASE_URL = "https://gitlab.com/api/v4"
HEADERS = ["PRIVATE-TOKEN: " + GITLAB_TOKEN, "Content-Type: application/json"]

CLEAN_MAIN = '''\
import httpx
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck SSL Monitor")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ssl-monitor"}


@app.get("/check")
def check_ssl(target: str):
    """Verify SSL certificate by making an HTTPS request."""
    response = httpx.get(target)
    return {
        "url": target,
        "status_code": response.status_code,
        "ssl_valid": True,
    }


@app.get("/check/chain")
def check_chain(target: str):
    """Check full SSL certificate chain."""
    response = httpx.get(target, follow_redirects=True)
    return {
        "url": target,
        "final_url": str(response.url),
        "ssl_valid": True,
        "status_code": response.status_code,
    }
'''

BRANCH_CONTENT = CLEAN_MAIN + '''

@app.get("/check/expiry")
def check_expiry(target: str):
    """Check SSL certificate expiry date."""
    response = httpx.get(target)
    return {"url": target, "expires": response.headers.get("expires")}
'''


def curl(method, path, data=None):
    cmd = ["curl", "-s", "-X", method, f"{BASE_URL}{path}"]
    for h in HEADERS:
        cmd += ["-H", h]
    if data:
        cmd += ["-d", json.dumps(data)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print(f"[curl] timed out: {cmd}", flush=True)
        return {}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from curl response: {r.stdout!r}") from e


def close_open_mrs():
    """Close any open MRs for the demo branch so we can recreate it cleanly."""
    mrs = curl(
        "GET", f"/projects/{PROJECT_ID}/merge_requests?state=opened&source_branch={BRANCH.replace('/', '%2F')}")
    if isinstance(mrs, list):
        for mr in mrs:
            iid = mr.get("iid")
            if iid:
                curl(
                    "PUT", f"/projects/{PROJECT_ID}/merge_requests/{iid}", {"state_event": "close"})
                print(f"   ✓ Closed MR !{iid}")


def prepare():
    """Steps 1–4: reset state. Run this before recording."""
    print("=== Ripple Demo — Prepare ===\n")

    print("0. Closing any open demo MRs...")
    close_open_mrs()

    print("1. Reverting ssl-monitor/main.py to clean state...")
    result = curl("PUT", f"/projects/{PROJECT_ID}/repository/files/main.py", {
        "branch": "main",
        "content": CLEAN_MAIN,
        "commit_message": "chore: revert to pre-demo state"
    })
    if result.get("file_path"):
        print("   ✓ main.py reverted")
    else:
        print(
            f"   (already clean or minor error: {result.get('message', 'ok')})")

    print(f"2. Cleaning up old branch '{BRANCH}'...")
    del_result = curl(
        "DELETE", f"/projects/{PROJECT_ID}/repository/branches/{BRANCH.replace('/', '%2F')}")
    if del_result.get("message") == "Branch was deleted":
        print("   ✓ Old branch deleted")
    else:
        print("   (branch didn't exist, skipping)")

    print(f"3. Creating branch '{BRANCH}'...")
    branch_result = curl("POST", f"/projects/{PROJECT_ID}/repository/branches", {
        "branch": BRANCH,
        "ref": "main"
    })
    if branch_result.get("name"):
        print(f"   ✓ Branch created: {branch_result['name']}")
    else:
        print(f"   ERROR: {branch_result}")
        sys.exit(1)

    print("4. Adding check_expiry endpoint (the bad pattern)...")
    file_result = curl("PUT", f"/projects/{PROJECT_ID}/repository/files/main.py", {
        "branch": BRANCH,
        "content": BRANCH_CONTENT,
        "commit_message": "feat: add SSL certificate expiry check endpoint"
    })
    if file_result.get("file_path"):
        print("   ✓ Endpoint added")
    else:
        print(f"   ERROR: {file_result}")
        sys.exit(1)

    print("\n✓ Ready. Run 'python3 scripts/open_demo_mr.py fire' when you're recording.")


def fire():
    """Step 5 only: open the MR. Run this on camera."""
    print("=== Ripple Demo — Fire ===\n")
    print("Opening MR (fires the Ripple webhook)...")
    mr_result = curl("POST", f"/projects/{PROJECT_ID}/merge_requests", {
        "source_branch": BRANCH,
        "target_branch": "main",
        "title": "feat: add SSL certificate expiry check endpoint",
        "description": "Adds /check/expiry to query SSL certificate expiry dates."
    })
    mr_url = mr_result.get("web_url")
    if mr_url:
        print(f"✓ MR opened: {mr_url}")
        print("\n→ Switch to the Ripple dashboard — tiles go amber within a few seconds.")
    else:
        print(f"ERROR: {mr_result}")
        sys.exit(1)


def main():
    """Run both prepare and fire (original behaviour)."""
    prepare()
    print()
    fire()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "prepare":
        prepare()
    elif mode == "fire":
        fire()
    else:
        main()
