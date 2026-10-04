import unittest
from copy import deepcopy
from wakfu_server.combat_state import Actor, Fight


class EffectUIDTests(unittest.TestCase):
    def setUp(self):
        pc = Actor(1, 0, (0, 0, 0), 100, 6, 3, 20, 1, 1, True)
        npc = Actor(2, 1, (1, 0, 0), 100, 6, 3, 10, 1)
        self.fight = Fight(
            1,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )

    def test_preview_rollback_does_not_consume_ids_and_commit_does(self):
        self.fight.native_effect_uid_next = 100
        preview = deepcopy(self.fight)
        self.assertEqual(preview.allocate_effect_uid(), 100)
        self.assertEqual(self.fight.native_effect_uid_next, 100)
        self.fight = preview
        self.assertEqual(self.fight.allocate_effect_uid(), 101)

    def test_collision_rejects_without_advancing(self):
        self.fight.native_effect_uid_next = 100
        self.fight.owned_stat_effects[100] = {}
        with self.assertRaisesRegex(ValueError, "collides"):
            self.fight.allocate_effect_uid()
        self.assertEqual(self.fight.native_effect_uid_next, 100)

    def test_unknown_and_exhausted_sequences_are_rejected(self):
        for value in (None, True, 0, -1, (1 << 63) - 1):
            self.fight.native_effect_uid_next = value
            with self.assertRaises(ValueError):
                self.fight.allocate_effect_uid()
            self.assertEqual(self.fight.native_effect_uid_next, value)
