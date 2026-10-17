"""Attested fdt retirement remains observable without fabricating a fdy row."""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_state import Actor
from wakfu_server.combat_effective_control import effective_affiliation
from wakfu_server.combat_controller_registry import current_native_team
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    unregister_global_fighter,
)


class RetiredAffiliationTests(unittest.TestCase):
    def fight(self):
        actors = [
            Actor(31, 0, (0, 0, 0), 100, 6, 4, 1, 200),
            Actor(-7, 1, (2, 0, 0), 100, 6, 6, 1, 200),
        ]
        fight = SimpleNamespace(
            actors={actor.id: actor for actor in actors}, native_effect_areas={}
        )
        initialize_global_pv_collections(fight, (31, -7), controller_registration=True)
        return fight

    def test_actual_retirement_keeps_diagnostic_actor_without_current_fdy(self):
        fight = self.fight()
        unregister_global_fighter(fight, 31)
        self.assertGreater(fight.actors[31].hp, 0)  # No HP-based absence inference.
        self.assertNotIn("31", fight.native_controller_registry["fighters"])
        self.assertEqual(
            {
                identity: effective_affiliation(fight, actor)
                for identity, actor in fight.actors.items()
            },
            {31: -1, -7: 1},
        )
        with self.assertRaises(ValueError):
            current_native_team(fight, 31)  # Strict controller operations stay strict.
        self.assertNotIn("31", fight.native_controller_registry["fighters"])

    def test_hp_zero_registered_fighter_still_requires_its_real_controller_row(self):
        fight = self.fight()
        fight.actors[31].hp = 0
        self.assertEqual(effective_affiliation(fight, fight.actors[31]), 0)
        del fight.native_controller_registry["fighters"]["31"]
        with self.assertRaisesRegex(ValueError, "Missing actual fdy controller row"):
            effective_affiliation(fight, fight.actors[31])

    def test_unattested_missing_membership_and_foreign_actor_remain_rejected(self):
        fight = self.fight()
        unregister_global_fighter(fight, 31)
        with self.assertRaisesRegex(ValueError, "Missing actual affiliation actor"):
            effective_affiliation(fight, Actor(31, 0, (0, 0, 0), 100, 6, 4, 1, 200))
        fight.native_global_pv_collections["retired_fighters"].clear()
        with self.assertRaisesRegex(
            ValueError, "Missing actual native fighter registration authority"
        ):
            effective_affiliation(fight, fight.actors[31])
