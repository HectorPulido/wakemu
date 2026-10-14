"""Bounded checkpoint scheduling, fairness and SQL-only policy regressions."""
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock

from wakfu_server.position_buffer import Positions
from wakfu_server.position_checkpoint_policy import validate_policy
from wakfu_server.position_checkpoint_worker import PositionCheckpointWorker


POLICY = dict(interval_seconds=2, max_accounts=2, max_seconds=0.1)


class PositionCheckpointTests(unittest.TestCase):
    def buffer(self, count=3):
        store = SimpleNamespace(
            connection=Mock(side_effect=AssertionError("Unexpected SQL"))
        )
        positions = Positions(store, lease_active=lambda *args: True)
        positions.entries = {
            (i, "generation", i): {"dirty": True} for i in range(1, count + 1)
        }
        return positions

    def test_clean_accounts_and_clean_scoped_flush_do_not_borrow_connection(self):
        positions = self.buffer()
        for entry in positions.entries.values():
            entry["dirty"] = False
        self.assertEqual(positions.flush(account_id=1), 0)
        self.assertEqual(
            positions.flush_background(max_accounts=2, max_seconds=0.1)["attempted"], 0
        )
        positions.store.connection.assert_not_called()

    def test_failing_dirty_accounts_cannot_starve_later_accounts(self):
        positions = self.buffer()
        visited = []

        def fail(**scope):
            visited.append(scope["account_id"])
            raise TimeoutError("busy")

        positions._flush_one = fail
        first = positions.flush_background(max_accounts=2, max_seconds=0.1)
        second = positions.flush_background(max_accounts=2, max_seconds=0.1)
        self.assertEqual(visited, [1, 2, 3, 1])
        self.assertEqual(first["failures"], 2)
        self.assertEqual(second["failures"], 2)
        self.assertTrue(all(e["dirty"] for e in positions.entries.values()))

    def test_elapsed_budget_finishes_account_without_starting_another(self):
        positions = self.buffer()
        now = [0.0]

        def flush(**scope):
            now[0] += 0.15
            return 1

        positions._flush_one = flush
        result = positions.flush_background(
            max_accounts=3, max_seconds=0.1, clock=lambda: now[0]
        )
        self.assertEqual((result["attempted"], result["characters"]), (1, 1))

    def test_concurrent_background_pass_never_waits_for_other_pass(self):
        positions = self.buffer()
        with positions.background_lock:
            result = positions.flush_background(max_accounts=2, max_seconds=0.1)
        self.assertTrue(result["busy"])
        self.assertEqual(result["attempted"], 0)

    def test_sql_policy_missing_is_startup_error(self):
        def missing(_store):
            raise ValueError("Missing SQL policy")

        with self.assertRaisesRegex(ValueError, "Missing SQL"):
            PositionCheckpointWorker(
                None, self.buffer(), threading.Event(), record=Mock(), loader=missing
            )

    def test_refresh_is_bounded_and_preserves_last_valid_policy(self):
        now = [0.0]
        loader = Mock(
            side_effect=[dict(POLICY), TimeoutError(), dict(POLICY, interval_seconds=3)]
        )
        positions = self.buffer(0)
        log = Mock()
        worker = PositionCheckpointWorker(
            None,
            positions,
            threading.Event(),
            record=log,
            loader=loader,
            clock=lambda: now[0],
        )
        for _ in range(10):
            worker.run_once()
        self.assertEqual(loader.call_count, 1)
        now[0] = 60
        worker.run_once()
        self.assertEqual(worker.policy["interval_seconds"], 2)
        worker.run_once()
        self.assertEqual(loader.call_count, 2)
        log.assert_called_once_with(
            event="position_checkpoint_policy_refresh_failed", error_type="TimeoutError"
        )
        now[0] = 120
        worker.run_once()
        self.assertEqual(worker.policy["interval_seconds"], 3)

    def test_invalid_policy_cannot_disable_or_unbound_checkpointing(self):
        for field, values in (
            ("interval_seconds", [0, True, float("nan"), 31]),
            ("max_accounts", [0, True, 4097]),
            ("max_seconds", [0, float("inf"), 11]),
        ):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(
                    ValueError
                ):
                    validate_policy(dict(POLICY, **{field: value}))


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.fail = False

    def eval(self, script, count, namespace, field, expected, *replacement):
        if self.fail:
            raise OSError("Redis unavailable")
        rows = self.values.setdefault(namespace, {})
        old = rows.get(field)
        if replacement:
            if (not expected and old is not None) or (expected and old != expected):
                return 0
            rows[field] = replacement[0]
            return 1
        if old is None:
            return 1
        if old != expected:
            return 0
        del rows[field]
        return 1

    def hscan_iter(self, namespace):
        return iter(list(self.values.get(namespace, {}).items()))


class RedisBackgroundCheckpointTests(unittest.TestCase):
    def test_post_commit_ack_failure_is_retried_without_new_sql(self):
        from contextlib import nullcontext
        from unittest.mock import patch
        from wakfu_server.position_redis import Journal, RedisPositions

        client = MemoryRedis()
        journal = Journal(client)
        store = SimpleNamespace(connection=Mock(return_value=nullcontext(Mock())))
        positions = RedisPositions(
            store, lease_active=lambda *args: True, journal=journal
        )
        key = (1, "generation", 101)
        old = dict(map_id=527, instance_id=0, x=1, y=2, z=0, direction=0)
        positions.entries[key] = dict(current=dict(old, x=2), persisted=old, dirty=True)
        positions.mirrors[key] = journal.put(key, positions.entries[key])

        def commit_then_redis_failure(*args, **kwargs):
            positions.entries[key]["dirty"] = False
            client.fail = True
            return 1

        with patch.object(Positions, "_flush", side_effect=commit_then_redis_failure):
            first = positions.flush_background(max_accounts=2, max_seconds=0.1)
        self.assertEqual(first["failures"], 1)
        self.assertIn(key, positions.pending_acks)
        self.assertFalse(positions.entries[key]["dirty"])
        self.assertEqual(store.connection.call_count, 1)
        client.fail = False
        second = positions.flush_background(max_accounts=2, max_seconds=0.1)
        self.assertEqual((second["attempted"], second["failures"]), (1, 0))
        self.assertEqual(store.connection.call_count, 1)
        self.assertFalse(positions.pending_acks)
        self.assertFalse(positions.mirrors)
        self.assertFalse(list(journal.records()))

    def test_clean_orphan_mirror_is_recovered_without_sql(self):
        from wakfu_server.position_redis import Journal, RedisPositions

        store = SimpleNamespace(
            connection=Mock(side_effect=AssertionError("Clean ACK borrowed SQL"))
        )
        journal = Journal(MemoryRedis())
        positions = RedisPositions(
            store, lease_active=lambda *args: True, journal=journal
        )
        key = (7, "generation", 101)
        old = dict(map_id=527, instance_id=0, x=1, y=2, z=0, direction=0)
        encoded = journal.put(key, dict(current=old, persisted=old, dirty=False))
        positions.mirrors[key] = encoded
        positions.pending_acks[key] = encoded
        result = positions.flush_background(max_accounts=2, max_seconds=0.1)
        self.assertEqual(result["attempted"], 1)
        self.assertEqual(result["failures"], 0)
        store.connection.assert_not_called()
        self.assertFalse(list(journal.records()))

    def test_clean_scoped_flush_does_not_ack_other_dirty_character_journal(self):
        from wakfu_server.position_redis import Journal, RedisPositions

        store = SimpleNamespace(
            connection=Mock(side_effect=AssertionError("Clean scope borrowed SQL"))
        )
        journal = Journal(MemoryRedis())
        positions = RedisPositions(
            store, lease_active=lambda *args: True, journal=journal
        )
        clean_key, dirty_key = (7, "generation", 101), (7, "generation", 102)
        old = dict(map_id=527, instance_id=0, x=1, y=2, z=0, direction=0)
        positions.entries[clean_key] = dict(current=old, persisted=old, dirty=False)
        positions.entries[dirty_key] = dict(
            current=dict(old, x=2), persisted=old, dirty=True
        )
        encoded = journal.put(dirty_key, positions.entries[dirty_key])
        positions.mirrors[dirty_key] = encoded
        self.assertEqual(
            positions.flush(account_id=7, generation="generation", character_id=101), 0
        )
        self.assertEqual(positions.mirrors[dirty_key], encoded)
        self.assertNotIn(dirty_key, positions.pending_acks)
        self.assertEqual(len(list(journal.records())), 1)
        self.assertTrue(positions.entries[dirty_key]["dirty"])
        store.connection.assert_not_called()
