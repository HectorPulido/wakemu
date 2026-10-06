import json
import os
import unittest
import uuid
from postgres_case import PostgresCase
from wakfu_server.position_buffer import Positions
from wakfu_server.position_redis import (
    Journal,
    RedisPositions,
    PositionJournalError,
    PositionJournalUnavailable,
    create,
)
from wakfu_server.session_cleanup import retry_step


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.fail = False

    def eval(self, script, n, key, field, expected, *replacement):
        if self.fail:
            raise OSError("test Redis unavailable")
        records = self.values.setdefault(key, {})
        old = records.get(field)
        if replacement:
            if (not expected and old is not None) or (expected and old != expected):
                return 0
            records[field] = replacement[0]
            return 1
        if old is None:
            return 1
        if old != expected:
            return 0
        records.pop(field)
        return 1

    def hscan_iter(self, key):
        return iter(list(self.values.get(key, {}).items()))

    def delete(self, key):
        self.values.pop(key, None)


class RedisFixture(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = 1000
        self.store.clock = lambda: self.now
        self.live = set()
        self.client = self.make_client()
        self.journal = Journal(
            self.client, namespace="wakfu:test:positions:" + uuid.uuid4().hex
        )
        self.addCleanup(self.client.delete, self.journal.namespace)
        self.buffer = RedisPositions(
            self.store,
            lease_active=lambda a, g, c: (a, g, c) in self.live,
            journal=self.journal,
        )

    def make_client(self):
        return MemoryRedis()

    def attach(self, name="Owner"):
        account = self.store.register(name, "local-password")["id"]
        generation = self.store.begin_session(account)
        char = self.store.create_character(account, name)
        char = self.store.select_character(account, generation, char["id"])
        self.live.add((account, generation, char["id"]))
        self.buffer.attach(account, generation, char)
        return account, generation, char

    def move(self, a, g, char):
        return self.buffer.move(
            a, g, char["id"], char, dict(x=char["x"] + 1, y=char["y"], z=char["z"])
        )


class RedisPositionTests(RedisFixture):
    def test_dirty_crash_recovery_and_committed_cleanup(self):
        a, g, char = self.attach()
        current = self.move(a, g, char)
        self.assertEqual(self.store.character(a, char["id"])["x"], char["x"])
        self.assertEqual(len(list(self.journal.records())), 1)
        fresh = self.reopen()
        fresh.clock = lambda: self.now
        report = Journal(self.client, namespace=self.journal.namespace).recover(fresh)
        self.assertEqual(
            report, dict(recovered=1, already_committed=0, stale=0, conflicts=[])
        )
        self.assertEqual(fresh.character(a, char["id"])["x"], current["x"])
        self.assertEqual(list(self.journal.records()), [])

    def test_batch_flush_removes_mirror_and_old_ack_cannot_delete_new_revision(self):
        a, g, char = self.attach()
        current = self.move(a, g, char)
        key = (a, g, char["id"])
        old = self.buffer.mirrors[key]
        current = self.move(a, g, current)
        new = self.buffer.mirrors[key]
        self.assertNotEqual(old, new)
        self.assertFalse(self.journal.ack(key, old))
        self.assertEqual(len(list(self.journal.records())), 1)
        self.assertEqual(self.buffer.flush(), 1)
        self.assertEqual(list(self.journal.records()), [])
        self.assertEqual(self.store.character(a, char["id"])["x"], current["x"])

    def test_replaced_generation_never_recovers_old_owner_position(self):
        a, g, char = self.attach()
        self.move(a, g, char)
        self.store.begin_session(a)
        report = self.journal.recover(self.store)
        self.assertEqual(report["stale"], 1)
        self.assertEqual(self.store.character(a, char["id"])["x"], char["x"])
        self.assertEqual(list(self.journal.records()), [])

    def test_expired_lease_is_discarded_without_applying(self):
        a, g, char = self.attach()
        self.move(a, g, char)
        self.now += 100000
        report = self.journal.recover(self.store)
        self.assertEqual(report["stale"], 1)
        self.assertEqual(self.store.character(a, char["id"])["x"], char["x"])

    def test_postgres_conflict_preserves_dirty_record_and_other_batch_rolls_back(self):
        a, g, char = self.attach()
        b, h, other = self.attach("Other")
        self.move(a, g, char)
        self.move(b, h, other)
        self.store.move(
            b, h, other["id"], other, dict(x=other["x"], y=other["y"] + 1, z=other["z"])
        )
        with self.assertRaisesRegex(ValueError, "CAS conflict"):
            self.buffer.flush()
        self.assertEqual(self.store.character(a, char["id"])["x"], char["x"])
        self.assertEqual(len(list(self.journal.records())), 2)
        self.assertTrue(all(e["dirty"] for e in self.buffer.entries.values()))
        # Recovery reports the conflicting position without overwriting it.
        report = self.journal.recover(self.store)
        self.assertEqual(report["recovered"], 1)
        self.assertEqual(report["conflicts"], [(b, h, other["id"])])
        self.assertEqual(self.store.character(b, other["id"])["y"], other["y"] + 1)

    def test_commit_before_redis_ack_crash_is_not_applied_twice(self):
        a, g, char = self.attach()
        current = self.move(a, g, char)
        Positions.flush(
            self.buffer
        )  # Simulate crash after PostgreSQL commit, before Redis ACK.
        report = self.journal.recover(self.store)
        self.assertEqual(report["already_committed"], 1)
        self.assertEqual(report["recovered"], 0)
        self.assertEqual(self.store.character(a, char["id"])["x"], current["x"])

    def test_movement_back_to_baseline_leaves_no_pending_loss(self):
        a, g, char = self.attach()
        current = self.move(a, g, char)
        self.buffer.move(
            a, g, char["id"], current, dict(x=char["x"], y=char["y"], z=char["z"])
        )
        self.assertEqual(self.buffer.flush(), 0)
        self.assertEqual(list(self.journal.records()), [])
        self.buffer.release(a, g, char["id"])

    def test_map_transition_barrier_avoids_recovery_cross_map(self):
        a, g, char = self.attach()
        current = self.move(a, g, char)
        self.buffer.flush()
        self.buffer.release(a, g, char["id"])
        moved = self.store.transition_map(
            a, g, char["id"], current, dict(map_id=527, instance_id=1, x=0, y=0, z=0)
        )
        self.buffer.attach(a, g, moved)
        self.move(a, g, moved)
        report = self.journal.recover(self.store)
        fresh = self.store.character(a, char["id"])
        self.assertEqual(
            (report["recovered"], fresh["map_id"], fresh["x"]), (1, 527, 1)
        )


class RedisFailureTests(RedisFixture):
    def test_redis_failure_before_mutation_keeps_memory_and_database_origin(self):
        a, g, char = self.attach()
        self.client.fail = True
        with self.assertRaises(PositionJournalError):
            self.move(a, g, char)
        self.assertEqual(
            self.buffer.entries[(a, g, char["id"])]["current"]["x"], char["x"]
        )
        self.assertFalse(self.buffer.entries[(a, g, char["id"])]["dirty"])
        self.assertEqual(self.store.character(a, char["id"])["x"], char["x"])
        self.client.fail = False

    def test_cleanup_failure_can_retry_and_recover_commit_without_loss(self):
        a, g, char = self.attach()
        current = self.move(a, g, char)
        original = self.journal.ack

        def fail(*args):
            raise PositionJournalError("Redis unavailable during ACK")

        self.journal.ack = fail
        with self.assertRaises(PositionJournalError):
            self.buffer.flush()
        self.assertFalse(self.buffer.entries[(a, g, char["id"])]["dirty"])
        self.assertEqual(self.store.character(a, char["id"])["x"], current["x"])
        self.assertTrue(self.buffer.pending_acks)
        self.journal.ack = original
        self.assertEqual(self.buffer.flush(), 0)
        self.assertFalse(self.buffer.pending_acks)
        self.assertEqual(list(self.journal.records()), [])

    def test_retry_after_postgres_commit_and_redis_ack_outage_does_not_apply_twice(
        self,
    ):
        a, g, char = self.attach()
        current = self.move(a, g, char)
        key = (a, g, char["id"])
        self.client.fail = True
        attempts, failures, renewals, waits = [], [], [], []

        def flush_one_barrier():
            attempts.append("flush")
            return self.buffer.flush(
                account_id=a, generation=g, character_id=char["id"]
            )

        def wait(seconds):
            waits.append(seconds)
            self.client.fail = False

        result = retry_step(
            flush_one_barrier,
            retry_errors=(PositionJournalUnavailable, OSError),
            failed=failures.append,
            renew=lambda: renewals.append("session heartbeat"),
            wait=wait,
        )

        self.assertEqual(result, 0)  # Retry only drains the already-committed ACK.
        self.assertEqual(attempts, ["flush", "flush"])
        self.assertEqual(len(failures), 1)
        self.assertEqual(renewals, ["session heartbeat"])
        self.assertEqual(waits, [1])
        self.assertEqual(self.store.character(a, char["id"])["x"], current["x"])
        self.assertFalse(self.buffer.entries[key]["dirty"])
        self.assertEqual(self.buffer.entries[key]["persisted"]["x"], current["x"])
        self.assertFalse(self.buffer.pending_acks)
        self.assertEqual(list(self.journal.records()), [])

    def test_cleanup_retry_does_not_retry_journal_conflict(self):
        failures, renewals, waits = [], [], []

        def conflict():
            raise PositionJournalError("Redis position revision conflict")

        with self.assertRaisesRegex(PositionJournalError, "revision conflict"):
            retry_step(
                conflict,
                retry_errors=(PositionJournalUnavailable, OSError),
                failed=failures.append,
                renew=lambda: renewals.append(True),
                wait=waits.append,
            )
        self.assertEqual((failures, renewals, waits), ([], [], []))

    def test_memory_default_uses_original_backend(self):
        buffer, report = create(self.store, lease_active=lambda *args: True, url="")
        self.assertIs(type(buffer), Positions)
        self.assertIsNone(report)


@unittest.skipUnless(
    os.environ.get("WAKFU_REDIS_TEST_URL"), "Isolated real Redis URL not configured"
)
class RealRedisPositionTests(RedisPositionTests):
    def make_client(self):
        import redis

        client = redis.Redis.from_url(
            os.environ["WAKFU_REDIS_TEST_URL"], socket_timeout=2
        )
        client.ping()
        return client
