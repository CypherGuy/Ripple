"""Create Atlas Vector Search indexes on ripple.wins and ripple.scars.

Run once: python3 scripts/create_vector_indexes.py

Requires M10+ Atlas cluster. Indexes build asynchronously (~1-2 min).
"""
import os
import sys
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

INDEX_NAME = "pattern_vector_search"
INDEX_DEF = {
    "fields": [
        {
            "type": "vector",
            "path": "pattern_embedding",
            "numDimensions": 768,
            "similarity": "cosine",
        }
    ]
}


def create_index(col):
    existing = [idx["name"] for idx in col.list_search_indexes()]
    if INDEX_NAME in existing:
        print(f"  [{col.name}] index '{INDEX_NAME}' already exists - skipping")
        return

    model = SearchIndexModel(definition=INDEX_DEF,
                             name=INDEX_NAME, type="vectorSearch")
    col.create_search_index(model=model)
    print(f"  [{col.name}] index creation requested - building asynchronously")


def wait_for_ready(col, timeout=120):
    print(f"  [{col.name}] waiting for index to become READY...",
          end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        for idx in col.list_search_indexes():
            if idx["name"] == INDEX_NAME and idx.get("status") == "READY":
                print(" READY")
                return True
        print(".", end="", flush=True)
        time.sleep(5)
    print(f"\n  [{col.name}] timed out waiting for index")
    return False


if __name__ == "__main__":
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI not set")
        sys.exit(1)

    client = MongoClient(uri)
    db = client["ripple"]

    print("Creating Atlas Vector Search indexes...")
    for name in ("wins", "scars"):
        col = db[name]
        try:
            create_index(col)
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
            print(
                "  Is this an M10+ Atlas cluster? Free tier (M0) does not support vector search.")
            sys.exit(1)

    print("\nWaiting for indexes to become ready...")
    for name in ("wins", "scars"):
        wait_for_ready(db[name])

    print("\nDone. Vector search is active on ripple.wins and ripple.scars.")
