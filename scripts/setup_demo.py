"""
Demo environment setup for Ripple.

Creates 20 GitLab repos under the configured namespace:
  - 7 repos with the timeout-less HTTP pattern (light up red in demo)
  - 13 repos with timeout-guarded HTTP calls (light up green)

Usage:
    python scripts/setup_demo.py --create          # create all repos
    python scripts/setup_demo.py --verify          # verify setup is complete
    python scripts/setup_demo.py --create --verify # create then verify
"""
import argparse
import os
import sys
import base64
import httpx
from pathlib import Path

# Ensure repo root is on sys.path so intelligence/scanner packages are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

GITLAB_BASE = "https://gitlab.com/api/v4"
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
GITLAB_NAMESPACE = os.environ.get("DEMO_NAMESPACE", "cypherguy-group/ripple-demo")

SERVICES_WITH_HITS = {
    "payment-service":      ("src/http/client.py",         'response = requests.get(f"{BASE_URL}/charge", headers=auth_headers)'),
    "auth-service":         ("src/clients/downstream.py",  "response = requests.get(url)"),
    "order-service":        ("src/http/external.py",       "result = httpx.get(endpoint)"),
    "notification-service": ("src/senders/email.py",       "r = requests.post(url, data=payload)"),
    "inventory-service":    ("src/sync/upstream.py",       "data = requests.get(url, headers=headers)"),
    "billing-service":      ("src/integrations/stripe.py", "resp = http_client.get(path)"),
    "reporting-service":    ("src/fetch/warehouse.py",     "rows = requests.get(url, params=filters)"),
}

SERVICES_CLEAN = [
    "gateway-service", "user-service", "search-service", "analytics-service",
    "recommendation-service", "config-service", "audit-service", "session-service",
    "webhook-service", "cache-service", "scheduler-service", "export-service", "admin-service",
]

ALL_SERVICES = list(SERVICES_WITH_HITS.keys()) + SERVICES_CLEAN

HEADERS = {"PRIVATE-TOKEN": GITLAB_TOKEN, "Content-Type": "application/json"}


def _hit_file_content(file_path: str, bad_line: str) -> str:
    return f"""import requests
import httpx

BASE_URL = "https://api.internal.example.com"

def fetch_data(url, headers=None, endpoint=None, payload=None, path=None, params=None):
    # WARNING: no timeout configured
    {bad_line}
    return response.json() if hasattr(response, 'json') else response

"""


def _clean_file_content(file_path: str) -> str:
    return f"""import requests
import httpx

BASE_URL = "https://api.internal.example.com"
DEFAULT_TIMEOUT = 5  # seconds — prevents thread pool exhaustion

def fetch_data(url, headers=None):
    response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    return response.json()

"""


def _get_or_create_group(namespace: str) -> int | None:
    """Return group ID for the namespace, creating subgroups as needed."""
    parts = namespace.split("/")
    if len(parts) == 1:
        r = httpx.get(f"{GITLAB_BASE}/groups/{parts[0]}", headers=HEADERS, timeout=10)
        return r.json().get("id") if r.status_code == 200 else None

    parent_path = parts[0]
    child_name = parts[1]
    parent_r = httpx.get(f"{GITLAB_BASE}/groups/{parent_path}", headers=HEADERS, timeout=10)
    if parent_r.status_code != 200:
        print(f"  error: parent group '{parent_path}' not found")
        return None
    parent_id = parent_r.json()["id"]

    full_path = f"{parent_path}/{child_name}"
    check_r = httpx.get(f"{GITLAB_BASE}/groups/{full_path.replace('/', '%2F')}", headers=HEADERS, timeout=10)
    if check_r.status_code == 200:
        return check_r.json()["id"]

    create_r = httpx.post(f"{GITLAB_BASE}/groups", headers=HEADERS, timeout=10, json={
        "name": child_name, "path": child_name, "parent_id": parent_id, "visibility": "private",
    })
    if create_r.status_code in (200, 201):
        print(f"  created group: {full_path}")
        return create_r.json()["id"]
    print(f"  error creating group: {create_r.text[:100]}")
    return None


def _create_repo(namespace: str, service: str, namespace_id: int) -> bool:
    encoded = f"{namespace}/{service}".replace("/", "%2F")
    check = httpx.get(f"{GITLAB_BASE}/projects/{encoded}", headers=HEADERS, timeout=10)
    if check.status_code == 200:
        return True

    r = httpx.post(f"{GITLAB_BASE}/projects", headers=HEADERS, timeout=15, json={
        "name": service, "path": service, "namespace_id": namespace_id,
        "visibility": "private", "initialize_with_readme": True,
    })
    return r.status_code in (200, 201)


def _push_file(namespace: str, service: str, file_path: str, content: str) -> bool:
    encoded_proj = f"{namespace}/{service}".replace("/", "%2F")
    encoded_file = file_path.replace("/", "%2F")
    url = f"{GITLAB_BASE}/projects/{encoded_proj}/repository/files/{encoded_file}"

    check = httpx.get(url, params={"ref": "main"}, headers=HEADERS, timeout=10)
    method = httpx.put if check.status_code == 200 else httpx.post
    r = method(url, headers=HEADERS, timeout=15, json={
        "branch": "main",
        "content": content,
        "commit_message": f"chore: add {file_path}",
    })
    return r.status_code in (200, 201)


def create(namespace: str) -> bool:
    print(f"Setting up demo environment under: {namespace}")
    group_id = _get_or_create_group(namespace)
    if not group_id:
        print("error: could not get or create namespace group")
        return False

    success = True
    for service in ALL_SERVICES:
        print(f"  repo: {service} ", end="", flush=True)
        if not _create_repo(namespace, service, group_id):
            print("FAILED (create)")
            success = False
            continue

        if service in SERVICES_WITH_HITS:
            file_path, bad_line = SERVICES_WITH_HITS[service]
            content = _hit_file_content(file_path, bad_line)
        else:
            file_path = "src/http/client.py"
            content = _clean_file_content(file_path)

        if _push_file(namespace, service, file_path, content):
            status = "HIT" if service in SERVICES_WITH_HITS else "clean"
            print(f"✓ ({status})")
        else:
            print("FAILED (push)")
            success = False

    return success


def verify(namespace: str) -> bool:
    print(f"Verifying demo environment: {namespace}")
    errors = []

    for service, (file_path, bad_line) in SERVICES_WITH_HITS.items():
        encoded_proj = f"{namespace}/{service}".replace("/", "%2F")
        encoded_file = file_path.replace("/", "%2F")
        r = httpx.get(
            f"{GITLAB_BASE}/projects/{encoded_proj}/repository/files/{encoded_file}",
            params={"ref": "main"}, headers=HEADERS, timeout=10,
        )
        if r.status_code != 200:
            errors.append(f"missing file: {service}/{file_path}")
            continue
        content = base64.b64decode(r.json()["content"]).decode()
        if bad_line not in content:
            errors.append(f"pattern not found in {service}/{file_path}")

    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGODB_URI"])["ripple"]
    scars = db.scars.count_documents({})
    wins = db.wins.count_documents({})
    if scars < 2 or wins < 2:
        errors.append(f"MongoDB seed incomplete: scars={scars} wins={wins} (need 2 each)")

    from intelligence.tools.dynatrace import _call_tool
    dt_result = _call_tool(os.environ["DT_ENVIRONMENT"], os.environ["DT_PLATFORM_TOKEN"],
                           "query-problems", {"history": "60d"})
    content_items = dt_result.get("result", {}).get("content", [])
    has_incident = any("DT-4821" in item.get("text", "") for item in content_items
                       if isinstance(item, dict))

    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        return False

    dt_status = "accessible" if has_incident else "no incidents yet (expected for fresh trial)"
    print(f"All 20 repos verified · 7 hits confirmed · MongoDB seeded (scars={scars}, wins={wins}) · Dynatrace: {dt_status}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Ripple demo environment setup")
    parser.add_argument("--create", action="store_true", help="Create demo repos")
    parser.add_argument("--verify", action="store_true", help="Verify setup is complete")
    parser.add_argument("--namespace", default=GITLAB_NAMESPACE,
                        help=f"GitLab namespace (default: {GITLAB_NAMESPACE})")
    args = parser.parse_args()

    if not args.create and not args.verify:
        parser.print_help()
        sys.exit(1)

    ok = True
    if args.create:
        ok = create(args.namespace) and ok
    if args.verify:
        ok = verify(args.namespace) and ok

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
