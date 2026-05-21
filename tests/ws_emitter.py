"""
Replays a realistic 20-service fan-out event sequence against the Orchestrator
POST /internal/broadcast endpoint, which relays to all WebSocket clients.
Run this while the dashboard is open to see tiles transition colour live.
"""
import time
import httpx
from datetime import datetime, timezone

BROADCAST_URL = "http://localhost:8000/internal/broadcast"

SERVICES_WITH_HITS = {
    "payment-service": "src/http/client.py",
    "auth-service": "src/clients/downstream.py",
    "order-service": "src/http/external.py",
    "notification-service": "src/senders/email.py",
    "inventory-service": "src/sync/upstream.py",
    "billing-service": "src/integrations/stripe.py",
    "reporting-service": "src/fetch/warehouse.py",
}

SERVICES_CLEAN = [
    "gateway-service", "user-service", "search-service", "analytics-service",
    "recommendation-service", "config-service", "audit-service", "session-service",
    "webhook-service", "cache-service", "scheduler-service", "export-service", "admin-service",
]

ALL_SERVICES = list(SERVICES_WITH_HITS.keys()) + SERVICES_CLEAN


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(data: dict) -> None:
    try:
        httpx.post(BROADCAST_URL, json=data, timeout=5)
    except Exception as e:
        print(f"  warn: could not broadcast ({e})")


def run():
    print(f"Emitting {len(ALL_SERVICES)} agent events to {BROADCAST_URL}")
    print("Keep the Ripple dashboard open at http://localhost:3000\n")

    # Fire agent_started for all services simultaneously
    for svc in ALL_SERVICES:
        emit({"event": "agent_started", "service": svc, "timestamp": ts()})
        print(f"  → agent_started  {svc}")
        time.sleep(0.08)

    print()

    # Stagger results - hits and no-hits interleaved
    import random
    results = (
        [(svc, True, path) for svc, path in SERVICES_WITH_HITS.items()] +
        [(svc, False, None) for svc in SERVICES_CLEAN]
    )
    random.shuffle(results)

    for svc, is_hit, file_path in results:
        time.sleep(random.uniform(0.2, 0.7))

        if is_hit:
            emit({
                "event": "hit_found",
                "service": svc,
                "timestamp": ts(),
                "data": {
                    "file_path": file_path,
                    "matching_lines": [{"line_number": 42, "content": "response = requests.get(url)"}],
                    "confidence": round(random.uniform(0.88, 0.97), 2),
                },
            })
            print(f"  ● hit_found      {svc} → {file_path}")
        else:
            emit({"event": "no_hit", "service": svc, "timestamp": ts()})
            print(f"  ✓ no_hit         {svc}")

    print(f"\nDone. 7 hits across {len(ALL_SERVICES)} services.")


if __name__ == "__main__":
    run()
