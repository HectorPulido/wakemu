"""Actual class book and shared transaction regressions under native AI control."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

import test_combat_spell_transaction as transaction_fixtures
from wakfu_server.spells import encode_deck
from wakfu_server.combat_class_ai_spell import (
    class_ai_capabilities,
    prepare_class_ai_plan,
    require_class_ai,
)
from wakfu_server.combat_cast import resolve_owned_spell_action
from wakfu_server.combat_controller_registry import (
    initialize_controller_registry,
    register_native_controller,
    apply_native_controller_transfer,
    remove_native_controller_transfer,
)
from wakfu_server.combat_spell_transaction import _prepare_spell_transaction


class ClassAi207Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = transaction_fixtures.SpellTransactionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fight = self.fixture.fight
        self.character = self.fixture.character
        self.deck = encode_deck([6266])
        initialize_controller_registry(self.fight)
        for actor in self.fight.actors.values():
            register_native_controller(
                self.fight, actor.id, team=actor.team, controller_id=actor.id
            )
            actor.native_controlled_by_ai = not actor.controlled
        self.actor = self.fight.actors[7]
        # Actual NPC-controlled original class player, preserving original owner.
        self.previous_ai = apply_native_controller_transfer(
            self.fight, -7, 7, use_current_controller=False
        )
        self.actor.effect_stats[4] = 6

    def execute(self, factory=None):
        return _prepare_spell_transaction(
            self.fixture.body,
            self.character,
            self.fight,
            None,
            self.deck,
            wp_current=6,
            action_id=1,
            line_of_sight=lambda *args: True,
            runtime_factory=factory or self.fixture.factory,
            conditional_context=self.fixture.cast_authority(),
            plan_builder=prepare_class_ai_plan,
        )

    def test_actual_class_ai_cast_pays_and_executes_shared_roots_privately(self):
        from wakfu_server.combat_spell_resource_costs import pay_extra_resources
        from wakfu_server.combat_cost_payment_events import replay_paid_spell_costs

        before = deepcopy(self.actor)
        with patch(
            "wakfu_server.combat_spell_resource_costs.pay_extra_resources",
            wraps=pay_extra_resources,
        ) as pay:
            with patch(
                "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs",
                wraps=replay_paid_spell_costs,
            ) as replay:
                result = self.execute()
        self.assertEqual(pay.call_count, 1)
        self.assertEqual(replay.call_count, 1)
        self.assertEqual(result.fight.actors[7].ap, 2)
        self.assertLess(result.fight.actors[-7].hp, 20)
        self.assertEqual(
            [opcode for opcode, _ in result.packets], [12588, 12678, 12613]
        )
        self.assertEqual(
            (self.actor.ap, self.actor.owner_id, self.actor.controlled),
            (before.ap, before.owner_id, True),
        )
        self.assertEqual(self.fight.actors[-7].hp, 20)

    def test_old_owner_cannot_send_input_while_server_ai_can_cast(self):
        request = {"actor_id": 7, "spell_uid": (7 << 32) | 6266}
        with self.assertRaisesRegex(ValueError, "owned active actor"):
            resolve_owned_spell_action(
                request, self.character, self.fight, 3, self.deck
            )
        self.assertLess(self.execute().fight.actors[-7].hp, 20)

    def test_failed_effect_dispatch_rolls_back_resources_and_damage(self):
        def fail(preview, plan):
            preview.actors[7].hp = 1
            raise ValueError("effect execution failed")

        before = (
            self.actor.hp,
            self.actor.ap,
            self.actor.effect_stats[4],
            self.fight.actors[-7].hp,
        )
        with self.assertRaisesRegex(ValueError, "effect execution failed"):
            self.execute(fail)
        self.assertEqual(
            before,
            (
                self.actor.hp,
                self.actor.ap,
                self.actor.effect_stats[4],
                self.fight.actors[-7].hp,
            ),
        )

    def test_capabilities_retain_exact_actual_deck_uid_and_level(self):
        rows = class_ai_capabilities(self.fight, self.character, self.deck)
        self.assertEqual(
            [(r["spellId"], r["level"], r["spellUid"]) for r in rows],
            [(6266, self.actor.effective_level, (7 << 32) | 6266)],
        )

    def test_temporary_grant_keeps_distinct_raw_uid_and_actual_level(self):
        self.fight.native_spell_grants = {
            7: {6266: {"reference": 6266, "uid": 6266, "level": 2}}
        }
        rows = class_ai_capabilities(self.fight, self.character, self.deck)
        # The native action protocol identifies a reference/level, so the
        # current raw grant is canonical; the original packed object survives.
        self.assertEqual({(r["spellUid"], r["level"]) for r in rows}, {(6266, 2)})
        from wakfu_server.combat_cast import _resolve_actor_spell_action

        resolved = _resolve_actor_spell_action(
            {"actor_id": 7, "spell_uid": (7 << 32) | 6266},
            self.character,
            self.fight,
            self.actor,
            self.deck,
            None,
        )
        self.assertEqual(resolved[1:], (6266, self.actor.effective_level))

    def test_morph_uses_actual_raw_book_instead_of_original_deck(self):
        self.fight.native_morph_spellbooks = {
            7: dict(book_uid=19, levels={6266: 3}, grants={}, removed_raw_uids=set())
        }
        rows = class_ai_capabilities(self.fight, self.character, self.deck)
        self.assertEqual([(r["spellUid"], r["level"]) for r in rows], [(6266, 3)])

    def test_morph_removed_object_is_not_advertised(self):
        self.fight.native_morph_spellbooks = {
            7: dict(book_uid=19, levels={6266: 3}, grants={}, removed_raw_uids={6266})
        }
        self.assertEqual(
            class_ai_capabilities(self.fight, self.character, self.deck), []
        )

    def test_unowned_uid_rejected_before_transaction_payment(self):
        self.fixture.body = struct.pack(">qqiih", 7, (7 << 32) | 12345, 1, 0, 0)
        with self.assertRaisesRegex(ValueError, "absent from current deck"):
            self.execute()
        self.assertEqual((self.actor.ap, self.actor.effect_stats[4]), (6, 6))

    def test_restore_original_controller_rejects_ai_and_accepts_original_owner(self):
        remove_native_controller_transfer(self.fight, 7, previous_ai=self.previous_ai)
        with self.assertRaisesRegex(ValueError, "authority"):
            require_class_ai(self.fight, self.character, self.deck)
        resolved = resolve_owned_spell_action(
            {"actor_id": 7, "spell_uid": (7 << 32) | 6266},
            self.character,
            self.fight,
            3,
            self.deck,
        )
        self.assertIs(resolved[0], self.actor)
        self.assertEqual(self.actor.owner_id, 3)

    def test_real_class_ai_can_end_server_turn_with_original_identity_preserved(self):
        turn = self.fight.turn_id
        self.fight.end_server_turn(7, turn)
        self.assertEqual(self.actor.owner_id, 3)
        self.assertTrue(self.actor.controlled)
        self.assertNotEqual(self.fight.current.id, 7)

    def test_missing_native_registry_or_wrong_participant_rejects(self):
        with self.assertRaisesRegex(ValueError, "authority"):
            require_class_ai(self.fight, dict(self.character, id=8), self.deck)
        del self.fight.native_controller_registry
        with self.assertRaisesRegex(ValueError, "authority"):
            require_class_ai(self.fight, self.character, self.deck)


if __name__ == "__main__":
    unittest.main()
