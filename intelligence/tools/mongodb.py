import logging
import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client = None

_VECTOR_INDEX = "pattern_vector_search"
_VECTOR_CANDIDATES = 20
_VECTOR_LIMIT = 5
_SIMILARITY_THRESHOLD = 0.70

_STOP_WORDS = {"a", "an", "the", "in", "on", "at", "to", "for", "of", "is", "are",
               "that", "this", "with", "without", "no", "not", "and", "or", "be",
               "it", "its", "when", "how", "what", "where", "which"}


def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client["ripple"]


def _key_terms(pattern: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{3,}", pattern.lower())
    return [w for w in words if w not in _STOP_WORDS][:6]


def _build_regex_query(pattern: str) -> dict:
    terms = _key_terms(pattern)
    if not terms:
        safe = re.escape(pattern[:40])
        return {"pattern": {"$regex": safe, "$options": "i"}}
    clauses = [{"pattern": {"$regex": re.escape(t), "$options": "i"}} for t in terms]
    return {"$and": clauses[:2]}


def _vector_search(col, embedding: list[float]) -> list[dict]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": _VECTOR_INDEX,
                "path": "pattern_embedding",
                "queryVector": embedding,
                "numCandidates": _VECTOR_CANDIDATES,
                "limit": _VECTOR_LIMIT,
            }
        },
        {
            "$addFields": {"score": {"$meta": "vectorSearchScore"}}
        },
        {
            "$match": {"score": {"$gte": _SIMILARITY_THRESHOLD}}
        },
        {
            "$project": {"_id": 0, "pattern_embedding": 0}
        },
    ]
    try:
        return list(col.aggregate(pipeline))
    except Exception as e:
        logger.warning("Vector search failed, falling back to regex: %s", e)
        return None  # signals caller to fall back


def find_similar_wins(pattern: str, _col=None, _embed_fn=None) -> list[dict]:
    col = _col if _col is not None else _get_db()["wins"]
    try:
        from shared.embeddings import embed_text
        embed_fn = _embed_fn or embed_text
        embedding = embed_fn(pattern)
        if embedding:
            results = _vector_search(col, embedding)
            if results is not None:
                return results
    except Exception as e:
        logger.warning("find_similar_wins embedding step failed: %s", e)
    return list(col.find(_build_regex_query(pattern), {"_id": 0, "pattern_embedding": 0}))


def find_similar_scars(pattern: str, _col=None, _embed_fn=None) -> list[dict]:
    col = _col if _col is not None else _get_db()["scars"]
    try:
        from shared.embeddings import embed_text
        embed_fn = _embed_fn or embed_text
        embedding = embed_fn(pattern)
        if embedding:
            results = _vector_search(col, embedding)
            if results is not None:
                return results
    except Exception as e:
        logger.warning("find_similar_scars embedding step failed: %s", e)
    return list(col.find(_build_regex_query(pattern), {"_id": 0, "pattern_embedding": 0}))
