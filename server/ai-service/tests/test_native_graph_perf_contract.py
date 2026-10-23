"""Complete snapshot contracts for realistic aliased native authority graphs."""
from collections import deque
from dataclasses import dataclass
import hashlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.context.native_context import NativeGraph, encode, encode_bytes
from wakfu_ai.context.native_fingerprint import _CompletePickler, fingerprint
from wakfu_ai.native.native_deadline import bounded
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet


@dataclass(slots=True)
class EffectReceipt:
    uid: int
    reference: int
    owner: int
    parameters: tuple


def authority_graph():
    terrain = ImmutableTerrainSet((x, y, 0) for x in range(12) for y in range(12))
    actors = [
        SimpleNamespace(
            id=identity,
            hp=3000,
            characteristics={str(key): key * 7 for key in range(30)},
            inventory=[
                {
                    "uid": identity * 100 + slot,
                    "reference": slot,
                    "effects": tuple([slot, 100, slot + 1]),
                }
                for slot in range(8)
            ],
            ledger=deque(
                (
                    EffectReceipt(
                        identity * 100 + entry, 100 + entry, identity, tuple([4, 3, 2])
                    )
                    for entry in range(8)
                ),
                maxlen=24,
            ),
        )
        for identity in range(6)
    ]
    fight = SimpleNamespace(terrain=terrain, actors=actors, events=list(actors) * 3)
    fight.self = fight
    for actor in actors:
        actor.fight = fight
        actor.walkable = terrain
    return fight


class NativeGraphPerfContractTests(unittest.TestCase):
    def test_complete_bytes_match_reference_with_terrain_inventory_and_ledger(self):
        fight = authority_graph()
        expected = json.dumps(
            encode(fight), separators=(",", ":"), allow_nan=False
        ).encode()
        # Exercise a warm terrain cache as well as the first encoding.
        self.assertEqual(encode_bytes(fight), expected)
        self.assertEqual(encode_bytes(fight), expected)
        graph = NativeGraph(expected)
        root = graph.data["root"]
        self.assertEqual(graph.field(root, "self"), root)
        terrain = graph.field(root, "terrain")
        actors = graph.resolve(graph.field(root, "actors"))["items"]
        events = graph.resolve(graph.field(root, "events"))["items"]
        for index, actor in enumerate(actors):
            self.assertEqual(graph.field(actor, "fight"), root)
            self.assertEqual(graph.field(actor, "walkable"), terrain)
            self.assertEqual(events[index], actor)
            self.assertEqual(events[index + len(actors)], actor)
        ledger = graph.resolve(graph.field(actors[0], "ledger"))
        self.assertEqual(ledger["maxlen"], 24)
        receipt = ledger["items"][0]
        self.assertEqual(graph.plain(graph.field(receipt, "parameters")), (4, 3, 2))

    def test_fingerprint_matches_complete_stream_and_observes_mutable_state(self):
        fight = authority_graph()
        stream = io.BytesIO()
        _CompletePickler(stream, protocol=5).dump(fight)
        original = fingerprint(fight)
        self.assertEqual(original, hashlib.sha256(stream.getbuffer()).hexdigest())
        before = encode_bytes(fight)
        fight.actors[0].ledger[0].parameters = (4, 3, 9)
        self.assertNotEqual(original, fingerprint(fight))
        self.assertNotEqual(before, encode_bytes(fight))
        original = fingerprint(fight)
        fight.events[0] = SimpleNamespace(**vars(fight.actors[0]))
        self.assertNotEqual(original, fingerprint(fight))

    def test_primitive_kinds_remain_distinct_and_zero_reference_survives(self):
        value = [None, False, True, 0, 1, -3, 2**150, "", "á", 0.0, -0.0]
        value.append(value)
        graph = NativeGraph(encode_bytes(value))
        items = graph.root["items"]
        self.assertEqual(items[-1], graph.data["root"])
        for reference, original in zip(items, value):
            if original is value:
                break
            actual = graph.plain(reference)
            self.assertIs(type(actual), type(original))
            self.assertEqual(actual, original)

    def test_heavily_aliased_scalar_traversal_keeps_deadline_checks(self):
        shared = [7]
        value = [shared] * 2000
        clock = [0.0]
        calls = [0]
        from wakfu_ai.native.native_deadline import check as deadline_check

        def expire_during_traversal():
            calls[0] += 1
            if calls[0] >= 4:
                clock[0] = 2.0
            deadline_check()

        with bounded(1.0, clock=lambda: clock[0]), patch(
            "wakfu_ai.context.native_context.check", side_effect=expire_during_traversal
        ), self.assertRaisesRegex(TimeoutError, "Native AI turn deadline"):
            encode_bytes(value)
        self.assertEqual(calls[0], 4)


if __name__ == "__main__":
    unittest.main()
