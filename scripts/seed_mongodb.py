import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

SCARS = [
    {
        "pattern": "HTTP call with no timeout in async context",
        "service": "gateway-service",
        "outcome": "rejected",
        "reason": "Timeout intentionally absent — call is to an internal sidecar with sub-millisecond guaranteed response time. Risk suppressed for this service.",
        "risk_adjustment": -3,
        "date": "2026-01-12",
    },
    {
        "pattern": "HTTP call with no timeout in async context",
        "service": "config-service",
        "outcome": "rejected",
        "reason": "Config fetch runs at startup only — blocking is intentional, service does not start until config is loaded.",
        "risk_adjustment": -2,
        "date": "2026-03-08",
    },
]

WINS = [
    {
        "pattern": "HTTP call with no timeout in async context",
        "service": "auth-service",
        "outcome": "merged",
        "reason": "Added 5s timeout to downstream call. No incidents in auth-service in the 83 days since fix merged.",
        "confidence_boost": 2,
        "date": "2026-02-20",
    },
    {
        "pattern": "HTTP call with no timeout in async context",
        "service": "session-service",
        "outcome": "merged",
        "reason": "Added 3s timeout. PR merged without modification by the service owner.",
        "confidence_boost": 1,
        "date": "2026-04-01",
    },
]


def seed():
    db = MongoClient(os.environ["MONGODB_URI"])["ripple"]
    db["scars"].delete_many({})
    db["wins"].delete_many({})
    for doc in SCARS:
        db["scars"].insert_one(doc)
        print(f"Inserted scar: {doc['service']}")
    for doc in WINS:
        db["wins"].insert_one(doc)
        print(f"Inserted win: {doc['service']}")


if __name__ == "__main__":
    seed()
