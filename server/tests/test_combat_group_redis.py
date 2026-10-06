"""Small Redis-shaped failure fixture used by legacy isolation tests.

Group persistence behavior tests moved to PostgreSQL coverage in
test_combat_group_store.py; this fixture remains imported by unrelated tests.
"""
from threading import Lock


class MemoryRedis:
    def __init__(self):
        self.data = {}
        self.fail = False
        self.lock = Lock()

    def ping(self):
        if self.fail:
            raise OSError("unavailable")
        return True

    def hget(self, key, field):
        self.ping()
        return self.data.get(key, {}).get(field)

    def hkeys(self, key):
        self.ping()
        return list(self.data.get(key, {}))

    def eval(self, script, n, key, field, expected, replacement):
        self.ping()
        with self.lock:
            records = self.data.setdefault(key, {})
            old = records.get(field)
            if (not expected and old is not None) or (expected and old != expected):
                return 0
            records[field] = replacement
            return 1

    def delete(self, key):
        self.data.pop(key, None)
