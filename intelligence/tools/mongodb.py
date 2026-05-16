import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client["ripple"]


def find_similar_wins(pattern: str, _col=None) -> list[dict]:
    col = _col if _col is not None else _get_db()["wins"]
    return list(col.find({"pattern": {"$regex": pattern[:40], "$options": "i"}}, {"_id": 0}))


def find_similar_scars(pattern: str, _col=None) -> list[dict]:
    col = _col if _col is not None else _get_db()["scars"]
    return list(col.find({"pattern": {"$regex": pattern[:40], "$options": "i"}}, {"_id": 0}))
