"""
Small in-memory answer cache for repeated first questions.

Safe because: it is cleared when shop.db changes, entries expire, and the agent
never caches time-dependent or failed answers (see agent.py).
"""
import os
import re
import time
from collections import OrderedDict

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "shop.db")


def normalize(text: str) -> str:
    """'Pan card NEW price?' and 'pan card new price' become the same key."""
    t = re.sub(r"[^\w\s\u0b80-\u0bff]", " ", text.lower())
    return " ".join(t.split())


class AnswerCache:
    def __init__(self, ttl_seconds=2 * 3600, max_items=500, db_path=DB_PATH, clock=time.time):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self.db_path = db_path
        self.clock = clock
        # Set the environment variable ANSWER_CACHE=off to disable (used when running the eval).
        self.enabled = os.getenv("ANSWER_CACHE", "on").lower() != "off"
        self._items = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _db_stamp(self):
        try:
            return os.path.getmtime(self.db_path)
        except OSError:
            return 0

    def get(self, message: str):
        if not self.enabled:
            return None
        key = normalize(message)
        entry = self._items.get(key)
        if entry:
            reply, expires, stamp = entry
            if self.clock() < expires and stamp == self._db_stamp():
                self._items.move_to_end(key)
                self.hits += 1
                return reply
            del self._items[key]
        self.misses += 1
        return None

    def put(self, message: str, reply: str):
        if not self.enabled or not reply:
            return
        key = normalize(message)
        self._items[key] = (reply, self.clock() + self.ttl, self._db_stamp())
        self._items.move_to_end(key)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)

    def stats(self):
        total = self.hits + self.misses
        rate = round(100 * self.hits / total, 1) if total else 0.0
        return {"hits": self.hits, "misses": self.misses, "hit_rate_pct": rate, "size": len(self._items)}