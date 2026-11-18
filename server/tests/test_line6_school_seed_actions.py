"""Synthetic protocol contract for the bounded existing-peer School seed helper."""
from contextlib import contextmanager
import struct
import threading
import unittest
from unittest.mock import patch

from tools import line6_school_seed_actions as actions


class _Cursor:
    def __init__(self, *, rows=(), row=None):
        self.rows = rows
        self.row = row

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class _Store:
    @contextmanager
    def connection(self):
        yield self

    def execute(self, query, args=()):
        if "FROM combat_groups" in query:
            return _Cursor(
                rows=[
                    dict(
                        map_id=1018,
                        instance_id=88,
                        members=[dict(id=-88, ref=self.seed_ref)],
                    )
                ]
            )
        if "FROM character_achievement_progress" in query:
            return _Cursor(row=dict(state={"objectives": [5670]}))
        raise AssertionError(query)


class _Peer:
    def __init__(self, *, character_id=7):
        self.records = []
        self.observation_lock = threading.Lock()
        self.character_id = character_id

    def mark(self):
        return len(self.records)

    def send(self, opcode, body):
        self.records.append((opcode, body))
        if opcode == 12925:
            reply = (
                struct.pack(">q", self.character_id)
                + b"\x00\x00\x11"
                + struct.pack(">i", -1)
            )
            self.records.append((13046, reply))

    def matching(self, opcode, start, predicate, *, timeout):
        self.matched = (opcode, start, timeout)
        self.asserted_match = any(
            seen_opcode == opcode and predicate(body)
            for seen_opcode, body in self.records[start:]
        )
        if not self.asserted_match:
            raise AssertionError("Expected normal native return response")


class _Probe:
    def __init__(self, *, seed_ref=3907, initial_map=1018, final_events=()):
        self.character = {"id": 7}
        self.account = {"id": 2}
        self.store = _Store()
        self.store.seed_ref = seed_ref
        self.peer = _Peer()
        self._initial = dict(map_id=initial_map, instance_id=88)
        self._returned = dict(map_id=1018, instance_id=0, x=-4, y=8, z=0, breed=1)
        self._current_calls = 0
        self.receipt = {}
        self.notes = []
        self.final_events = list(final_events)

    def current(self):
        self._current_calls += 1
        return self._initial if self._current_calls == 1 else self._returned

    @staticmethod
    def configuration():
        return {"topology": {"owned_story_controller": {"id": "huppermage-seed-1018"}}}

    def ack_loads(self, mark):
        self.acked = mark

    def note(self, message, **values):
        self.notes.append((message, values))


class _Runner:
    fight_id = 501

    def __init__(self, probe):
        self.probe = probe
        self.actions = []
        self.casts = []
        self.snapshots = [
            dict(
                phase="active",
                actors={
                    "7": dict(id=7, team=0, hp=100, mp=1, position=[0, 0, 0]),
                    "-88": dict(id=-88, team=1, hp=1, mp=0, position=[2, 0, 0]),
                },
                edges=[],
            ),
            dict(
                phase="active",
                actors={
                    "7": dict(id=7, team=0, hp=100, mp=1, position=[1, 0, 0]),
                    "-88": dict(id=-88, team=1, hp=1, mp=0, position=[2, 0, 0]),
                },
                edges=[],
            ),
        ]
        self.terminal = dict(
            phase="finished",
            winner=0,
            actors={"7": dict(id=7, team=0, hp=100, mp=0, position=[1, 0, 0])},
            events=probe.final_events,
        )
        self.snapshots.append(self.terminal)

    def ready_for_input(self):
        return self.snapshots.pop(0)

    def action(self, action_id, body, *, label):
        self.actions.append((action_id, body, label))

    def cast(self, uid, target, *, class_spell):
        self.casts.append((uid, target, class_spell))

    def checkpoint(self):
        return self.terminal


class Line6SchoolSeedActionsTests(unittest.TestCase):
    def test_bounded_existing_peer_seed_collection_contract(self):
        probe = _Probe()
        runner = _Runner(probe)
        with patch("tools.line3_fields_combat.path_to_cast", return_value=[(1, 0, 0)]):
            receipt = actions.collect_seed(probe, runner)
        self.assertEqual(
            [row["kind"] for row in receipt["operations"]],
            ["paid_native_movement", "native_collection"],
        )
        self.assertEqual(runner.actions[0][0], 12161)
        self.assertEqual(
            runner.actions[0][1],
            struct.pack(">q", 7) + struct.pack(">iih", 1, 0, 0),
        )
        self.assertEqual(runner.casts, [(5599, (2, 0, 0), False)])
        self.assertEqual(receipt["objective_id"], 5670)
        self.assertEqual(
            receipt["qualification"].split(";")[0],
            "Actual native5599 action and normal finished return",
        )
        self.assertTrue(probe.peer.asserted_match)
        self.assertEqual(probe.acked, 0)

        # Existing-peer identity checks reject wrong scope and a foreign seed.
        for rejected in (_Probe(initial_map=1019), _Probe(seed_ref=3908)):
            with self.subTest(
                seed_ref=rejected.store.seed_ref, map=rejected._initial["map_id"]
            ), self.assertRaises(ValueError):
                actions._original_seed(rejected, 501)

        # The helper never accepts a command-marked outcome as native collection.
        admin = _Probe(final_events=[dict(kind="administrative_outcome")])
        admin_runner = _Runner(admin)
        with patch(
            "tools.line3_fields_combat.path_to_cast", return_value=[(1, 0, 0)]
        ), self.assertRaisesRegex(AssertionError, "Administrative outcomes"):
            actions.collect_seed(admin, admin_runner)

        with self.assertRaisesRegex(ValueError, "between1 and128"):
            actions.collect_seed(_Probe(), _Runner(_Probe()), max_operations=129)


if __name__ == "__main__":
    unittest.main()
