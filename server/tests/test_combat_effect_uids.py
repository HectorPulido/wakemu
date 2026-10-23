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

    def test_running_counter_crosses_active_and_retired_area_pv_ids(self):
        self.fight.native_effect_uid_next = 8983
        self.fight.native_effect_areas[8984] = dict(uid=8984)
        self.fight.native_retired_area_managers[8990] = dict(uid=8990, reference=2067)
        preview = deepcopy(self.fight)
        self.assertEqual(
            [preview.allocate_effect_uid() for _ in range(8)], list(range(8983, 8991))
        )
        self.assertEqual(preview.native_effect_uid_next, 8991)
        self.assertEqual(self.fight.native_effect_uid_next, 8983)
        self.assertEqual(preview.native_effect_areas, self.fight.native_effect_areas)
        self.assertEqual(
            preview.native_retired_area_managers,
            self.fight.native_retired_area_managers,
        )
        self.fight = preview
        self.assertEqual(self.fight.allocate_effect_uid(), 8991)

    def test_real_owned_runner_collisions_remain_atomic_in_every_registry(self):
        for registry in (
            "state_wire_payloads",
            "owned_stat_effects",
            "native_owned_group_effects",
            "native_owned_area_effects",
            "native_owned_spatial_effects",
        ):
            with self.subTest(registry=registry):
                fight = deepcopy(self.fight)
                fight.native_effect_uid_next = 8990
                getattr(fight, registry)[8990] = {}
                with self.assertRaisesRegex(
                    ValueError, "collides with an owned effect"
                ):
                    fight.allocate_effect_uid()
                self.assertEqual(fight.native_effect_uid_next, 8990)
                self.assertIn(8990, getattr(fight, registry))
