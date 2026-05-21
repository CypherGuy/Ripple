"""Clear all scars and wins from Ripple's institutional memory."""
from dotenv import load_dotenv
load_dotenv()

import os
from pymongo import MongoClient

client = MongoClient(os.environ["MONGODB_URI"])
db = client["ripple"]

w = db["wins"].delete_many({})
s = db["scars"].delete_many({})

print(f"Deleted {w.deleted_count} wins, {s.deleted_count} scars")
