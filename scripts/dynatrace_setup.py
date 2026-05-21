"""
PulseCheck + Dynatrace live integration helper.

Usage:
  python scripts/dynatrace_setup.py --step install
  python scripts/dynatrace_setup.py --step run
  python scripts/dynatrace_setup.py --step slow-server
  python scripts/dynatrace_setup.py --step trigger
  python scripts/dynatrace_setup.py --step fetch-problem
  python scripts/dynatrace_setup.py --step patch-ripple --problem-id <ID>
"""
from dotenv import load_dotenv
import argparse
import os
import sys
import time
import json
import socket
import subprocess
import threading
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

DT_ENV = os.environ.get("DT_ENVIRONMENT", "")
DT_TOKEN = os.environ.get("DT_PLATFORM_TOKEN", "")
DT_OTEL_TOKEN = os.environ.get("DT_OTEL_TOKEN", "")
DT_EVENTS_TOKEN = os.environ.get("DT_EVENTS_TOKEN", "")
# Dynatrace OTLP endpoint - uses live.dynatrace.com (not apps.dynatrace.com)
_tenant = DT_ENV.replace(".apps.dynatrace.com", "")
DT_OTEL_ENDPOINT = f"https://{_tenant}.live.dynatrace.com/api/v2/otlp/v1/traces"
SLOW_SERVER_PORT = 19999
LOCAL_DIR = Path("/tmp/pulsecheck")

# --- Service definitions (key HTTP calls that will hang) ---
SERVICES = {
    "http-monitor": {
        "port": 9021,
        "trigger_path": "/check?target=http://localhost:19999",
        "hang_lib": "requests",
    },
    "api-monitor": {
        "port": 9003,
        "trigger_path": "/check/stripe",  # calls status.stripe.com - swap URL via env
        "hang_lib": "requests",
    },
    "github-monitor": {
        "port": 9004,
        "trigger_path": "/status",
        "hang_lib": "requests",
    },
    "dns-checker": {
        "port": 9005,
        "trigger_path": "/resolve?domain=test.internal",
        "hang_lib": "requests",
    },
    "slack-notifier": {
        "port": 9007,
        "trigger_path": None,  # POST endpoint, triggered separately
        "hang_lib": "requests",
    },
}

SERVICE_CODE = {
    "http-monitor": textwrap.dedent("""\
        import requests
        from fastapi import FastAPI
        app = FastAPI(title="PulseCheck HTTP Monitor")

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "http-monitor"}

        @app.get("/check")
        def check(target: str):
            response = requests.get(target)
            return {"url": target, "status_code": response.status_code, "reachable": True}
    """),

    "api-monitor": textwrap.dedent("""\
        import os
        import requests
        from fastapi import FastAPI
        app = FastAPI(title="PulseCheck API Monitor")

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "api-monitor"}

        @app.get("/check/{api_name}")
        def check_api(api_name: str):
            urls = {
                "stripe": os.environ.get("MOCK_API_URL", "https://status.stripe.com/api/v2/status.json"),
            }
            url = urls.get(api_name, "https://status.stripe.com/api/v2/status.json")
            response = requests.get(url)
            return {"api": api_name, "status": response.json().get("status", {}).get("indicator")}
    """),

    "github-monitor": textwrap.dedent("""\
        import os
        import requests
        from fastapi import FastAPI
        app = FastAPI(title="PulseCheck GitHub Monitor")

        GITHUB_STATUS_URL = os.environ.get("MOCK_API_URL", "https://www.githubstatus.com/api/v2/status.json")

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "github-monitor"}

        @app.get("/status")
        def github_status():
            response = requests.get(GITHUB_STATUS_URL)
            data = response.json()
            return {"indicator": data["status"]["indicator"], "description": data["status"]["description"]}
    """),

    "dns-checker": textwrap.dedent("""\
        import os
        import requests
        from fastapi import FastAPI
        app = FastAPI(title="PulseCheck DNS Checker")

        DOH_URL = os.environ.get("MOCK_API_URL", "https://dns.google/resolve")

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "dns-checker"}

        @app.get("/resolve")
        def resolve(domain: str, record_type: str = "A"):
            response = requests.get(DOH_URL, params={"name": domain, "type": record_type})
            data = response.json()
            answers = data.get("Answer", [])
            return {"domain": domain, "resolved": len(answers) > 0, "records": [a["data"] for a in answers]}
    """),

    "slack-notifier": textwrap.dedent("""\
        import os
        import requests
        from fastapi import FastAPI
        from pydantic import BaseModel
        app = FastAPI(title="PulseCheck Slack Notifier")

        SLACK_WEBHOOK_URL = os.environ.get("MOCK_API_URL", "https://hooks.slack.com/services/placeholder")

        class Alert(BaseModel):
            service: str
            message: str

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "slack-notifier"}

        @app.post("/notify")
        def notify(alert: Alert):
            response = requests.post(SLACK_WEBHOOK_URL, json={"text": alert.message})
            return {"sent": response.status_code == 200}
    """),
}


# ── Step: install ────────────────────────────────────────────────────────────

def step_install():
    print("=== Step 1: Install Dynatrace OneAgent ===\n")
    print("Download OneAgent from your Dynatrace tenant:\n")
    print(f"  https://{DT_ENV}/#install/agentsetup;type=full\n")
    print("Steps:")
    print("  1. Click 'macOS' as the platform")
    print("  2. Download the installer (.sh file)")
    print("  3. Run it with sudo:")
    print("     sudo /bin/sh Dynatrace-OneAgent-MacOS-*.sh")
    print("  4. OneAgent starts automatically and connects to your tenant\n")
    print("Once installed, run:")
    print("  python scripts/dynatrace_setup.py --step run\n")
    print("Verify OneAgent is running:")
    print("  sudo launchctl list | grep dynatrace")


# ── Step: run ────────────────────────────────────────────────────────────────

OTEL_BOOTSTRAP = textwrap.dedent(f"""\
    # OpenTelemetry bootstrap - injected at top of every PulseCheck service
    # Instruments requests + httpx automatically and exports spans to Dynatrace
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    _exporter = OTLPSpanExporter(
        endpoint="{DT_OTEL_ENDPOINT}",
        headers={{"Authorization": "Api-Token {DT_OTEL_TOKEN}"}},
    )
    _provider = TracerProvider()
    _provider.add_span_processor(BatchSpanProcessor(_exporter))
    trace.set_tracer_provider(_provider)
    RequestsInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    # ── end OTel bootstrap ──
""")


def step_run():
    print("=== Step 2: Run PulseCheck services with OTel → Dynatrace ===\n")
    print(f"Exporting traces to: {DT_OTEL_ENDPOINT}\n")
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    procs = []
    for name, code in SERVICE_CODE.items():
        svc_dir = LOCAL_DIR / name
        svc_dir.mkdir(exist_ok=True)
        # Prepend OTel bootstrap so every HTTP call is auto-instrumented
        (svc_dir / "main.py").write_text(OTEL_BOOTSTRAP + "\n" + code)
        port = SERVICES[name]["port"]

        env = os.environ.copy()
        env["MOCK_API_URL"] = f"http://localhost:{SLOW_SERVER_PORT}"
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
                "--port", str(port), "--host", "0.0.0.0"],
            cwd=svc_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append((name, port, proc))
        print(f"  Started {name} on :{port} (pid={proc.pid})")

    time.sleep(3)
    print("\nVerifying health endpoints...")
    import httpx
    for name, port, _ in procs:
        try:
            r = httpx.get(f"http://localhost:{port}/health", timeout=3)
            status = r.json().get("status", "?")
            print(f"  {name}: {status}")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")

    pids = {name: proc.pid for name, _, proc in procs}
    (LOCAL_DIR / "pids.json").write_text(json.dumps(pids, indent=2))
    print(f"\nPIDs written to {LOCAL_DIR}/pids.json")
    print("\nNext - start the slow server in a new terminal:")
    print("  python scripts/dynatrace_setup.py --step slow-server")


# ── Step: slow-server ────────────────────────────────────────────────────────

SLOW_HOLD_SECONDS = 30  # hold then close - OTel span completes with error, gets exported


def step_slow_server():
    print(f"=== Step 3: Slow Server on :{SLOW_SERVER_PORT} ===\n")
    print(
        f"Holds each connection for {SLOW_HOLD_SECONDS}s then closes it abruptly.")
    print("This produces a completed failed span that OTel exports to Dynatrace.")
    print(
        f"\nListening on localhost:{SLOW_SERVER_PORT} - press Ctrl+C to stop.\n")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("localhost", SLOW_SERVER_PORT))
    server.listen(50)

    connections = []

    def hold_then_close(conn, addr):
        try:
            time.sleep(SLOW_HOLD_SECONDS)
            conn.close()
            print(
                f"  Closed {addr} after {SLOW_HOLD_SECONDS}s (span will export to Dynatrace)")
        except Exception:
            pass

    try:
        while True:
            conn, addr = server.accept()
            connections.append(conn)
            t = threading.Thread(target=hold_then_close,
                                 args=(conn, addr), daemon=True)
            t.start()
            print(
                f"  Accepted {addr} - holding for {SLOW_HOLD_SECONDS}s (total: {len(connections)})")
    except KeyboardInterrupt:
        print(f"\nStopped. Total connections held: {len(connections)}")
        server.close()


# ── Step: trigger ────────────────────────────────────────────────────────────

def step_trigger():
    print("=== Step 4: Trigger the incident ===\n")
    print(
        f"Calling each PulseCheck service with target=http://localhost:{SLOW_SERVER_PORT}")
    print("Each call will hang (no timeout). Dynatrace will capture slow outbound calls.\n")

    import httpx

    def call_with_timeout(name, port, path):
        try:
            # We set a long timeout here just to not block this script forever
            # The *service* has no timeout - that's the bug Dynatrace captures
            httpx.get(f"http://localhost:{port}{path}", timeout=30)
            print(f"  {name}: returned (unexpected)")
        except httpx.ReadTimeout:
            print(f"  {name}: timed out after 30s (Dynatrace captured the hang)")
        except Exception as e:
            print(f"  {name}: {e}")

    # Point all services at the slow server via env override for GET services
    # For services with configurable URLs, trigger directly
    threads = []
    trigger_map = [
        ("http-monitor",   9021,
         f"/check?target=http://localhost:{SLOW_SERVER_PORT}"),
        ("github-monitor", 9004, "/status"),   # uses MOCK_API_URL if set
        ("dns-checker",    9005, f"/resolve?domain=slow.internal"),
    ]

    print("Triggering hangs in parallel...\n")
    for name, port, path in trigger_map:
        t = threading.Thread(target=call_with_timeout,
                             args=(name, port, path), daemon=True)
        t.start()
        threads.append(t)

    # Also trigger slack-notifier via POST
    def trigger_slack():
        try:
            httpx.post(
                f"http://localhost:9007/notify",
                json={"service": "ssl-monitor", "message": "SSL check hung"},
                timeout=30,
            )
        except Exception:
            print("  slack-notifier: timed out (Dynatrace captured the hang)")

    t = threading.Thread(target=trigger_slack, daemon=True)
    t.start()
    threads.append(t)

    for t in threads:
        t.join(timeout=SLOW_HOLD_SECONDS + 10)

    print("\nHangs triggered. Wait 2-3 minutes for Dynatrace Davis to raise a problem.")
    print("Then run:")
    print("  python scripts/dynatrace_setup.py --step fetch-problem")


# ── Step: fetch-problem ──────────────────────────────────────────────────────

def step_fetch_problem():
    print("=== Step 5: Fetch real Dynatrace problem ===\n")
    import httpx

    MCP_URL = f"https://{DT_ENV}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
    headers = {"Authorization": f"Bearer {DT_TOKEN}",
               "Content-Type": "application/json"}

    # Query recent problems
    dql = "fetch dt.davis.problems | sort timestamp desc | limit 5"
    r = httpx.post(
        MCP_URL,
        json={"jsonrpc": "2.0", "method": "tools/call",
              "params": {"name": "execute-dql", "arguments": {"dqlQueryString": dql}}, "id": 1},
        headers=headers,
        timeout=20,
    )

    content = r.json().get("result", {}).get("content", [])
    records = []
    for item in reversed(content):
        text = item.get("text", "") if isinstance(item, dict) else ""
        if "Query result records:" in text:
            try:
                records = json.loads(text.split(
                    "Query result records:")[-1].strip()) or []
            except Exception:
                pass
            break

    if not records:
        print("No problems found yet. Wait another minute and try again.\n")
        print("You can also check directly:")
        print(f"  https://{DT_ENV}/#problems\n")
        return

    print(f"Found {len(records)} recent problem(s):\n")
    for i, p in enumerate(records):
        pid = p.get("display_id") or p.get("problemId") or p.get("id", "?")
        title = p.get("title") or p.get("problemTitle") or "Unknown"
        duration = p.get("duration") or p.get("durationMinutes") or "?"
        print(f"  [{i+1}] {pid} - {title} ({duration} min)")

    print()
    best = records[0]
    pid = best.get("display_id") or best.get("problemId") or best.get("id")
    print(f"Most recent: {pid}")
    print("\nTo update Ripple with this problem ID, run:")
    print(
        f"  python scripts/dynatrace_setup.py --step patch-ripple --problem-id {pid}")


# ── Step: push-event ────────────────────────────────────────────────────────

def step_push_event():
    """
    Push a synthetic availability event to Dynatrace via the v2 Events API.
    This creates a real Davis problem with a real problem ID that Ripple can query.
    """
    print("=== Step 5b: Push synthetic availability event to Dynatrace ===\n")
    import httpx

    # The Events Ingest API v2 - requires 'events.ingest' scope on the token
    EVENTS_URL = f"https://{_tenant}.live.dynatrace.com/api/v2/events/ingest"
    headers = {
        "Authorization": f"Api-Token {DT_EVENTS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "eventType": "AVAILABILITY_EVENT",
        "title": "PulseCheck ssl-monitor hung on slow cert check - cascade into latency-monitor and incident-manager",
        "entitySelector": "type(SERVICE)",
        "properties": {
            "dt.event.description": (
                "Multiple PulseCheck monitoring services made outbound HTTP calls with no timeout. "
                "ssl-monitor's /check endpoint hung indefinitely waiting for a slow TLS handshake, "
                "exhausting its thread pool. The hang cascaded into latency-monitor and incident-manager "
                "which share the same downstream client pattern. Root cause: requests.get() and httpx.get() "
                "called without timeout= argument across 11 of 12 PulseCheck services."
            ),
            "affected_services": "ssl-monitor, latency-monitor, incident-manager",
            "pattern": "HTTP call with no timeout",
            "estimated_cost": "£23,000",
            "duration_minutes": "47",
        },
    }

    r = httpx.post(EVENTS_URL, headers=headers, json=payload, timeout=15)
    print(f"Response: {r.status_code}")

    if r.status_code in (200, 201, 202):
        data = r.json()
        print(f"Event ingested: {data}\n")
        print("Davis will raise a problem within 1-2 minutes.")
        print("Then run:")
        print("  python scripts/dynatrace_setup.py --step fetch-problem")
    else:
        print(f"Error: {r.status_code} - {r.text}")


# ── Step: patch-ripple ───────────────────────────────────────────────────────

def step_patch_ripple(problem_id: str):
    print(f"=== Step 6: Patch Ripple with problem {problem_id} ===\n")
    import httpx

    MCP_URL = f"https://{DT_ENV}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
    headers = {"Authorization": f"Bearer {DT_TOKEN}",
               "Content-Type": "application/json"}

    # Fetch problem details
    dql = f'fetch dt.davis.problems | filter display_id == "{problem_id}" | limit 1'
    r = httpx.post(
        MCP_URL,
        json={"jsonrpc": "2.0", "method": "tools/call",
              "params": {"name": "execute-dql", "arguments": {"dqlQueryString": dql}}, "id": 1},
        headers=headers,
        timeout=20,
    )
    content = r.json().get("result", {}).get("content", [])
    records = []
    for item in reversed(content):
        text = item.get("text", "") if isinstance(item, dict) else ""
        if "Query result records:" in text:
            try:
                records = json.loads(text.split(
                    "Query result records:")[-1].strip()) or []
            except Exception:
                pass
            break

    problem = records[0] if records else {}
    duration = int(problem.get("duration")
                   or problem.get("durationMinutes") or 47)
    title = problem.get("title") or problem.get("problemTitle") or \
        "PulseCheck ssl-monitor hung on slow cert check"

    print(f"Problem: {problem_id}")
    print(f"Title:   {title}")
    print(f"Duration: {duration} min\n")

    # Patch IncidentPanel.tsx
    panel_path = Path(__file__).parent.parent / "dashboard" / \
        "components" / "IncidentPanel.tsx"
    code = panel_path.read_text()

    import re
    code = re.sub(r"id: '[^']*'", f"id: '{problem_id}'", code)
    code = re.sub(r"title: '[^']*'", f"title: '{title}'", code)
    code = re.sub(r"duration: \d+", f"duration: {duration}", code)
    panel_path.write_text(code)
    print(f"Patched {panel_path.name}")

    # Write incident context for webhook trigger
    incident_ctx = {
        "incident_id": problem_id,
        "duration_minutes": duration,
        "estimated_cost": "£23,000",
        "root_cause_summary": title,
    }
    ctx_path = Path(__file__).parent.parent / ".incident_context.json"
    ctx_path.write_text(json.dumps(incident_ctx, indent=2))
    print(f"Wrote incident context to .incident_context.json")

    print("\nRipple is now using the real Dynatrace problem.")
    print("Restart the dashboard and fire the webhook to see live data:")
    print(f"""
  curl -s -X POST http://localhost:8000/webhook \\
    -H "Content-Type: application/json" \\
    -d '{{
      "pr_id": "pulsecheck-dt-live",
      "repo": "cypherguy-group/pulsecheck/ssl-monitor",
      "diff": "@@ -12 +12 @@ response = httpx.get(target_url)",
      "incident_context": {json.dumps(incident_ctx)}
    }}' | jq .
""")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True,
                        choices=["install", "run", "slow-server", "trigger", "push-event", "fetch-problem", "patch-ripple"])
    parser.add_argument("--problem-id", default="")
    args = parser.parse_args()

    if args.step == "install":
        step_install()
    elif args.step == "run":
        step_run()
    elif args.step == "slow-server":
        step_slow_server()
    elif args.step == "trigger":
        step_trigger()
    elif args.step == "push-event":
        step_push_event()
    elif args.step == "fetch-problem":
        step_fetch_problem()
    elif args.step == "patch-ripple":
        if not args.problem_id:
            print("--problem-id is required for patch-ripple")
            sys.exit(1)
        step_patch_ripple(args.problem_id)


if __name__ == "__main__":
    main()
