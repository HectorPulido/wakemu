"""Offline regressions for position-buffer lock scope during database stalls."""
import threading
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server.position_buffer import Positions
from wakfu_server.position_redis import Journal, RedisPositions


class _Result:
    rowcount = 1

    def fetchone(self):
        return {"character_id": 101}


class _Database:
    def __init__(self, execute_gate=None):
        self.execute_gate = execute_gate

    def execute(self, statement, params=()):
        if self.execute_gate is not None and statement.startswith("SET LOCAL"):
            self.execute_gate[0].set()
            if not self.execute_gate[1].wait(2):
                raise TimeoutError("test did not release blocked DB statement")
        return _Result()


class _Connection:
    def __init__(self, store):
        self.store = store
        self.db = _Database(store.execute_gate)

    def __enter__(self):
        self.store.active_connections += 1
        return self.db

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None and self.store.commit_error is not None:
                raise self.store.commit_error
        finally:
            self.store.active_connections -= 1
        return False


class _Store:
    def __init__(self, *, connection_gate=None, execute_gate=None, commit_error=None):
        self.connection_gate = connection_gate
        self.execute_gate = execute_gate
        self.commit_error = commit_error
        self.connection_timeouts = []
        self.active_connections = 0

    def connection(self, **options):
        self.connection_timeouts.append(options.get("timeout"))
        if self.connection_gate is not None:
            self.connection_gate[0].set()
            if not self.connection_gate[1].wait(2):
                raise TimeoutError("test did not release blocked connection checkout")
        return _Connection(self)

    @staticmethod
    def now():
        return 1


class _MemoryRedis:
    def __init__(self):
        self.values = {}

    def eval(self, script, count, namespace, field, expected, *replacement):
        records = self.values.setdefault(namespace, {})
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
        del records[field]
        return 1

    def hscan_iter(self, namespace):
        return iter(self.values.get(namespace, {}).items())


def _character(cid, x=0):
    return {
        "id": cid,
        "map_id": 7,
        "instance_id": 0,
        "x": x,
        "y": 0,
        "z": 0,
        "direction": 3,
    }


def _install(buffer, account, generation, character):
    key = (account, generation, character["id"])
    baseline = {
        k: character[k] for k in ("map_id", "instance_id", "x", "y", "z", "direction")
    }
    buffer.entries[key] = {
        "current": dict(character),
        "persisted": baseline,
        "dirty": False,
    }
    return key


class PositionBufferContentionTests(unittest.TestCase):
    def _move(self, buffer, account, generation, character):
        return buffer.move(
            account,
            generation,
            character["id"],
            character,
            {"x": character["x"] + 1, "y": character["y"], "z": character["z"]},
        )

    def _run_flush(self, buffer, errors):
        try:
            buffer.flush()
        except Exception as error:  # surfaced in the owning test thread
            errors.append(error)

    def _run_move(self, buffer, account, generation, character, finished, result):
        try:
            result.append(self._move(buffer, account, generation, character))
        except Exception as error:  # surfaced in the owning test thread
            result.append(error)
        finally:
            finished.set()

    def test_connection_checkout_wait_does_not_hold_buffer_or_account_locks(self):
        entered, release = threading.Event(), threading.Event()
        store = _Store(connection_gate=(entered, release))
        buffer = Positions(store, lease_active=lambda *key: True)
        first, second = _character(101), _character(202)
        _install(buffer, 1, "g1", first)
        _install(buffer, 2, "g2", second)
        # Exercise connection contention with actual work; clean flushes skip SQL.
        self._move(buffer, 1, "g1", first)
        errors = []
        worker = threading.Thread(
            target=self._run_flush, args=(buffer, errors), daemon=True
        )
        worker.start()
        self.assertTrue(entered.wait(1), "flush never reached connection checkout")
        moved, result = threading.Event(), []
        mover = threading.Thread(
            target=self._run_move,
            args=(buffer, 2, "g2", second, moved, result),
            daemon=True,
        )
        mover.start()
        try:
            self.assertTrue(moved.wait(0.5), "move waited behind connection checkout")
        finally:
            release.set()
            worker.join(2)
            mover.join(2)
        self.assertFalse(
            worker.is_alive(), "flush remained stuck after checkout release"
        )
        self.assertFalse(mover.is_alive(), "move remained stuck after checkout release")
        self.assertEqual([], errors)
        self.assertEqual(1, result[0]["x"])

    def test_blocked_flush_statement_does_not_block_existing_account_move(self):
        entered, release = threading.Event(), threading.Event()
        store = _Store(execute_gate=(entered, release))
        buffer = Positions(store, lease_active=lambda *key: True)
        first = _character(101)
        _install(buffer, 1, "g1", first)
        self._move(buffer, 1, "g1", first)
        newcomer = _character(202)
        _install(buffer, 2, "g2", newcomer)
        errors = []
        worker = threading.Thread(
            target=self._run_flush, args=(buffer, errors), daemon=True
        )
        worker.start()
        self.assertTrue(entered.wait(1), "flush never reached its blocked statement")
        moved, result = threading.Event(), []
        mover = threading.Thread(
            target=self._run_move,
            args=(buffer, 2, "g2", newcomer, moved, result),
            daemon=True,
        )
        mover.start()
        try:
            self.assertTrue(
                moved.wait(0.5), "account B move waited behind account A flush"
            )
        finally:
            release.set()
            worker.join(2)
            mover.join(2)
        self.assertFalse(
            worker.is_alive(), "flush remained stuck after statement release"
        )
        self.assertFalse(
            mover.is_alive(), "move remained stuck after statement release"
        )
        self.assertEqual([], errors)
        self.assertEqual(1, result[0]["x"])

    def test_commit_failure_keeps_dirty_entry_and_redis_mirror(self):
        store = _Store(commit_error=RuntimeError("simulated commit failure"))
        redis = _MemoryRedis()
        journal = Journal(redis, namespace="test:positions")
        buffer = RedisPositions(store, lease_active=lambda *key: True, journal=journal)
        character = _character(101)
        key = _install(buffer, 1, "g1", character)
        self._move(buffer, 1, "g1", character)
        mirror_before = buffer.mirrors[key]
        with self.assertRaisesRegex(RuntimeError, "simulated commit failure"):
            buffer.flush()
        self.assertTrue(buffer.entries[key]["dirty"])
        self.assertEqual(mirror_before, buffer.mirrors[key])
        records = list(journal.records())
        self.assertEqual(1, len(records))
        self.assertEqual(key, records[0][0])

    def test_busy_account_barrier_fails_fast_and_returns_database_connection(self):
        store = _Store()
        buffer = Positions(store, lease_active=lambda *key: True)
        character = _character(101)
        _install(buffer, 1, "g1", character)
        self._move(buffer, 1, "g1", character)
        held, release = threading.Event(), threading.Event()

        def own_account():
            with buffer.account_barrier(1):
                held.set()
                release.wait(2)

        owner = threading.Thread(target=own_account, daemon=True)
        owner.start()
        self.assertTrue(held.wait(1), "account owner did not acquire its barrier")
        try:
            with self.assertRaisesRegex(TimeoutError, "owner is busy"):
                buffer.flush(account_id=1)
            self.assertEqual([0.25], store.connection_timeouts)
            self.assertEqual(0, store.active_connections)
        finally:
            release.set()
            owner.join(2)
        self.assertFalse(owner.is_alive())

    def test_scoped_flush_is_reentrant_under_its_account_barrier(self):
        store = _Store()
        buffer = Positions(store, lease_active=lambda *key: True)
        character = _character(101)
        _install(buffer, 1, "g1", character)
        self._move(buffer, 1, "g1", character)
        with buffer.account_barrier(1):
            self.assertEqual(1, buffer.flush(account_id=1))
        self.assertFalse(buffer.entries[(1, "g1", 101)]["dirty"])
        self.assertEqual(0, store.active_connections)


class PositionBufferPostgresContentionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.live = set()
        self.buffer = Positions(
            self.store, lease_active=lambda a, g, c: (a, g, c) in self.live
        )

    def _attach(self, prefix):
        suffix = "".join(chr(97 + int(value, 16)) for value in uuid.uuid4().hex[:8])
        name = prefix + suffix
        account = self.store.register(name, "local-password")["id"]
        generation = self.store.begin_session(account)
        character = self.store.create_character(account, name)
        character = self.store.select_character(account, generation, character["id"])
        self.live.add((account, generation, character["id"]))
        self.buffer.attach(account, generation, character)
        return account, generation, character

    def _move(self, account, generation, character):
        return self.buffer.move(
            account,
            generation,
            character["id"],
            character,
            {"x": character["x"] + 1, "y": character["y"], "z": character["z"]},
        )

    def test_row_lock_timeout_preserves_account_a_and_allows_account_b_progress(self):
        from psycopg.errors import LockNotAvailable

        account_a, generation_a, character_a = self._attach("LockA")
        account_b, generation_b, character_b = self._attach("LockB")
        self._move(account_a, generation_a, character_a)
        current_b = self._move(account_b, generation_b, character_b)
        errors = []
        finished = threading.Event()

        def flush_all():
            try:
                self.buffer.flush()
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()

        with self.store.connection() as locker:
            locker.execute(
                "SELECT account_id FROM sessions WHERE account_id=%s AND generation=%s FOR UPDATE",
                (account_a, generation_a),
            )
            worker = threading.Thread(target=flush_all, daemon=True)
            worker.start()
            self.assertFalse(
                finished.wait(0.05),
                "flush did not remain blocked on account A row lock",
            )
            moved_b_event, moved_b_result = threading.Event(), []

            def move_b():
                try:
                    moved_b_result.append(
                        self._move(account_b, generation_b, current_b)
                    )
                except Exception as error:
                    moved_b_result.append(error)
                finally:
                    moved_b_event.set()

            mover = threading.Thread(target=move_b, daemon=True)
            mover.start()
            self.assertTrue(
                moved_b_event.wait(0.1),
                "account B move waited behind account A row lock",
            )
            self.assertEqual(character_b["x"] + 2, moved_b_result[0]["x"])
            self.assertTrue(
                finished.wait(2), "flush exceeded its configured row-lock timeout"
            )

        worker.join(2)
        self.assertFalse(
            worker.is_alive(), "flush did not return after row lock release"
        )
        self.assertEqual(1, len(errors))
        self.assertIsInstance(errors[0], LockNotAvailable)
        key_a = (account_a, generation_a, character_a["id"])
        self.assertTrue(self.buffer.entries[key_a]["dirty"])
        self.assertEqual(1, self.buffer.flush(account_id=account_a))
        stored_a = self.store.character(account_a, character_a["id"])
        self.assertEqual(character_a["x"] + 1, stored_a["x"])
        stored_b = self.store.character(account_b, character_b["id"])
        self.assertEqual(character_b["x"] + 2, stored_b["x"])


if __name__ == "__main__":
    unittest.main()
