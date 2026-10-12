"""Actual current-controller authorization while actor ownership is immutable."""
import unittest
import test_combat_controller_registry as registry_tests
from wakfu_server.combat_effective_control import (
    effective_server_controlled,
    effective_input_owner,
    require_effective_owner,
)
from wakfu_server.combat_controller_registry import (
    transfer_native_controller,
    restore_native_controller,
)
from wakfu_server.combat_ai_control import set_native_ai_control


class EffectiveControl207Tests(unittest.TestCase):
    def setUp(self):
        self.fight = registry_tests.NativeControllerRegistryTests().fight()
        self.a, self.b = self.fight.actors.values()
        self.a.controlled = self.b.controlled = True
        self.a.owner_id = 101
        self.b.owner_id = 202
        self.a.native_controlled_by_ai = self.b.native_controlled_by_ai = False

    def test_old_owner_rejected_new_controller_accepted_then_original_restored(self):
        transfer_native_controller(self.fight, self.a.id, self.b.id)
        with self.assertRaisesRegex(ValueError, "not controlled"):
            require_effective_owner(self.fight, self.a, 101)
        self.assertIs(require_effective_owner(self.fight, self.a, 202), self.a)
        self.assertEqual(self.a.owner_id, 101)
        self.assertTrue(self.a.controlled)
        restore_native_controller(self.fight, self.a.id)
        self.assertIs(require_effective_owner(self.fight, self.a, 101), self.a)
        with self.assertRaises(ValueError):
            require_effective_owner(self.fight, self.a, 202)

    def test_ai_flag_routes_server_turn_even_original_player(self):
        set_native_ai_control(self.a, True)
        self.assertTrue(effective_server_controlled(self.fight, self.a))
        self.assertIsNone(effective_input_owner(self.fight, self.a))
        with self.assertRaises(ValueError):
            require_effective_owner(self.fight, self.a, 101)

    def test_npc_actual_ai_true_is_server_controlled(self):
        self.a.controlled = False
        self.a.owner_id = None
        set_native_ai_control(self.a, True)
        self.assertTrue(effective_server_controlled(self.fight, self.a))

    def test_fight_input_boundary_rejects_old_owner_and_restores(self):
        from wakfu_server.combat_state import Fight

        self.fight._in_play = lambda actor: actor.hp > 0
        self.fight.current = self.a
        transfer_native_controller(self.fight, self.a.id, self.b.id)
        with self.assertRaisesRegex(ValueError, "not controlled"):
            Fight._current_owned(self.fight, 101, self.a.id)
        self.assertIs(Fight._current_owned(self.fight, 202, self.a.id), self.a)
        restore_native_controller(self.fight, self.a.id)
        self.assertIs(Fight._current_owned(self.fight, 101, self.a.id), self.a)

    def test_actual_fight_server_turn_uses_native_ai_even_original_player(self):
        from wakfu_server.combat_state import Fight

        self.fight.current = self.a
        self.fight.turn_id = 9
        advanced = []
        self.fight._advance = lambda: advanced.append(self.a.id)
        set_native_ai_control(self.a, True)
        Fight.end_server_turn(self.fight, self.a.id, 9)
        self.assertEqual(advanced, [self.a.id])
        set_native_ai_control(self.a, False)
        with self.assertRaisesRegex(ValueError, "Invalid server controlled turn"):
            Fight.end_server_turn(self.fight, self.a.id, 9)

    def test_missing_native_ai_authority_rejected(self):
        del self.a.native_controlled_by_ai
        with self.assertRaisesRegex(ValueError, "fqL"):
            effective_server_controlled(self.fight, self.a)

    def test_legacy_snapshot_preserves_original_authorization(self):
        del self.fight.native_controller_registry
        self.assertFalse(effective_server_controlled(self.fight, self.a))
        self.assertEqual(effective_input_owner(self.fight, self.a), 101)


if __name__ == "__main__":
    unittest.main()
