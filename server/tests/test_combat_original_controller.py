import unittest
from types import SimpleNamespace
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_original_controller import original_target_controller
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents


class OriginalControllerTests(unittest.TestCase):
    def test_zero_arguments_signed_identity_null_and_unknown(self):
        for value in (0, -200, 7):
            context = ConditionContext(
                {}, effect_target_original_controller_query=lambda: value
            )
            self.assertTrue(
                evaluate_condition(
                    f"GetEffectTargetOriginalController() == {value}", context
                )
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetEffectTargetOriginalController() == 0", ConditionContext({})
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetEffectTargetOriginalController('target') == 0", context
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetEffectTargetOriginalController() == 0",
                ConditionContext(
                    {}, effect_target_original_controller_query=lambda: True
                ),
            )

    def test_controller_authority_is_not_account_owner_or_identity_guess(self):
        actor = SimpleNamespace(id=-200, owner_id=7)
        fight = SimpleNamespace(actors={-200: actor})
        authority = lambda p, a: SimpleNamespace(native_controller_id=91)
        self.assertEqual(original_target_controller(fight, authority, -200), 91)
        self.assertEqual(original_target_controller(fight, authority, None), 0)
        with self.assertRaises(ValueError):
            original_target_controller(
                fight, lambda p, a: SimpleNamespace(native_controller_id=None), -200
            )
        with self.assertRaises(ValueError):
            original_target_controller(fight, authority, 456)

    def test_area_controller_is_native_owner_not_area_uid(self):
        fight = SimpleNamespace(
            actors={},
            native_effect_areas={500: dict(native_area_contract="faZ", owner_id=91)},
        )
        self.assertEqual(original_target_controller(fight, None, 500), 91)
        fight.native_effect_areas[500]["owner_id"] = None
        self.assertEqual(original_target_controller(fight, None, 500), 0)
        del fight.native_effect_areas[500]["owner_id"]
        with self.assertRaises(ValueError):
            original_target_controller(fight, None, 500)

    def test_replay_criteria_passes_retained_target_not_rebound_or_source(self):
        class Adapter:
            def condition(
                self, p, plan, effect, invocation, *, native_original_target_id
            ):
                return native_original_target_id

        events = object.__new__(OrdinaryHealingEvents)
        events.adapter = Adapter()
        events.plan = {}
        events.preview = SimpleNamespace(
            native_owned_group_effects={33: dict(invocation=dict(target_id=91))}
        )
        invocation = SimpleNamespace(base_uid=33, target_id=202)
        self.assertEqual(
            events.conditions({}, invocation, SimpleNamespace(target_id=303)), 91
        )
        events.preview.native_owned_group_effects[33]["invocation"]["target_id"] = None
        self.assertIsNone(events.conditions({}, invocation, None))

    def test_fresh_ordinary_npc_self_controller_and_changed_relationship_rejected(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority

        actor = Actor(-200, 1, (0, 0, 0), 20, 3, 3, 1, 1)
        fight = SimpleNamespace(actors={-200: actor}, events=[])
        authority = OrdinaryActorAuthority(
            characters={},
            monsters={-200: dict(id=-200, ref=5525)},
            decks={},
            excluded_decks={},
            catalog={"npc": {"5525": {"fight_properties": []}}},
        )
        self.assertEqual(authority(fight, actor).native_controller_id, -200)
        actor.native_master_id = 7
        with self.assertRaises(ValueError):
            authority(fight, actor)
