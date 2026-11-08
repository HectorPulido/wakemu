"""Checkpoint serialization preserves SQL adapter identity and validation fences."""
from contextlib import nullcontext
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from psycopg.types.json import Jsonb, JsonbDumper

from wakfu_server import fight_checkpoint_store as candidate


class SingleEncodingTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.store = SimpleNamespace(
            connection=Mock(return_value=nullcontext(self.db)), now=lambda: 0
        )
        self.checkpoints = candidate.Checkpoints(self.store)
        self.checkpoints._session = Mock(return_value=dict(character_id=6))
        self.checkpoints._participant = Mock()
        self.checkpoints._validate_roster = Mock()
        self.fight = SimpleNamespace(
            id=7, actors={6: SimpleNamespace(controlled=True, owner_id=9)}
        )
        self.saved = []
        self.dumper = JsonbDumper(Jsonb)

        def query(sql, params):
            if sql.startswith("SELECT id,status FROM combat_fights"):
                return Mock(fetchone=lambda: dict(id=7, status="active"))
            if sql.startswith("SELECT account_id,generation,revision,status,"):
                return Mock(fetchone=lambda: None)
            if sql.startswith("INSERT INTO fight_checkpoints"):
                wrapper = params[5]
                self.saved.append((wrapper, self.dumper.dump(wrapper)))
                return Mock()
            raise AssertionError(sql)

        self.db.execute.side_effect = query
        # Post-write consumers receive the fight, never the detached state.
        self.enterContext(
            patch.dict(
                "sys.modules",
                {
                    "wakfu_server.combat_captured_roster_checkpoint": SimpleNamespace(
                        persist_captured_roster_updates=Mock()
                    ),
                    "wakfu_server.combat_consumable_handoff": SimpleNamespace(
                        persist=Mock(return_value=()), mark_committed=Mock()
                    ),
                    "wakfu_server.rift_runtime": SimpleNamespace(
                        mark_progress_committed=Mock()
                    ),
                },
            )
        )

    def test_encode_once_preserves_wrapper_identity_bytes_and_independent_saves(self):
        states = [
            dict(phase="active", nested=[1, "é", {"value": True}]),
            dict(phase="active", nested=[2, "other", {"value": False}]),
        ]
        expected = [json.dumps(state, allow_nan=False).encode() for state in states]
        original = json.dumps
        with patch.object(candidate.json, "dumps", wraps=original) as dumps:
            for state in states:
                self.assertEqual(
                    1,
                    self.checkpoints.save_prepared(9, "generation", self.fight, state),
                )
            self.assertEqual(2, dumps.call_count)
        for state, raw, (wrapper, stored) in zip(states, expected, self.saved):
            self.assertIs(wrapper.obj, state)
            self.assertEqual(raw, stored)
            self.assertEqual(raw, self.dumper.dump(wrapper))
        self.assertNotEqual(self.saved[0][1], self.saved[1][1])

    def test_invalid_nan_and_nonserializable_state_fail_before_connection(self):
        for state, exception in (
            (dict(value=float("nan")), ValueError),
            (dict(value=object()), TypeError),
        ):
            with self.subTest(exception=exception), self.assertRaises(exception):
                self.checkpoints.save_prepared(9, "generation", self.fight, state)
        self.store.connection.assert_not_called()
        self.db.execute.assert_not_called()

    def test_private_snapshot_does_not_follow_later_live_nested_mutation(self):
        self.fight.details = dict(values=[1, dict(value=2)])
        state = candidate.snapshot(self.fight)
        before = json.dumps(state)
        self.fight.details["values"][1]["value"] = 99
        self.fight.actors[6].owner_id = 10
        self.assertEqual(before, json.dumps(state))


if __name__ == "__main__":
    unittest.main()
