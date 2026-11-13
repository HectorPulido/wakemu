import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server import rii_dialogue_gate


class RiiDialogueGateTests(unittest.TestCase):
    def test_only_exact_native_placement_exposes_actions(self):
        row = {
            "map_id": 1385,
            "instance_id": 0,
            "actor_id": -1706442046308322,
            "reference_id": 5461,
        }
        self.assertTrue(rii_dialogue_gate.qualified_placement(row))
        for change in (
            {"reference_id": 5460},
            {"actor_id": -1},
            {"instance_id": 1},
            {"map_id": 527},
        ):
            self.assertFalse(rii_dialogue_gate.qualified_placement({**row, **change}))

    def test_qualified_rii_spawn_advertises_both_initial_and_return_actions(self):
        from wakfu_server import npc_world

        row = {
            "map_id": 1388,
            "instance_id": 0,
            "actor_id": -1706442046308339,
            "reference_id": 5460,
            "x": 0,
            "y": -19,
            "z": 3,
            "direction": 0,
            "interaction_range": 4,
            "dialogue_root": 5755,
            "action_ids": [1390],
            "enabled": True,
        }
        native = {
            "nodes": [{"id": 5755, "criteria": "", "choices": []}],
            "speakers": [
                {
                    "ref": 5460,
                    "min_level": 1,
                    "max_level": 1,
                    "actions": [{"id": 1389}, {"id": 1390}],
                }
            ],
            "translations": {"es": {"content.7.5460": "Airyna"}},
        }
        with patch.object(npc_world, "validate_placements"):
            _, packet = npc_world.spawn(row, native)
            self.assertIn(struct.pack(">hhH", -1, -1, 0), packet)
            other = {**row, "actor_id": -1234}
            _, packet = npc_world.spawn(other, native)
            self.assertIn(struct.pack(">hhHii", -1, -1, 2, 1389, 1390), packet)

    def test_captured_actor_speaker_and_session_only(self):
        char = {"map_id": 1385, "instance_id": 0}
        huly = -1706442046308322
        self.assertTrue(
            rii_dialogue_gate.allow(13222, struct.pack(">qq", huly, 1243), char, None)
        )
        self.assertTrue(
            rii_dialogue_gate.allow(
                12535, struct.pack(">ibq", 5772, 1, 424), char, None
            )
        )
        self.assertTrue(
            rii_dialogue_gate.allow(
                12058,
                struct.pack(">ii", 5770, 13283),
                char,
                SimpleNamespace(speaker_id=huly),
            )
        )
        self.assertFalse(
            rii_dialogue_gate.allow(13222, struct.pack(">qq", -1, 1243), char, None)
        )
        self.assertFalse(
            rii_dialogue_gate.allow(
                12058,
                struct.pack(">ii", 5770, 13283),
                char,
                SimpleNamespace(speaker_id=-1),
            )
        )
        self.assertFalse(
            rii_dialogue_gate.allow(
                12058, b"bad", char, SimpleNamespace(speaker_id=huly)
            )
        )
        self.assertFalse(
            rii_dialogue_gate.allow(
                13222, struct.pack(">qq", huly, 1243), {**char, "instance_id": 5}, None
            )
        )
        self.assertFalse(
            rii_dialogue_gate.allow(
                13222, struct.pack(">qq", huly, 1243), {**char, "map_id": 527}, None
            )
        )
