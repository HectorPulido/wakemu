import os, tempfile, unittest, uuid
from pathlib import Path
from threading import Lock
from wakfu_server.store import Store
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_group_redis import RedisGroups
from wakfu_server.state_journal import StateJournalError


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


class RedisGroupsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "world.db")
        self.now = [0.0]
        self.client = self.make_client()
        self.namespace = "wakfu:test:groups:" + uuid.uuid4().hex
        self.addCleanup(self.client.delete, self.namespace)
        self.groups = self.make_groups()
        self.members = [owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)]
        self.key = self.groups.register(1134, 0, 501, self.members)

    def make_client(self):
        return MemoryRedis()

    def make_groups(self, **kw):
        return RedisGroups(
            self.store,
            self.client,
            namespace=self.namespace,
            clock=lambda: self.now[0],
            **kw
        )

    def saved(self):
        with self.store.connection() as db:
            return list(db.execute("SELECT * FROM combat_groups"))

    def test_batch_interval_and_shutdown(self):
        lease, _ = self.groups.claim(self.key, "a", 77)
        self.groups.finish(lease, defeated=True)
        self.assertEqual(self.saved(), [])
        self.now[0] = 1199
        self.assertEqual(self.groups.flush_due(), 0)
        self.now[0] = 1200
        self.assertEqual(self.groups.flush_due(), 1)
        self.assertEqual(self.saved()[0]["status"], "defeated")
        self.assertEqual(self.groups.flush(), 0)
        self.groups.respawn(self.key)
        self.assertEqual(self.groups.close(), 1)
        self.assertEqual(self.saved()[0]["status"], "available")

    def test_restart_preserves_defeat_and_invalidates_lost_fight(self):
        old, _ = self.groups.claim(self.key, "a", 77)
        after = self.make_groups(recover=True)
        self.assertEqual(len(after.available(1134, 0)), 1)
        self.assertFalse(after.finish(old, defeated=True))
        new, _ = after.claim(self.key, "a", 77)
        after.finish(new, defeated=True)
        self.assertEqual(self.make_groups(recover=True).available(1134, 0), [])
        self.assertEqual(self.saved(), [])

    def test_ownership_and_stale_outcome(self):
        active = {"a"}
        groups = self.make_groups(lease_active=lambda g: g in active)
        with self.assertRaises(ValueError):
            groups.claim(self.key, "b", 77)
        lease, _ = groups.claim(self.key, "a", 77)
        self.assertEqual(groups.release_session("b"), [])
        active.clear()
        self.assertEqual(len(groups.release_session("a")), 1)
        self.assertFalse(groups.finish(lease, defeated=True))

    def test_checkpoint_preserves_newer_mutation(self):
        value, encoded = self.groups.journal.read(self.key)
        lease, _ = self.groups.claim(self.key, "a", 77)
        self.groups.journal.checkpoint(self.key, encoded)
        latest, _ = self.groups.journal.read(self.key)
        self.assertEqual(latest["baseline"], value["current"])
        self.assertEqual(latest["current"]["status"], "fighting")
        # Simulate the SQL commit represented by this checkpoint.
        with self.store.connection() as db:
            import json

            s = value["current"]
            db.execute(
                "INSERT INTO combat_groups VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    *self.key,
                    json.dumps(s["members"]),
                    s["status"],
                    None,
                    None,
                    s["revision"],
                    None,
                ),
            )
        self.assertEqual(self.groups.flush(), 1)
        self.assertEqual(self.saved()[0]["status"], "fighting")

    def test_sql_conflict_rolls_back_batch(self):
        self.groups.flush()
        lease, _ = self.groups.claim(self.key, "a", 77)
        with self.store.connection() as db:
            db.execute("UPDATE combat_groups SET revision=revision+9")
        with self.assertRaises(StateJournalError):
            self.groups.flush()
        self.assertEqual(self.saved()[0]["status"], "available")
        self.assertEqual(self.groups.available(1134, 0), [])

    def test_sql_commit_checkpoint_failure_is_retryable(self):
        original = self.groups.journal.checkpoint

        def fail(*args):
            raise StateJournalError("simulated checkpoint outage")

        self.groups.journal.checkpoint = fail
        with self.assertRaises(StateJournalError):
            self.groups.flush()
        self.assertEqual(len(self.saved()), 1)
        self.groups.journal.checkpoint = original
        self.assertEqual(self.groups.flush(), 1)
        self.assertEqual(self.groups.flush(), 0)
        self.assertEqual(len(self.saved()), 1)

    def test_restart_hydrates_sqlite_without_duplicate_registration(self):
        self.groups.close()
        self.client.delete(self.namespace)
        restored = self.make_groups(recover=True)
        self.assertEqual(restored.register(1134, 0, 501, self.members), self.key)
        self.assertEqual(len(restored.available(1134, 0)), 1)
        self.assertEqual(restored.flush(), 0)

    def test_two_workers_cannot_claim_same_group(self):
        other = self.make_groups()
        lease, _ = self.groups.claim(self.key, "a", 77)
        with self.assertRaises(ValueError):
            other.claim(self.key, "b", 78)
        self.assertTrue(other.finish(lease, defeated=False))

    def test_redis_failure_never_falls_back(self):
        if not isinstance(self.client, MemoryRedis):
            self.skipTest("failure injection only")
        self.client.fail = True
        with self.assertRaises(StateJournalError):
            self.groups.claim(self.key, "a", 77)
        with self.assertRaises(StateJournalError):
            self.make_groups()
        self.client.fail = False
        self.assertEqual(len(self.groups.available(1134, 0)), 1)
        self.assertEqual(self.saved(), [])


@unittest.skipUnless(
    os.environ.get("WAKFU_REDIS_TEST_URL"), "isolated Redis URL required"
)
class RealRedisGroupsTests(RedisGroupsTests):
    def make_client(self):
        import redis

        return redis.Redis.from_url(
            os.environ["WAKFU_REDIS_TEST_URL"], decode_responses=True
        )
