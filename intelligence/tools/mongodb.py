import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client["ripple"]


_STOP_WORDS = {"a", "an", "the", "in", "on", "at", "to", "for", "of", "is", "are",
               "that", "this", "with", "without", "no", "not", "and", "or", "be",
               "it", "its", "when", "how", "what", "where", "which"}


def _key_terms(pattern: str) -> list[str]:
    """Extract significant words from a pattern for fuzzy matching."""
    words = re.findall(r"[a-zA-Z]{3,}", pattern.lower())
    return [w for w in words if w not in _STOP_WORDS][:6]


def _build_query(pattern: str) -> dict:
    terms = _key_terms(pattern)
    if not terms:
        safe = re.escape(pattern[:40])
        return {"pattern": {"$regex": safe, "$options": "i"}}
    # Match documents whose pattern contains at least 2 of the key terms
    clauses = [{"pattern": {"$regex": re.escape(t), "$options": "i"}} for t in terms]
    return {"$and": clauses[:2]}  # require first 2 key terms to match


def find_similar_wins(pattern: str, _col=None) -> list[dict]:
    col = _col if _col is not None else _get_db()["wins"]
    return list(col.find(_build_query(pattern), {"_id": 0}))


def find_similar_scars(pattern: str, _col=None) -> list[dict]:
    col = _col if _col is not None else _get_db()["scars"]
    return list(col.find(_build_query(pattern), {"_id": 0}))
