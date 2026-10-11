"""Distinct current/original fdy relations at actual registration boundaries."""
from types import SimpleNamespace
import unittest
from wakfu_server.combat_state import Actor
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    register_global_fighter,
    unregister_global_fighter,
)
from wakfu_server.combat_controller_registry import (
    current_native_controller,
    current_native_team,
    transfer_native_controller,
    restore_native_controller,
    clear_native_controller,
    set_native_current_team,
    apply_native_controller_transfer,
    remove_native_controller_transfer,
)


class NativeControllerRegistryTests(unittest.TestCase):
    def fight(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 1, 68),
            Actor(-7, 1, (2, 0, 0), 100, 6, 3, 1, 68),
        ]
        fight = SimpleNamespace(
            actors={actor.id: actor for actor in actors}, native_effect_areas={}
        )
        initialize_global_pv_collections(fight, (7, -7), controller_registration=True)
        return fight

    def test_transfer_samples_current_team_and_restore_uses_constructor_originals(self):
        fight = self.fight()
        set_native_current_team(fight, -7, 4)
        transfer_native_controller(fight, 7, -7)
        self.assertEqual(
            (current_native_controller(fight, 7), current_native_team(fight, 7)),
            (-7, 4),
        )
        set_native_current_team(fight, -7, 5)
        self.assertEqual(current_native_team(fight, 7), 4)
        clear_native_controller(fight, 7)
        self.assertIsNone(current_native_controller(fight, 7))
        self.assertEqual(current_native_team(fight, 7), -1)
        restore_native_controller(fight, 7)
        self.assertEqual(
            (current_native_controller(fight, 7), current_native_team(fight, 7)), (7, 0)
        )
        self.assertEqual(fight.actors[7].native_fight_affiliation, 0)

    def test_summon_registration_keeps_original_owner_and_retirement_removes_row(self):
        fight = self.fight()
        summon = Actor(-8, 0, (1, 0, 0), 100, 6, 3, 1, 68)
        summon.native_controller_id = 7
        fight.actors[-8] = summon
        register_global_fighter(fight, -8, controller_id=7)
        transfer_native_controller(fight, -8, -7)
        self.assertEqual(current_native_controller(fight, -8), -7)
        self.assertEqual(summon.native_controller_id, 7)
        restore_native_controller(fight, -8)
        self.assertEqual(current_native_controller(fight, -8), 7)
        unregister_global_fighter(fight, -8)
        with self.assertRaises(ValueError):
            current_native_team(fight, -8)

    def test_legacy_or_detached_state_does_not_infer_current_from_original(self):
        fight = self.fight()
        del fight.native_controller_registry
        fight.actors[7].native_controller_id = -7
        with self.assertRaises(ValueError):
            current_native_controller(fight, 7)
        with self.assertRaises(ValueError):
            current_native_team(fight, 7)

    def test_runner_uses_current_caster_controller_and_restores_preceding_ai(self):
        fight = self.fight()
        fight.actors[7].native_controlled_by_ai = True
        fight.actors[-7].native_controlled_by_ai = False
        previous = apply_native_controller_transfer(
            fight, 7, -7, use_current_controller=False
        )
        self.assertFalse(previous)
        self.assertTrue(fight.actors[-7].native_controlled_by_ai)
        self.assertEqual(current_native_controller(fight, -7), 7)
        # Another transfer uses the source's current controller, not its original.
        apply_native_controller_transfer(fight, -7, 7, use_current_controller=True)
        self.assertEqual(current_native_controller(fight, 7), 7)
        remove_native_controller_transfer(fight, -7, previous_ai=previous)
        self.assertEqual(
            (current_native_controller(fight, -7), current_native_team(fight, -7)),
            (-7, 1),
        )
        self.assertFalse(fight.actors[-7].native_controlled_by_ai)

    def test_unknown_ai_does_not_partially_mutate_controller(self):
        fight = self.fight()
        fight.actors[7].native_controlled_by_ai = True
        with self.assertRaises(ValueError):
            apply_native_controller_transfer(fight, 7, -7, use_current_controller=False)
        self.assertEqual(current_native_controller(fight, -7), -7)
