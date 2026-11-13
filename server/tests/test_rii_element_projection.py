"""Elemental lesson weakness reaches the real combat turn wire projection."""
import struct
import unittest

import test_combat_runtime_messages as runtime_fixture
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_wire import decode_actor_state


class ElementalProjectionTests(unittest.TestCase):
    def test_fight_start_republishes_initialized_sack_stats(self):
        fight, _ = runtime_fixture.RuntimeMessageTests().state()
        target = fight.actors[-200]
        target.effect_stats = {28: 0, 29: 32000, 30: 32000, 31: 32000}
        target.effect_minima = {stat: -2147483648 for stat in target.effect_stats}
        target.effect_maxima = {stat: 2147483647 for stat in target.effect_stats}
        fight.rii_element_lesson_contract = {
            "owner": 100,
            "target": -200,
            "hits": 0,
            "last_turn": None,
            "initialized": True,
            "profile_turn": 1,
            "profile_index": 0,
        }

        def serialize(actor, state):
            return (
                struct.pack(">iiii", *(actor.effect_stats[k] for k in (28, 29, 30, 31)))
                if actor.id == -200
                else b"owner"
            )

        runtime = RuntimeMessages(
            fight, runtime_stats_serializer=serialize, clock=lambda: 0.0
        )
        packets = runtime.combat_started(
            {100: (b"owner", b"\0\0"), -200: (b"old", b"\0\0")}
        )
        targets = [
            decode_actor_state(opcode, body)
            for opcode, body in packets
            if opcode == 12873
        ]
        target_packets = [row["state"] for row in targets if row["actor_id"] == -200]
        self.assertEqual(target_packets[0], b"old")
        self.assertIn(struct.pack(">iiii", 0, 32000, 32000, 32000), target_packets[1:])

    def test_each_owner_turn_emits_updated_target_characteristics(self):
        fight, _ = runtime_fixture.RuntimeMessageTests().state()
        target = fight.actors[-200]
        target.effect_stats = {28: 0, 29: 0, 30: 0, 31: 0}
        target.effect_minima = {stat: -2147483648 for stat in target.effect_stats}
        target.effect_maxima = {stat: 2147483647 for stat in target.effect_stats}
        fight.rii_element_lesson_contract = {
            "owner": 100,
            "target": -200,
            "hits": 0,
            "last_turn": None,
            "initialized": True,
        }

        def serialize(actor, state):
            return (
                struct.pack(">iiii", *(actor.effect_stats[k] for k in (28, 29, 30, 31)))
                if actor.id == -200
                else b"owner"
            )

        runtime = RuntimeMessages(
            fight, runtime_stats_serializer=serialize, clock=lambda: 0.0
        )
        packets = runtime.turn_started()
        targets = [
            decode_actor_state(opcode, body)
            for opcode, body in packets
            if opcode == 12873
        ]
        target_packets = [row for row in targets if row["actor_id"] == -200]
        self.assertEqual(len(target_packets), 1)
        self.assertEqual(
            target_packets[0]["state"], struct.pack(">iiii", 0, 32000, 32000, 32000)
        )
        self.assertEqual(fight.rii_element_lesson_contract["profile_turn"], 1)
        fight.turn_id = 3
        packets = runtime.turn_started()
        targets = [
            decode_actor_state(opcode, body)
            for opcode, body in packets
            if opcode == 12873
        ]
        target_packets = [row for row in targets if row["actor_id"] == -200]
        self.assertEqual(len(target_packets), 1)
        self.assertEqual(
            target_packets[0]["state"], struct.pack(">iiii", 32000, 0, 32000, 32000)
        )


if __name__ == "__main__":
    unittest.main()
