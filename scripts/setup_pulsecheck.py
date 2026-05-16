"""
Creates 12 PulseCheck repos under cypherguy-group/pulsecheck and pushes real code.
Run: python scripts/setup_pulsecheck.py
"""
import os
import sys
import base64
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

GITLAB_BASE = "https://gitlab.com/api/v4"
NAMESPACE = "cypherguy-group/pulsecheck"
NAMESPACE_ID = 132406814  # cypherguy-group/pulsecheck group ID
TOKEN = os.environ["GITLAB_TOKEN"]
HEADERS = {"PRIVATE-TOKEN": TOKEN, "Content-Type": "application/json"}

REQUIREMENTS = "fastapi\nuvicorn\nrequests\nhttpx\npython-dotenv\n"

SERVICES = {
    "http-monitor": {
        "description": "Checks whether HTTP endpoints are reachable and returns their status code.",
        "port": 9001,
        "main": '''import os
import requests
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck HTTP Monitor")


@app.get("/health")
def health():
    return {"status": "ok", "service": "http-monitor"}


@app.get("/check")
def check(target: str):
    """Check whether a URL is reachable."""
    response = requests.get(target)
    return {
        "url": target,
        "status_code": response.status_code,
        "reachable": response.status_code < 500,
    }


@app.get("/check/batch")
def check_batch(targets: str):
    """Check multiple comma-separated URLs."""
    results = []
    for url in targets.split(","):
        url = url.strip()
        response = requests.get(url)
        results.append({"url": url, "status_code": response.status_code})
    return {"results": results}
''',
    },

    "ssl-monitor": {
        "description": "Verifies SSL certificates are valid and not close to expiry.",
        "port": 9002,
        "main": '''import httpx
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
''',
    },

    "api-monitor": {
        "description": "Polls third-party API health endpoints and reports their availability.",
        "port": 9003,
        "main": '''import requests
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck API Monitor")

WATCHED_APIS = {
    "stripe": "https://status.stripe.com/api/v2/status.json",
    "twilio": "https://status.twilio.com/api/v2/status.json",
    "sendgrid": "https://status.sendgrid.com/api/v2/status.json",
}


@app.get("/health")
def health():
    return {"status": "ok", "service": "api-monitor"}


@app.get("/check/{api_name}")
def check_api(api_name: str):
    """Check a specific third-party API status page."""
    url = WATCHED_APIS.get(api_name)
    if not url:
        return {"error": "unknown api"}
    response = requests.get(url)
    data = response.json()
    return {
        "api": api_name,
        "indicator": data.get("status", {}).get("indicator"),
        "description": data.get("status", {}).get("description"),
    }


@app.get("/check/all")
def check_all():
    """Check all watched APIs."""
    results = {}
    for name, url in WATCHED_APIS.items():
        r = requests.get(url)
        results[name] = r.json().get("status", {}).get("indicator")
    return results
''',
    },

    "github-monitor": {
        "description": "Monitors GitHub and GitLab platform status via their public status APIs.",
        "port": 9004,
        "main": '''import requests
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck GitHub Monitor")

GITHUB_STATUS_URL = "https://www.githubstatus.com/api/v2/status.json"
GITHUB_COMPONENTS_URL = "https://www.githubstatus.com/api/v2/components.json"


@app.get("/health")
def health():
    return {"status": "ok", "service": "github-monitor"}


@app.get("/status")
def github_status():
    """Fetch current GitHub platform status."""
    response = requests.get(GITHUB_STATUS_URL)
    data = response.json()
    return {
        "indicator": data["status"]["indicator"],
        "description": data["status"]["description"],
        "updated_at": data["page"]["updated_at"],
    }


@app.get("/components")
def github_components():
    """Fetch status of individual GitHub components (Actions, Pages, API, etc.)."""
    response = requests.get(GITHUB_COMPONENTS_URL)
    components = response.json().get("components", [])
    return [
        {"name": c["name"], "status": c["status"]}
        for c in components
        if c.get("status") != "operational"
    ]
''',
    },

    "dns-checker": {
        "description": "Resolves DNS records via Google DNS-over-HTTPS and reports resolution status.",
        "port": 9005,
        "main": '''import requests
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck DNS Checker")

DOH_URL = "https://dns.google/resolve"


@app.get("/health")
def health():
    return {"status": "ok", "service": "dns-checker"}


@app.get("/resolve")
def resolve(domain: str, record_type: str = "A"):
    """Resolve a DNS record via Google DNS-over-HTTPS."""
    response = requests.get(DOH_URL, params={"name": domain, "type": record_type})
    data = response.json()
    answers = data.get("Answer", [])
    return {
        "domain": domain,
        "type": record_type,
        "resolved": len(answers) > 0,
        "records": [a["data"] for a in answers],
        "status": data.get("Status"),
    }


@app.get("/resolve/batch")
def resolve_batch(domains: str):
    """Resolve multiple comma-separated domains."""
    results = []
    for domain in domains.split(","):
        domain = domain.strip()
        r = requests.get(DOH_URL, params={"name": domain, "type": "A"})
        answers = r.json().get("Answer", [])
        results.append({"domain": domain, "resolved": len(answers) > 0})
    return results
''',
    },

    "latency-monitor": {
        "description": "Measures HTTP response latency for target URLs and flags slow responses.",
        "port": 9006,
        "main": '''import time
import httpx
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck Latency Monitor")

SLOW_THRESHOLD_MS = 2000


@app.get("/health")
def health():
    return {"status": "ok", "service": "latency-monitor"}


@app.get("/measure")
def measure(target: str):
    """Measure response latency for a URL."""
    start = time.time()
    result = httpx.get(target)
    elapsed_ms = int((time.time() - start) * 1000)
    return {
        "url": target,
        "status_code": result.status_code,
        "latency_ms": elapsed_ms,
        "slow": elapsed_ms > SLOW_THRESHOLD_MS,
    }


@app.get("/measure/batch")
def measure_batch(targets: str):
    """Measure latency for multiple comma-separated URLs."""
    results = []
    for url in targets.split(","):
        url = url.strip()
        start = time.time()
        r = httpx.get(url)
        elapsed_ms = int((time.time() - start) * 1000)
        results.append({"url": url, "latency_ms": elapsed_ms, "status_code": r.status_code})
    return results
''',
    },

    "slack-notifier": {
        "description": "Sends alert notifications to Slack channels via incoming webhooks.",
        "port": 9007,
        "main": '''import os
import requests
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck Slack Notifier")

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


class Alert(BaseModel):
    service: str
    message: str
    severity: str = "warning"


@app.get("/health")
def health():
    return {"status": "ok", "service": "slack-notifier"}


@app.post("/notify")
def notify(alert: Alert):
    """Send an alert to Slack."""
    emoji = ":red_circle:" if alert.severity == "critical" else ":warning:"
    payload = {
        "text": f"{emoji} *{alert.service}* — {alert.message}",
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    return {"sent": response.status_code == 200}


@app.post("/notify/resolve")
def notify_resolve(alert: Alert):
    """Send a resolution notification to Slack."""
    payload = {
        "text": f":white_check_mark: *{alert.service}* resolved — {alert.message}",
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    return {"sent": response.status_code == 200}
''',
    },

    "email-notifier": {
        "description": "Sends alert emails via the SendGrid API when services go down or recover.",
        "port": 9008,
        "main": '''import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck Email Notifier")

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL = os.environ.get("ALERT_FROM_EMAIL", "alerts@pulsecheck.io")


class EmailAlert(BaseModel):
    to: str
    service: str
    message: str
    severity: str = "warning"


@app.get("/health")
def health():
    return {"status": "ok", "service": "email-notifier"}


@app.post("/send")
def send_alert(alert: EmailAlert):
    """Send an alert email via SendGrid."""
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "personalizations": [{"to": [{"email": alert.to}]}],
        "from": {"email": FROM_EMAIL},
        "subject": f"[PulseCheck] {alert.severity.upper()}: {alert.service}",
        "content": [{"type": "text/plain", "value": alert.message}],
    }
    response = requests.post(SENDGRID_URL, headers=headers, json=payload)
    return {"sent": response.status_code == 202, "status": response.status_code}
''',
    },

    "webhook-dispatcher": {
        "description": "Forwards alert events to user-configured webhook URLs when checks fail.",
        "port": 9009,
        "main": '''import requests
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck Webhook Dispatcher")


class WebhookEvent(BaseModel):
    webhook_url: str
    service: str
    event: str
    payload: dict = {}


@app.get("/health")
def health():
    return {"status": "ok", "service": "webhook-dispatcher"}


@app.post("/dispatch")
def dispatch(event: WebhookEvent):
    """Forward an alert event to a user-configured webhook URL."""
    body = {
        "service": event.service,
        "event": event.event,
        **event.payload,
    }
    response = requests.post(event.webhook_url, json=body)
    return {
        "dispatched": True,
        "status_code": response.status_code,
        "webhook_url": event.webhook_url,
    }


@app.post("/dispatch/batch")
def dispatch_batch(events: list[WebhookEvent]):
    """Dispatch multiple events to their respective webhooks."""
    results = []
    for event in events:
        body = {"service": event.service, "event": event.event, **event.payload}
        r = requests.post(event.webhook_url, json=body)
        results.append({"webhook_url": event.webhook_url, "status_code": r.status_code})
    return results
''',
    },

    "incident-manager": {
        "description": "Creates and resolves incidents in PagerDuty when checks breach thresholds.",
        "port": 9010,
        "main": '''import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck Incident Manager")

PAGERDUTY_URL = "https://events.pagerduty.com/v2/enqueue"
PD_ROUTING_KEY = os.environ.get("PAGERDUTY_ROUTING_KEY", "")


class Incident(BaseModel):
    service: str
    summary: str
    severity: str = "error"
    dedup_key: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "service": "incident-manager"}


@app.post("/trigger")
def trigger_incident(incident: Incident):
    """Trigger a PagerDuty incident."""
    payload = {
        "routing_key": PD_ROUTING_KEY,
        "event_action": "trigger",
        "dedup_key": incident.dedup_key or incident.service,
        "payload": {
            "summary": f"{incident.service}: {incident.summary}",
            "severity": incident.severity,
            "source": "pulsecheck",
        },
    }
    response = requests.post(PAGERDUTY_URL, json=payload)
    return {"triggered": response.status_code == 202, "dedup_key": incident.dedup_key}


@app.post("/resolve")
def resolve_incident(dedup_key: str):
    """Resolve a PagerDuty incident."""
    payload = {
        "routing_key": PD_ROUTING_KEY,
        "event_action": "resolve",
        "dedup_key": dedup_key,
    }
    response = requests.post(PAGERDUTY_URL, json=payload)
    return {"resolved": response.status_code == 202}
''',
    },

    "metrics-collector": {
        "description": "Records uptime and latency measurements into an InfluxDB time-series store.",
        "port": 9011,
        "main": '''import os
import time
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck Metrics Collector")

INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "pulsecheck")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "uptime")


class Measurement(BaseModel):
    service: str
    latency_ms: int
    status_code: int
    reachable: bool


@app.get("/health")
def health():
    return {"status": "ok", "service": "metrics-collector"}


@app.post("/record")
def record(measurement: Measurement):
    """Write a measurement to InfluxDB."""
    line = (
        f"uptime,service={measurement.service} "
        f"latency={measurement.latency_ms},"
        f"status_code={measurement.status_code},"
        f"reachable={'true' if measurement.reachable else 'false'} "
        f"{int(time.time() * 1e9)}"
    )
    headers = {
        "Authorization": f"Token {INFLUX_TOKEN}",
        "Content-Type": "text/plain; charset=utf-8",
    }
    response = requests.post(
        f"{INFLUX_URL}/api/v2/write",
        params={"org": INFLUX_ORG, "bucket": INFLUX_BUCKET, "precision": "ns"},
        headers=headers,
        data=line,
    )
    return {"recorded": response.status_code == 204}
''',
    },

    "report-generator": {
        "description": "Produces uptime summary reports by fetching metrics from the collector API.",
        "port": 9012,
        "main": '''import os
import requests
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="PulseCheck Report Generator")

METRICS_URL = os.environ.get("METRICS_COLLECTOR_URL", "http://localhost:9011")
COLLECTOR_URL = os.environ.get("METRICS_COLLECTOR_URL", "http://localhost:9011")


@app.get("/health")
def health():
    return {"status": "ok", "service": "report-generator"}


@app.get("/report/daily")
def daily_report(service: str):
    """Generate a daily uptime report for a service."""
    response = requests.get(f"{COLLECTOR_URL}/metrics/daily", params={"service": service})
    data = response.json()
    uptime_pct = data.get("uptime_percent", 0)
    return {
        "service": service,
        "period": "24h",
        "uptime_percent": uptime_pct,
        "status": "healthy" if uptime_pct >= 99.9 else "degraded",
        "incidents": data.get("incident_count", 0),
        "avg_latency_ms": data.get("avg_latency_ms", 0),
    }


@app.get("/report/weekly")
def weekly_report(service: str):
    """Generate a weekly uptime summary for a service."""
    response = requests.get(f"{COLLECTOR_URL}/metrics/weekly", params={"service": service})
    data = response.json()
    return {
        "service": service,
        "period": "7d",
        "uptime_percent": data.get("uptime_percent", 0),
        "total_downtime_minutes": data.get("downtime_minutes", 0),
        "incidents": data.get("incident_count", 0),
    }
''',
    },
}


def create_project(name: str, description: str) -> int | None:
    r = httpx.post(
        f"{GITLAB_BASE}/projects",
        headers=HEADERS,
        json={
            "name": name,
            "path": name,
            "namespace_id": NAMESPACE_ID,
            "description": description,
            "visibility": "private",
            "initialize_with_readme": False,
        },
        timeout=15,
    )
    if r.status_code in (200, 201):
        pid = r.json()["id"]
        print(f"  Created {name} (id={pid})")
        return pid
    # already exists — look it up
    if r.status_code == 400:
        search = httpx.get(
            f"{GITLAB_BASE}/groups/{NAMESPACE_ID}/projects",
            headers=HEADERS,
            params={"search": name},
            timeout=10,
        )
        for p in search.json():
            if p["path"] == name:
                print(f"  {name} already exists (id={p['id']})")
                return p["id"]
    print(f"  ERROR creating {name}: {r.status_code} {r.text[:200]}")
    return None


def push_file(project_id: int, path: str, content: str, message: str, branch: str = "main"):
    encoded = base64.b64encode(content.encode()).decode()
    # try create
    r = httpx.post(
        f"{GITLAB_BASE}/projects/{project_id}/repository/files/{path.replace('/', '%2F')}",
        headers=HEADERS,
        json={"branch": branch, "content": content, "commit_message": message, "encoding": "text"},
        timeout=15,
    )
    if r.status_code in (200, 201):
        return
    # try update
    httpx.put(
        f"{GITLAB_BASE}/projects/{project_id}/repository/files/{path.replace('/', '%2F')}",
        headers=HEADERS,
        json={"branch": branch, "content": content, "commit_message": message, "encoding": "text"},
        timeout=15,
    )


def main():
    print("=== PulseCheck Setup ===\n")
    for name, svc in SERVICES.items():
        print(f"[{name}]")
        pid = create_project(name, svc["description"])
        if not pid:
            continue

        readme = f"# {name}\n\n{svc['description']}\n\n## Run\n\n```bash\nuvicorn main:app --port {svc['port']}\n```\n"
        push_file(pid, "README.md", readme, "Add README")
        push_file(pid, "requirements.txt", REQUIREMENTS, "Add requirements")
        push_file(pid, "main.py", svc["main"], "Add service implementation")
        print(f"  Pushed code to {name}\n")

    print("=== Done ===")
    print(f"All services at: https://gitlab.com/groups/cypherguy-group/pulsecheck")


if __name__ == "__main__":
    main()
