import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from cache import AnswerCache, normalize  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(tmp_path, **kw):
    db = tmp_path / "shop.db"
    db.write_text("x")
    clock = Clock()
    return AnswerCache(db_path=str(db), clock=clock, **kw), clock, db


def test_normalize_ignores_case_and_punctuation():
    assert normalize("Pan card NEW price?") == normalize("pan card new price")


def test_hit_after_put(tmp_path):
    c, _, _ = make(tmp_path)
    c.put("pan card new price", "PAN card costs INR 300.")
    assert c.get("Pan Card New Price?") == "PAN card costs INR 300."
    assert c.stats()["hits"] == 1


def test_miss_when_database_changes(tmp_path):
    c, _, db = make(tmp_path)
    c.put("pan card new price", "INR 300")
    os.utime(db, (os.path.getmtime(db) + 10, os.path.getmtime(db) + 10))
    assert c.get("pan card new price") is None


def test_entry_expires(tmp_path):
    c, clock, _ = make(tmp_path, ttl_seconds=60)
    c.put("hello", "hi")
    clock.t += 61
    assert c.get("hello") is None


def test_oldest_entry_is_evicted(tmp_path):
    c, _, _ = make(tmp_path, max_items=2)
    c.put("a", "1")
    c.put("b", "2")
    c.put("c", "3")
    assert c.get("a") is None
    assert c.get("c") == "3"