#!/usr/bin/env python3
"""
Backup demo trigger — creates a fresh MR without any prep.

Uses a timestamped branch so it never conflicts with existing MRs.
Run this if open_demo_mr.py prepare has already been done but something
went wrong and you need to re-fire the Ripple webhook fast.

Usage:
    python3 scripts/backup_trigger.py
"""

import json
import os
import subprocess
import sys
import time
from dotenv import load_dotenv

load_dotenv()

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
if not GITLAB_TOKEN:
    print("ERROR: GITLAB_TOKEN not set")
    sys.exit(1)

PROJECT_ID = 82256532  # cypherguy-group/pulsecheck/ssl-monitor
BASE_URL = "https://gitlab.com/api/v4"
HEADERS = ["PRIVATE-TOKEN: " + GITLAB_TOKEN, "Content-Type: application/json"]

BRANCH_CONTENT = '''\
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


def main():
    branch = f"feature/ssl-expiry-{int(time.time())}"
    print(f"Branch: {branch}\n")

    print("1. Creating branch...")
    result = curl("POST", f"/projects/{PROJECT_ID}/repository/branches", {
        "branch": branch,
        "ref": "main",
    })
    if not result.get("name"):
        print(f"   ERROR: {result}")
        sys.exit(1)
    print("   ✓")

    print("2. Adding bad endpoint...")
    result = curl("PUT", f"/projects/{PROJECT_ID}/repository/files/main.py", {
        "branch": branch,
        "content": BRANCH_CONTENT,
        "commit_message": "feat: add SSL certificate expiry check endpoint",
    })
    if not result.get("file_path"):
        print(f"   ERROR: {result}")
        sys.exit(1)
    print("   ✓")

    print("3. Opening MR...")
    result = curl("POST", f"/projects/{PROJECT_ID}/merge_requests", {
        "source_branch": branch,
        "target_branch": "main",
        "title": "feat: add SSL certificate expiry check endpoint",
        "description": "Adds /check/expiry to query SSL certificate expiry dates.",
    })
    url = result.get("web_url")
    if not url:
        print(f"   ERROR: {result}")
        sys.exit(1)
    print(f"   ✓ {url}")
    print("\n→ Ripple is firing. Switch to the dashboard.")


if __name__ == "__main__":
    main()
