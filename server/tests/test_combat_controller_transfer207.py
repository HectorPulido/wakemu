"""Native eWD207 parameter and actual registered relation regressions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_combat_controller_registry as registry_tests
from wakfu_server.combat_controller_transfer import (
    native_controller_selection,
    prepare_controller_transfer,
    apply_controller_transfer,
    remove_controller_transfer,
)
from wakfu_server.combat_controller_registry import (
    current_native_controller,
    current_native_team,
    transfer_native_controller,
)


class NativeControllerTransfer207Tests(unittest.TestCase):
    def setUp(self):
        self.fight = registry_tests.NativeControllerRegistryTests().fight()
        self.caster = self.fight.actors[7]
        self.target = self.fight.actors[-7]
        self.caster.native_controlled_by_ai = True
        self.target.native_controlled_by_ai = False
        self.authority = lambda fight, actor: SimpleNamespace(
            targeting={"is_eGj": True}
        )

    def prepare(self, parameters=(), published=False):
        return prepare_controller_transfer(
            self.fight,
            self.caster,
            self.target,
            self.authority,
            parameters=parameters,
            level=1,
            definitions={},
            effects={},
            published=published,
        )

    def test_native_oracle_first_parameter_exact_one_and_default(self):
        self.assertFalse(native_controller_selection([], 1))
        for value in [-2147483648, -1, 0, 1, 2, 2147483647]:
            self.assertEqual(native_controller_selection([value, 0], 1), value == 1)
            self.assertEqual(
                native_controller_selection([value, 0, 1, 0], 1), value == 1
            )

    def test_actual_transfer_retains_ownership_and_restores_original_not_previous(self):
        transfer_native_controller(self.fight, -7, 7)
        self.target.native_controller_id = -7
        receipt = apply_controller_transfer(self.fight, 7, -7, self.prepare())
        self.assertEqual(current_native_controller(self.fight, -7), 7)
        self.assertTrue(self.target.native_controlled_by_ai)
        self.assertEqual(self.target.native_controller_id, -7)
        remove_controller_transfer(self.fight, receipt)
        self.assertEqual(
            (
                current_native_controller(self.fight, -7),
                current_native_team(self.fight, -7),
            ),
            (-7, 1),
        )
        self.assertFalse(self.target.native_controlled_by_ai)

    def test_unknown_ai_fails_before_relation_changes(self):
        del self.target.native_controlled_by_ai
        with self.assertRaisesRegex(ValueError, "fqL"):
            self.prepare()
        self.assertEqual(current_native_controller(self.fight, -7), -7)

    def test_published_book_requires_real_source_and_does_not_change_ownership(self):
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            side_effect=ValueError("missing source"),
        ):
            with self.assertRaisesRegex(ValueError, "missing source"):
                self.prepare(published=True)
        self.assertEqual(current_native_controller(self.fight, -7), -7)

    def test_publication_flag_cannot_be_inferred_from_retention(self):
        with self.assertRaisesRegex(ValueError, "publication flag"):
            self.prepare(published=None)

    def test_current_caster_controller_selected_when_available(self):
        transfer_native_controller(self.fight, 7, -7)
        receipt = apply_controller_transfer(self.fight, 7, -7, self.prepare([1, 0]))
        self.assertEqual(receipt.applied_controller, -7)
        self.assertEqual(receipt.applied_team, 1)


class ControllerTransferRunner207Tests(unittest.TestCase):
    def fixture(self, retained=False):
        from wakfu_server.combat_controller_transfer import (
            NativeControllerTransferHandler,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_character_copy_book import CopyBookAction

        fight = registry_tests.NativeControllerRegistryTests().fight()
        fight.id = 8
        fight.owned_stat_effects = {}
        fight.actors[7].native_controlled_by_ai = True
        fight.actors[-7].native_controlled_by_ai = False
        packets = []
        handler = NativeControllerTransferHandler(
            fight,
            packets,
            allocate_uid=lambda: 91,
            action_id=5,
            context=lambda e, i: StatExecutionContext(True, True, None, retained, b""),
            authority=lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
            rng=lambda: 0.5,
            definitions={},
            effects={},
        )
        effect = dict(effect_class=207, parameters=[], target_masks=[None] * 7)
        invocation = EffectInvocation(
            22,
            1,
            7,
            -7,
            (2, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )
        book = (CopyBookAction(1001, 549, 1, False, True, False),)
        return handler, fight, packets, effect, invocation, book

    def test_runner_native_wire_phases_and_book_do_not_grant_ownership(self):
        handler, fight, packets, effect, invocation, book = self.fixture()
        phases = []
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda e, i, **k: phases.append(
                (k["channel"], current_native_controller(fight, -7))
            )
        )
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            return_value=(book, "owned.actual.fixture"),
        ):
            self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(phases, [(1, -7), (2, -7), (3, 7), (4, 7)])
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(fight.native_controller_action_books[-7]["actions"], book)
        self.assertFalse(hasattr(fight.actors[-7], "native_summon_action_book"))
        self.assertEqual(handler.runners, {})

    def test_player_ai_without_real_class_executor_rejects_before_any_mutation(self):
        import pickle

        handler, fight, packets, effect, invocation, book = self.fixture()
        target = fight.actors[-7]
        target.controlled = True
        target.owner_id = 101
        handler.authority = lambda f, a: SimpleNamespace(
            targeting={"is_eGj": True}, is_player=a is target
        )
        allocations = []
        phases = []
        handler.allocate_uid = lambda: allocations.append(91) or 91
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *a, **k: phases.append(k)
        )
        before = pickle.dumps(fight)
        with self.assertRaisesRegex(ValueError, "player AI capability producer"):
            handler(effect, {}, invocation)
        self.assertEqual(pickle.dumps(fight), before)
        self.assertEqual(packets, [])
        self.assertEqual(allocations, [])
        self.assertEqual(phases, [])
        self.assertEqual(handler.runners, {})

    def test_retained_removal_restores_original_controller_ai_and_retires_ui_book(self):
        from wakfu_server.combat_controller_transfer import remove_controller_runner

        handler, fight, packets, effect, invocation, book = self.fixture(retained=True)
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            return_value=(book, "owned.actual.fixture"),
        ):
            self.assertTrue(handler(effect, {}, invocation))
        self.assertTrue(fight.actors[-7].native_controlled_by_ai)
        remove_controller_runner(
            SimpleNamespace(fight=fight, action_id=6, packets=packets), 91
        )
        self.assertEqual(current_native_controller(fight, -7), -7)
        self.assertFalse(fight.actors[-7].native_controlled_by_ai)
        self.assertNotIn(-7, fight.native_controller_action_books)
        self.assertNotIn(91, fight.owned_stat_effects)
        self.assertEqual(packets[-1][0], 13560)


class ControllerTransferInput207Tests(unittest.TestCase):
    fixture = ControllerTransferRunner207Tests.fixture

    def test_actual_cast_uid_resolver_rejects_old_owner_and_accepts_current_controller(
        self,
    ):
        from wakfu_server.combat_cast import resolve_owned_spell_action

        handler, fight, packets, effect, invocation, book = self.fixture()
        caster, target = fight.actors[7], fight.actors[-7]
        caster.controlled = True
        caster.owner_id = 202
        caster.native_controlled_by_ai = False
        target.controlled = True
        target.owner_id = 101
        fight.phase = "active"
        fight.current = target
        with patch(
            prepare_controller_transfer.__module__ + ".target_controller_spellbook",
            return_value=(book, "owned.actual.fixture"),
        ):
            self.assertTrue(handler(effect, {}, invocation))
        request = {"actor_id": target.id, "spell_uid": 1001}
        with self.assertRaisesRegex(ValueError, "owned active actor"):
            resolve_owned_spell_action(request, {"id": target.id}, fight, 101, b"")
        resolved = resolve_owned_spell_action(
            request, {"id": caster.id}, fight, 202, b""
        )
        self.assertEqual(resolved, (target, 549, 1))
        self.assertEqual(target.owner_id, 101)
        with self.assertRaisesRegex(ValueError, "absent"):
            resolve_owned_spell_action(
                {"actor_id": target.id, "spell_uid": 9999},
                {"id": caster.id},
                fight,
                202,
                b"",
            )


if __name__ == "__main__":
    unittest.main()
