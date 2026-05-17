"""
Deploy Ripple services to Cloud Run.
Usage: python scripts/cloud_deploy.py [service1 service2 ...]
If no args, deploys all services.
Services: intelligence, scanner, fix_factory, orchestrator, dashboard
"""
import os, sys, subprocess, tempfile, yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

REGISTRY = "europe-west2-docker.pkg.dev/ripple-496422/ripple-eu"
REGION = "europe-west2"
PROJECT = "ripple-496422"
ORCHESTRATOR_URL = "https://ripple-orchestrator-mctjeick3a-nw.a.run.app"
SECRETS = ",".join([
    "GITLAB_TOKEN=ripple-gitlab-token:latest",
    "DT_PLATFORM_TOKEN=ripple-dt-platform-token:latest",
    "DT_OTEL_TOKEN=ripple-dt-otel-token:latest",
    "DT_EVENTS_TOKEN=ripple-dt-events-token:latest",
    "MONGODB_URI=ripple-mongodb-uri:latest",
    "GEMINI_API_KEY=ripple-gemini-api-key:latest",
    "DT_ENVIRONMENT=ripple-dt-environment:latest",
    "DEMO_NAMESPACE=ripple-demo-namespace:latest",
    "INTERNAL_SECRET=ripple-internal-secret:latest",
    "ADMIN_SECRET=ripple-admin-secret:latest",
])

SERVICES = {
    "intelligence": {"name": "ripple-intelligence", "port": 8001, "env": {}},
    "scanner":      {"name": "ripple-scanner",      "port": 8002, "env": {"ORCHESTRATOR_URL": ORCHESTRATOR_URL}},
    "fix_factory":  {"name": "ripple-fix-factory",  "port": 8003, "env": {}},
    "orchestrator": {"name": "ripple-orchestrator", "port": 8000, "env": {
        "INTELLIGENCE_URL": "https://ripple-intelligence-mctjeick3a-nw.a.run.app",
        "SCANNER_URL":      "https://ripple-scanner-mctjeick3a-nw.a.run.app",
        "FIX_FACTORY_URL":  "https://ripple-fix-factory-mctjeick3a-nw.a.run.app",
        "ORCHESTRATOR_URL": ORCHESTRATOR_URL,
    }},
}


def build(svc: str, image: str):
    dockerfile = f"Dockerfile.{svc}" if svc != "dashboard" else "dashboard/Dockerfile"
    context = "." if svc != "dashboard" else "dashboard/"
    cb = {
        "steps": [{"name": "gcr.io/cloud-builders/docker",
                   "args": ["build", "-f", dockerfile, "-t", image, context]}],
        "images": [image],
        "options": {"logging": "CLOUD_LOGGING_ONLY"},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(cb, f)
        cb_path = f.name
    r = subprocess.run(
        ["gcloud", "builds", "submit", ".", "--config", cb_path,
         "--project", PROJECT, "--region", REGION, "--quiet"],
        capture_output=True, text=True,
    )
    os.unlink(cb_path)
    return r.returncode == 0, r.stderr[-200:]


def deploy(name: str, image: str, port: int, extra_env: dict):
    cmd = ["gcloud", "run", "deploy", name, "--image", image,
           "--region", REGION, "--project", PROJECT,
           "--allow-unauthenticated", "--set-secrets", SECRETS,
           "--memory", "1Gi", "--timeout", "300", "--port", str(port), "--quiet"]
    if extra_env:
        cmd += ["--set-env-vars", ",".join(f"{k}={v}" for k, v in extra_env.items())]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, r.stderr[-150:]


def deploy_dashboard(image: str):
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    env_vars = ",".join([
        f"NEXT_PUBLIC_WS_URL=wss://ripple-orchestrator-mctjeick3a-nw.a.run.app/ws",
        f"NEXT_PUBLIC_ORCHESTRATOR_URL={ORCHESTRATOR_URL}",
        f"NEXT_PUBLIC_ADMIN_SECRET={admin_secret}",
    ])
    r = subprocess.run(
        ["gcloud", "run", "deploy", "ripple-dashboard", "--image", image,
         "--region", REGION, "--project", PROJECT, "--allow-unauthenticated",
         "--memory", "512Mi", "--port", "3000", "--set-env-vars", env_vars, "--quiet"],
        capture_output=True, text=True,
    )
    return r.returncode == 0, r.stderr[-150:]


def main():
    targets = sys.argv[1:] or list(SERVICES.keys()) + ["dashboard"]
    os.chdir(ROOT)

    for svc in targets:
        image = f"{REGISTRY}/ripple-{svc.replace('_', '-')}:latest"
        if svc == "dashboard":
            image = f"{REGISTRY}/ripple-dashboard:latest"

        print(f"\n[{svc}] Building...")
        ok, err = build(svc, image)
        if not ok:
            print(f"  BUILD FAILED: {err}"); continue
        print(f"  Built ✓  Deploying...")

        if svc == "dashboard":
            ok, err = deploy_dashboard(image)
        else:
            cfg = SERVICES[svc]
            ok, err = deploy(cfg["name"], image, cfg["port"], cfg["env"])

        print(f"  {'Deployed ✓' if ok else 'DEPLOY FAILED: ' + err}")

    print("\nDone.")


if __name__ == "__main__":
    main()
