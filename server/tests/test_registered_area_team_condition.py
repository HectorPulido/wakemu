"""Registered faV criteria read its captured bcM, independently from its owner."""
from copy import deepcopy
import unittest
import test_combat_runtime_adapter as _adapter_fixture

from wakfu_server.combat_conditions import evaluate_condition, UnknownCondition
from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class RegisteredAreaTeamConditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _adapter_fixture.ServerAdapterTests.setUpClass()

    def setUp(self):
        self.source = _adapter_fixture.ServerAdapterTests()
        self.source.setUp()
        self.fight, self.adapter = self.source.preview, self.source.adapter
        self.fight.actors[7].position = (2, 3, 0)
        # This bounded custom authority must supply the constructor bcM operand;
        # it does not have production ordinary-roster fallback authority.
        self.fight.actors[7].native_fight_affiliation = 0
        self.fight.native_effect_areas = {}
        sequence = iter((901, 902))
        handler = NativeEffectAreaHandler(
            self.fight,
            [],
            action_id=1,
            allocate_uid=lambda: next(sequence),
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
            area_affiliation=self.adapter.area_affiliation,
        )
        handler.on_created = lambda row: None
        handler(
            {"effect_class": 315},
            {"parameters": [823]},
            EffectInvocation(100, 1, 7, None, (2, 3, 0)),
        )
        self.row = self.fight.native_effect_areas[901]

    def test_registered_target_and_caster_keep_constructor_capture_after_owner_change(
        self,
    ):
        self.assertEqual(self.row["native_fight_affiliation"], 0)
        self.fight.actors[7].native_fight_affiliation = 1
        for invocation, expression in (
            (
                EffectInvocation(339526, 1, 7, 901, (2, 3, 0)),
                'GetTeamId("target") == 0 and GetTeamId("caster") == 1',
            ),
            (
                EffectInvocation(339526, 1, 901, 7, (2, 3, 0)),
                'GetTeamId("caster") == 0 and GetTeamId("target") == 1',
            ),
        ):
            with self.subTest(expression=expression):
                context = self.adapter.condition(self.fight, {}, None, invocation)
                self.assertTrue(evaluate_condition(expression, context))

    def test_missing_capture_is_not_replaced_with_current_owner_team(self):
        del self.row["native_fight_affiliation"]
        del self.row["native_fight_affiliation_source"]
        with self.assertRaisesRegex(ValueError, "bcM"):
            context = self.adapter.condition(
                self.fight, {}, None, EffectInvocation(339526, 1, 7, 901, (2, 3, 0))
            )
            evaluate_condition('GetTeamId("target") == 0', context)

    def test_signed_byte_capture_boundaries_remain_exact(self):
        for value in (-128, -1, 0, 1, 127):
            with self.subTest(value=value):
                self.row["native_fight_affiliation"] = value
                context = self.adapter.condition(
                    self.fight,
                    {},
                    None,
                    EffectInvocation(339526, 1, 7, 901, (2, 3, 0)),
                )
                self.assertTrue(
                    evaluate_condition(
                        'GetTeamId("target") == ' + str(value),
                        context,
                    )
                )

    def test_malformed_capture_does_not_fall_back_to_owner(self):
        for value in (None, True, 128, -129, "0"):
            with self.subTest(value=value):
                self.row["native_fight_affiliation"] = value
                with self.assertRaises(ValueError):
                    context = self.adapter.condition(
                        self.fight,
                        {},
                        None,
                        EffectInvocation(339526, 1, 7, 901, (2, 3, 0)),
                    )
                    evaluate_condition('GetTeamId("target") == 0', context)

    def test_transaction_clone_preserves_captured_enemy_team(self):
        self.fight.actors[7].native_fight_affiliation = 1
        clone = deepcopy(self.fight)
        self.assertEqual(clone.native_effect_areas[901]["native_fight_affiliation"], 0)
        context = self.adapter.condition(
            clone,
            {},
            None,
            EffectInvocation(339526, 1, 7, 901, (2, 3, 0)),
        )
        self.assertTrue(
            evaluate_condition(
                'GetTeamId("target") != GetTeamId("caster")',
                context,
            )
        )

    def test_triggering_area_source_and_target_supply_actual_native_radius(self):
        for source_id, target_id in ((7, 901), (901, 7)):
            for x, expected in ((2, True), (7, False)):
                with self.subTest(source=source_id, target=target_id, x=x):
                    self.fight.actors[7].position = (x, 3, 0)
                    invocation = EffectInvocation(
                        339526,
                        1,
                        7,
                        -7,
                        (1, 0, 0),
                        native_trigger_context={
                            "caster_id": source_id,
                            "target_id": target_id,
                            "effect_flags": [],
                        },
                    )
                    context = self.adapter.condition(self.fight, {}, None, invocation)
                    self.assertEqual(
                        evaluate_condition(
                            "IsTriggeredByMeleeEffect()",
                            context,
                        ),
                        expected,
                    )

    def test_unregistered_trigger_area_stays_rejected(self):
        invocation = EffectInvocation(
            339526,
            1,
            7,
            -7,
            (1, 0, 0),
            native_trigger_context={
                "caster_id": 7,
                "target_id": 99999,
                "effect_flags": [],
            },
        )
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            self.adapter.condition(self.fight, {}, None, invocation)

    def test_proven_absent_trigger_keeps_native_non_melee_result(self):
        context = self.adapter.condition(
            self.fight, {}, None, EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        )
        self.assertFalse(evaluate_condition("IsTriggeredByMeleeEffect()", context))

    def test_triggering_roles_keep_original_area_team_and_identity(self):
        self.fight.actors[7].native_fight_affiliation = 1
        for caster_id, target_id, caster_team, target_team in (
            (7, 901, 1, 0),
            (901, 7, 0, 1),
        ):
            with self.subTest(caster=caster_id, target=target_id):
                context = self.adapter.condition(
                    self.fight,
                    {},
                    None,
                    EffectInvocation(
                        339526,
                        1,
                        7,
                        -7,
                        (1, 0, 0),
                        native_trigger_context={
                            "caster_id": caster_id,
                            "target_id": target_id,
                            "effect_flags": [],
                        },
                    ),
                )
                self.assertTrue(
                    evaluate_condition(
                        f'GetTeamId("triggeringCaster") == {caster_team} and '
                        f'GetTeamId("triggeringTarget") == {target_team} and '
                        f"GetTriggeringEffectCaster() == {caster_id} and "
                        f"GetTriggeringEffectTarget() == {target_id}",
                        context,
                    )
                )
        for listener_id, expected in ((901, True), (7, False)):
            with self.subTest(listener=listener_id):
                context = self.adapter.condition(
                    self.fight,
                    {},
                    None,
                    EffectInvocation(
                        339526,
                        1,
                        listener_id,
                        -7,
                        (1, 0, 0),
                        native_trigger_context={
                            "caster_id": 901,
                            "target_id": 7,
                            "effect_flags": [],
                        },
                    ),
                )
                self.assertEqual(
                    evaluate_condition(
                        "GetTriggeringEffectCasterIsSameAsCaster()",
                        context,
                    ),
                    expected,
                )

    def test_retired_source_scope_keeps_actual_capture_and_null_qf(self):
        from wakfu_server.combat_state_managers import removed_area_pv_scope

        row = self.fight.native_effect_areas.pop(901)
        self.assertIs(row, self.row)
        self.assertIsNone(row.get("state_ledger"))
        self.fight.actors[7].native_fight_affiliation = 1
        with removed_area_pv_scope(self.fight, row):
            context = self.adapter.condition(
                self.fight,
                {},
                None,
                EffectInvocation(
                    339526,
                    1,
                    7,
                    -7,
                    (1, 0, 0),
                    native_trigger_context={
                        "caster_id": 7,
                        "target_id": 901,
                        "effect_flags": [],
                    },
                ),
            )
            self.assertTrue(
                evaluate_condition(
                    'GetTeamId("triggeringTarget") == 0 and '
                    "GetTriggeringEffectTarget() == 901 and "
                    'not HasState(9141, "triggeringTarget")',
                    context,
                )
            )
            self.assertIsNone(row.get("state_ledger"))
        self.assertNotIn(901, self.fight.native_effect_areas)
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            self.adapter.condition(
                self.fight,
                {},
                None,
                EffectInvocation(
                    339526,
                    1,
                    7,
                    -7,
                    (1, 0, 0),
                    native_trigger_context={"caster_id": 7, "target_id": 901},
                ),
            )

    def test_registered_trigger_area_does_not_gain_character_spellbook(self):
        context = self.adapter.condition(
            self.fight,
            {},
            None,
            EffectInvocation(
                339526,
                1,
                7,
                -7,
                (1, 0, 0),
                native_trigger_context={
                    "caster_id": 7,
                    "target_id": 901,
                    "effect_flags": [],
                },
            ),
        )
        with self.assertRaisesRegex(ValueError, "not a character"):
            evaluate_condition('GetSpellLevel(6266, "triggeringTarget") == 1', context)

    def test_original_source_identity_is_not_coerced_from_numeric_lookalike(self):
        with self.assertRaisesRegex(ValueError, "source PV identity"):
            self.adapter.condition(
                self.fight,
                {},
                None,
                EffectInvocation(
                    339526,
                    1,
                    7,
                    -7,
                    (1, 0, 0),
                    native_trigger_context={
                        "caster_id": 7.0,
                        "target_id": 901,
                        "effect_flags": [],
                    },
                ),
            )

    def test_proven_null_target_keeps_native_minus_one(self):
        context = self.adapter.condition(
            self.fight, {}, None, EffectInvocation(339526, 1, 7, None, None)
        )
        self.assertTrue(evaluate_condition('GetTeamId("target") == -1', context))


if __name__ == "__main__":
    unittest.main()
