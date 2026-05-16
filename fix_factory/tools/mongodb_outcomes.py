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
