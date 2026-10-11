import struct
import unittest

from wakfu_server.maps.npc_world import (
    begin,
    decode_interaction,
    nearby,
    spawn,
    validate_placements,
)


class NpcWorldTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            actor_id=-2251799813685248,
            reference_id=2986,
            map_id=1134,
            instance_id=0,
            x=-10,
            y=-8,
            z=-1,
            direction=3,
            interaction_range=4,
            dialogue_root=6274,
            action_ids=[515],
            enabled=True,
        )
        self.character = dict(map_id=1134, instance_id=0, x=-12, y=-8, z=-1)
        self.native = {
            "nodes": [
                {
                    "id": 6274,
                    "criteria": "",
                    "native_cmT": "npc2986",
                    "choices": [
                        {"id": 14075, "criteria": ""},
                        {"id": 14076, "criteria": "quest_flag"},
                    ],
                }
            ],
            "speakers": [
                {"ref": 2986, "min_level": 0, "max_level": 1, "actions": [{"id": 515}]}
            ],
            "translations": {"es": {"content.7.2986": "Arh Kayuh"}},
        }

    def test_visible_native_actor_packet_and_click_contract(self):
        opcode, body = spawn(self.row, self.native)
        self.assertEqual(opcode, 12608)
        self.assertEqual(body[:3], b"\x00\x01\x01")
        self.assertEqual(struct.unpack_from(">q", body, 3)[0], self.row["actor_id"])
        self.assertIn(b"Arh Kayuh", body)
        self.assertEqual(
            decode_interaction(struct.pack(">qq", self.row["actor_id"], 515)),
            (self.row["actor_id"], 515),
        )
        with self.assertRaises(ValueError):
            decode_interaction(bytes(15))

    def test_initial_dialogue_closes_without_quest_grants(self):
        session, packet = begin(
            lambda: self.character,
            lambda: [self.row],
            self.row["actor_id"],
            515,
            self.native,
        )
        self.assertEqual(packet[0], 12969)
        with self.assertRaises(ValueError):
            session.choose(6274, 14076)
        with self.assertRaises(ValueError):
            session.choose(6274, 99)
        self.assertIsNone(session.choose(6274, 14075))

    def test_rejects_wrong_instance_distance_or_action_and_rechecks_on_choice(self):
        for changes, action in [({"instance_id": 1}, 515), ({"x": 50}, 515), ({}, 999)]:
            self.character.update(changes)
            with self.assertRaises(ValueError):
                begin(
                    lambda: self.character,
                    lambda: [self.row],
                    self.row["actor_id"],
                    action,
                    self.native,
                )
            self.character.update(map_id=1134, instance_id=0, x=-12)
        session, _ = begin(
            lambda: self.character,
            lambda: [self.row],
            self.row["actor_id"],
            515,
            self.native,
        )
        self.character["instance_id"] = 1
        self.assertFalse(nearby(self.character, self.row))
        with self.assertRaises(ValueError):
            session.choose(6274, 14075)
        self.assertIsNone(session.node_id)

    def test_rejects_duplicate_identity_positions_and_foreign_native_roots(self):
        for other in [
            dict(self.row),
            dict(self.row, actor_id=self.row["actor_id"] - 1),
            dict(self.row, dialogue_root=99),
        ]:
            with self.assertRaises(ValueError):
                validate_placements([self.row, other], self.native)
        with self.assertRaises(ValueError):
            validate_placements([dict(self.row, action_ids=[999])], self.native)
