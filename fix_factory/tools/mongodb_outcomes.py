import os
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_col():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client["ripple"]["outcomes"]


def store_outcome(outcome: dict, _col=None) -> None:
    col = _col if _col is not None else _get_col()
    col.insert_one({**outcome, "stored_at": datetime.now(timezone.utc).isoformat()})


def _get_wins_col():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client["ripple"]["wins"]


def _get_scars_col():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client["ripple"]["scars"]


def record_feedback(
    service: str,
    mr_url: str | None,
    outcome: str,
    pattern: str,
    reason: str,
    _wins_col=None,
    _scars_col=None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "service": service,
        "mr_url": mr_url,
        "outcome": outcome,
        "pattern": pattern,
        "reason": reason,
        "recorded_at": now,
    }
    if outcome == "merged":
        col = _wins_col if _wins_col is not None else _get_wins_col()
        col.insert_one({**doc, "confidence_boost": 1})
    else:
        col = _scars_col if _scars_col is not None else _get_scars_col()
        col.insert_one({**doc, "risk_adjustment": -2})
