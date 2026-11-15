"""Redis walking journals scalar candidates without copying character graphs."""

import json
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.position_buffer import _KEYS
from spatial_fixture import seed_position
from wakfu_server.position_redis import (
    Journal,
    RedisPositions,
    PositionJournalError,
    PositionJournalUnavailable,
)


class CharacterGraph(dict):
    def __deepcopy__(self, memo):
        raise AssertionError("Position movement must not traverse character graphs")


class MemoryRedis:
    def __init__(self):
        self.rows = {}
        self.fail = False

    def eval(self, script, count, namespace, field, expected, *replacement):
        if self.fail:
            raise OSError("Redis unavailable")
        key = (namespace, field)
        old = self.rows.get(key)
        if replacement:
            if (not expected and old is not None) or (expected and old != expected):
                return 0
            self.rows[key] = replacement[0]
            return 1
        if old is None:
            return 1
        if old != expected:
            return 0
        del self.rows[key]
        return 1


class RedisMoveProjectionTests(unittest.TestCase):
    def setUp(self):
        self.key = (3, "selected-generation", 7)
        self.live = {self.key}
        self.client = MemoryRedis()
        self.journal = Journal(self.client, namespace="test:position-projection")
        self.store = SimpleNamespace(
            now=lambda: 1,
            connection=Mock(
                side_effect=AssertionError("Walking must not open PostgreSQL")
            ),
        )
        self.positions = RedisPositions(
            self.store,
            lease_active=lambda *key: key in self.live,
            journal=self.journal,
        )
        self.graph = CharacterGraph(
            inventory=[
                dict(uid=uid, quantity=1, slots=[1, 2, 3]) for uid in range(1000)
            ],
            achievements={str(uid): dict(progress=uid % 7) for uid in range(1000)},
        )
        self.character = dict(
            id=7,
            account_id=3,
            map_id=1134,
            instance_id=0,
            x=1,
            y=2,
            z=-1,
            direction=3,
            hp=100,
            max_hp=100,
            domain_graph=self.graph,
        )
        seed_position(self.positions, self.key, self.character)

    def move(self, start=None, end=None):
        return self.positions.move(
            *self.key,
            self.positions.entries[self.key]["current"] if start is None else start,
            dict(x=2, y=2, z=-1, direction=6) if end is None else end,
        )

    def test_success_shares_graph_but_isolates_scalar_candidate_and_journal(self):
        original = self.positions.entries[self.key]
        revision = self.positions.entry_state(self.key)["revision"]
        result = self.move()
        entry = self.positions.entries[self.key]
        self.assertGreater(self.positions.entry_state(self.key)["revision"], revision)
        self.assertIs(entry["current"]["domain_graph"], self.graph)
        self.assertIs(result["domain_graph"], self.graph)
        self.assertEqual(
            (
                original["current"]["x"],
                original["current"]["direction"],
                original["dirty"],
            ),
            (1, 3, False),
        )
        self.assertEqual(
            (result["x"], result["direction"], result["hp"], entry["dirty"]),
            (2, 6, 100, True),
        )
        self.assertIsNot(result, entry["current"])
        encoded = self.positions.mirrors[self.key]
        record = json.loads(encoded)
        self.assertEqual(
            set(record), {"version", "owner", "revision", "baseline", "current"}
        )
        self.assertEqual(set(record["current"]), set(_KEYS))
        self.assertEqual(record["baseline"], original["persisted"])
        self.assertEqual(record["current"], {key: result[key] for key in _KEYS})
        self.assertEqual(record["owner"], list(self.key))
        self.store.connection.assert_not_called()

    def assert_entry_unchanged(
        self, entry, current, persisted, dirty, mirrors, pending
    ):
        actual = self.positions.entries[self.key]
        self.assertEqual(actual["current"], current)
        self.assertEqual(actual["persisted"], persisted)
        self.assertEqual(actual["dirty"], dirty)
        self.assertEqual(actual["revision"], entry["revision"])
        self.assertEqual(self.positions.mirrors, mirrors)
        self.assertEqual(self.positions.pending_acks, pending)
        self.assertIs(actual["current"]["domain_graph"], self.graph)
        self.store.connection.assert_not_called()

    def test_redis_outage_and_cas_conflict_preserve_owned_dirty_state_and_revision(
        self,
    ):
        self.move()
        for failure in ("unavailable", "conflict"):
            with self.subTest(failure=failure):
                entry = self.positions.entries[self.key]
                current, persisted = entry["current"], entry["persisted"]
                before = {key: current[key] for key in _KEYS}
                mirrors, pending = dict(self.positions.mirrors), dict(
                    self.positions.pending_acks
                )
                self.client.fail = failure == "unavailable"
                if failure == "conflict":
                    (redis_key,) = self.client.rows
                    self.client.rows[redis_key] = "foreign-newer-revision"
                error = (
                    PositionJournalUnavailable
                    if failure == "unavailable"
                    else PositionJournalError
                )
                with self.assertRaises(error):
                    self.move(end=dict(x=3, y=2, z=-1, direction=5))
                self.assert_entry_unchanged(
                    entry, current, persisted, True, mirrors, pending
                )
                self.assertEqual({key: current[key] for key in _KEYS}, before)
                if failure == "conflict":
                    self.assertEqual(
                        self.client.rows[redis_key], "foreign-newer-revision"
                    )

    def test_validation_and_stale_lease_do_not_write_or_mutate_clean_entry(self):
        entry = self.positions.entries[self.key]
        current, persisted = entry["current"], entry["persisted"]
        invalid = (
            (dict(self.character, x=99), dict(x=2, y=2, z=-1)),
            (self.character, dict(x=True, y=2, z=-1)),
            (self.character, dict(x=2, y=2, z=32768)),
            (self.character, dict(x=2, y=2, z=-1, direction=True)),
            (self.character, dict(x=2, y=2, z=-1, direction=-1)),
            (self.character, dict(x=2, y=2, z=-1, direction=8)),
        )
        with patch.object(self.journal, "put", wraps=self.journal.put) as put:
            for start, end in invalid:
                with self.subTest(start=start["x"], end=end), self.assertRaises(
                    ValueError
                ):
                    self.move(start=start, end=end)
                self.assert_entry_unchanged(entry, current, persisted, False, {}, {})
                self.assertEqual({key: current[key] for key in _KEYS}, persisted)
            self.live.clear()
            with self.assertRaisesRegex(ValueError, "Stale"):
                self.move()
            put.assert_not_called()
        self.assert_entry_unchanged(entry, current, persisted, False, {}, {})

    def test_failed_move_preserves_pending_ack_after_return_to_baseline(self):
        self.move()
        self.move(
            end={key: self.character[key] for key in ("x", "y", "z", "direction")}
        )
        entry = self.positions.entries[self.key]
        current, persisted = entry["current"], entry["persisted"]
        mirrors, pending = dict(self.positions.mirrors), dict(
            self.positions.pending_acks
        )
        self.assertEqual(pending, mirrors)
        self.assertFalse(entry["dirty"])
        self.client.fail = True
        with self.assertRaises(PositionJournalUnavailable):
            self.move()
        self.assert_entry_unchanged(entry, current, persisted, False, mirrors, pending)
        self.assertEqual({key: current[key] for key in _KEYS}, persisted)

    def test_later_merge_refreshes_graph_without_restoring_old_position(self):
        self.move()
        refreshed = dict(self.character, hp=95, domain_graph=CharacterGraph(new=True))
        self.positions.merge(*self.key[:2], refreshed)
        result = self.move(end=dict(x=3, y=2, z=-1))
        self.assertEqual((result["x"], result["direction"], result["hp"]), (3, 6, 95))
        self.assertIs(result["domain_graph"], refreshed["domain_graph"])
        self.assertEqual(self.positions.entries[self.key]["persisted"]["x"], 1)

    def test_failed_stale_release_ack_keeps_native_owner_and_allows_retry(self):
        self.move()
        self.live.clear()
        before = self.positions.entry_state(self.key)
        mirrors = dict(self.positions.mirrors)
        pending = dict(self.positions.pending_acks)
        for failure in (False, PositionJournalUnavailable("Redis unavailable")):
            with self.subTest(failure=failure):
                effect = (
                    {"side_effect": failure}
                    if isinstance(failure, Exception)
                    else {"return_value": failure}
                )
                with patch.object(self.journal, "ack", **effect):
                    with self.assertRaises(PositionJournalError):
                        self.positions.release(*self.key, discard_stale=True)
                self.assertEqual(self.positions.entry_state(self.key), before)
                self.assertEqual(self.positions.mirrors, mirrors)
                self.assertEqual(self.positions.pending_acks, pending)
        self.positions.release(*self.key, discard_stale=True)
        self.assertNotIn(self.key, self.positions.entries)
        self.assertFalse(self.positions.mirrors)
        self.assertFalse(self.client.rows)

    def test_failed_transition_ack_cannot_reactivate_source_checkpoint(self):
        current = self.move()
        source = {key: current[key] for key in _KEYS}
        destination = dict(source, map_id=527, x=100)
        db = Mock()
        db.execute.return_value.fetchone.return_value = destination
        self.store.connection = Mock(side_effect=lambda: nullcontext(db))
        before = self.positions.entry_state(self.key)
        self.assertTrue(before["dirty"])
        mirrors = dict(self.positions.mirrors)
        self.assertFalse(self.positions.pending_acks)
        for failure in (False, PositionJournalUnavailable("Redis unavailable")):
            with self.subTest(failure=failure):
                effect = (
                    {"side_effect": failure}
                    if isinstance(failure, Exception)
                    else {"return_value": failure}
                )
                with patch.object(self.journal, "ack", **effect):
                    with self.assertRaises(PositionJournalError):
                        self.positions.release_committed_transition(
                            *self.key, source, destination
                        )
                after = self.positions.entry_state(self.key)
                for field in ("key", "current", "persisted", "revision"):
                    self.assertEqual(after[field], before[field])
                self.assertFalse(after["dirty"])
                self.assertFalse(self.positions.has_dirty())
                self.assertEqual(self.positions.mirrors, mirrors)
                self.assertEqual(self.positions.pending_acks, mirrors)
        self.positions.release_committed_transition(*self.key, source, destination)
        self.assertNotIn(self.key, self.positions.entries)
        self.assertFalse(self.positions.mirrors)
        self.assertFalse(self.positions.pending_acks)
        self.assertFalse(self.client.rows)
        self.assertEqual(db.execute.call_count, 3)
        self.assertTrue(
            all("SELECT" in call.args[0] for call in db.execute.call_args_list)
        )
