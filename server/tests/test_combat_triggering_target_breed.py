import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class TriggeringTargetBreedTests(unittest.TestCase):
    def check(self, context, expected):
        return evaluate_condition(
            "GetTriggeringEffectTargetBreedId() == " + str(expected), context
        )

    def test_actual_source_target_uses_its_breed_not_caster_or_recipient(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(breed_id=1),
                "target": ConditionActor(breed_id=2),
                "triggeringtarget": ConditionActor(
                    is_native_fighter=True, breed_id=3077
                ),
            },
            triggering_effect_present=True,
        )
        self.assertTrue(self.check(context, 3077))

    def test_proven_null_and_nonfighter_are_native_minus_one(self):
        for context in (
            ConditionContext({}, null_actor_aliases=frozenset({"triggeringtarget"})),
            ConditionContext(
                {"triggeringtarget": ConditionActor(is_native_fighter=False)}
            ),
        ):
            self.assertTrue(self.check(context, -1))

    def test_unknown_target_type_and_unknown_breed_stay_unknown(self):
        for actor in (
            None,
            ConditionActor(breed_id=3),
            ConditionActor(is_native_fighter=True),
            ConditionActor(is_native_fighter=True, breed_id=True),
            ConditionActor(is_native_fighter=True, breed_id=32768),
        ):
            context = ConditionContext(
                {} if actor is None else {"triggeringtarget": actor}
            )
            with self.assertRaises(UnknownCondition):
                self.check(context, -1)

    def test_native_short_boundaries_and_zero_argument_contract(self):
        for breed in (-32768, 32767):
            self.assertTrue(
                self.check(
                    ConditionContext(
                        {
                            "triggeringtarget": ConditionActor(
                                is_native_fighter=True, breed_id=breed
                            ),
                        }
                    ),
                    breed,
                )
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetTriggeringEffectTargetBreedId(1) == -1", ConditionContext({})
            )


class TriggeringBreedAdapterTests(unittest.TestCase):
    def test_existing_runtime_producer_resolves_actual_source_target_alias(self):
        from test_combat_runtime_adapter import ServerAdapterTests
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        ServerAdapterTests.setUpClass()
        fixture = ServerAdapterTests()
        fixture.setUp()
        invocation = EffectInvocation(
            1,
            1,
            7,
            8,
            (2, 3, 0),
            native_trigger_context={"caster_id": 8, "target_id": 7},
        )
        context = fixture.adapter.condition(fixture.preview, {}, None, invocation)
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectTargetBreedId() == 15", context)
        )
        null = fixture.adapter.condition(
            fixture.preview,
            {},
            None,
            EffectInvocation(1, 1, 7, 8, (2, 3, 0)),
        )
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectTargetBreedId() == -1", null)
        )
