"""Clear all scars and wins from Ripple's institutional memory."""
import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()


client = MongoClient(os.environ["MONGODB_URI"])
db = client["ripple"]

w = db["wins"].delete_many({})
s = db["scars"].delete_many({})

print(f"Deleted {w.deleted_count} wins, {s.deleted_count} scars")
