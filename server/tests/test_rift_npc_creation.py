import unittest

from protocol_codec import Reader
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_multiplayer_wire import decode_added
from wakfu_server.rift_npc_creation import creation_packets


class RiftNpcCreationTests(unittest.TestCase):
    def setUp(self):
        self.monster = owned_instance(
            5525,
            1,
            -200,
            map_id=1134,
            x=-10,
            y=-2,
            z=-1,
        )

    def test_appearance_precedes_regular_enemy_admission_without_phase_reset(self):
        packets = creation_packets(self.monster, 99, obstacle_id=7, group_id=200)
        self.assertEqual([opcode for opcode, _ in packets], [12608, 13091])
        reader = Reader(packets[0][1])
        self.assertEqual(
            tuple(reader.number(t) for t in ("B", "B", "B", "q")), (0, 1, 1, -200)
        )
        admission = decode_added(packets[1][1])
        self.assertEqual(admission["actor_id"], -200)
        self.assertEqual(admission["fight_id"], 99)
        self.assertEqual(admission["actor_type"], 0)
        self.assertEqual(admission["team"], 1)
        self.assertIsNone(admission["controller"])
        self.assertEqual(admission["effects"], bytes(2))
        self.assertEqual(admission["stats"][0], 2)

    def test_unowned_modified_monster_cannot_be_published(self):
        altered = dict(self.monster, hp=self.monster["hp"] + 1)
        with self.assertRaises(ValueError):
            creation_packets(altered, 99, obstacle_id=7, group_id=200)

    def test_invalid_obstacle_fails_before_returning_packets(self):
        with self.assertRaises(ValueError):
            creation_packets(self.monster, 99, obstacle_id=127, group_id=200)
