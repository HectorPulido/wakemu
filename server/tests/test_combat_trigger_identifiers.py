from dataclasses import asdict, replace
import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_trigger_identifiers import (
    source_identifiers,
    condition_identifiers,
)
from wakfu_server.combat_event_replay import NativeEventSource


class TriggerIdentifierTests(unittest.TestCase):
    def test_container_type_known_null_present_and_unknown(self):
        for source, expected in (
            (None, 0),
            ({"native_container": {"present": False}}, 0),
            ({"native_container": {"present": True, "type": 11}}, 11),
            ({"native_container": {"present": True, "type": 1}}, 1),
            ({"native_container": {"present": True, "type": 3}}, 3),
        ):
            self.assertTrue(
                evaluate_condition(
                    f"GetTriggeringContainerType() == {expected}", self.context(source)
                )
            )
        for source in (
            {},
            {"native_container": {"present": True}},
            {"native_container": {"present": True, "type": 99}},
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "GetTriggeringContainerType() == 0", self.context(source)
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetTriggeringContainerType(1) == 11", self.context(None)
            )

    def test_triggering_caster_uses_source_identity_and_null_sentinel(self):
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectCaster() == -1", self.context(None))
        )
        for identity in (7, -99, (1 << 62)):
            context = ConditionContext(
                {}, triggering_effect_present=True, triggering_effect_caster_id=identity
            )
            self.assertTrue(
                evaluate_condition(
                    f"GetTriggeringEffectCaster() == {identity}", context
                )
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectCaster() == 0", self.context({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectCaster(1) == -1", self.context(None))

    def test_same_trigger_caster_requires_proven_object_identity_and_no_arguments(self):
        for same in (False, True):
            context = ConditionContext({}, triggering_caster_is_same=same)
            self.assertEqual(
                evaluate_condition(
                    "GetTriggeringEffectCasterIsSameAsCaster()", context
                ),
                same,
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetTriggeringEffectCasterIsSameAsCaster()", ConditionContext({})
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetTriggeringEffectCasterIsSameAsCaster(1)",
                ConditionContext({}, triggering_caster_is_same=True),
            )

    def test_triggering_target_identity_is_separate_from_caster(self):
        context = ConditionContext(
            {},
            triggering_effect_present=True,
            triggering_effect_caster_id=7,
            triggering_effect_target_id=-99,
        )
        self.assertTrue(
            evaluate_condition(
                "GetTriggeringEffectCaster() <> GetTriggeringEffectTarget()", context
            )
        )
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectTarget() == -1", self.context(None))
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectTarget() == -1", self.context({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectTarget(1) == -1", self.context(None))

    def context(self, source):
        return ConditionContext({}, **condition_identifiers(source))

    def test_no_source_and_unknown_source_are_distinct(self):
        c = self.context(None)
        self.assertTrue(
            evaluate_condition(
                "GetTriggeringContainerStateId() == 0 and GetTriggeringEffectActionId() == -1",
                c,
            )
        )
        for source in ({}, {"effect_action_id": 400}):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    "GetTriggeringContainerStateId() == 0", self.context(source)
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectActionId() == 400", self.context({}))
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectActionId(0) == -1", self.context({}))
        )

    def test_source_action_is_runner_family_not_reference_and_depth_same_source(self):
        c = self.context(
            {
                "generic_effect": 987654,
                "effect_action_id": 400,
                "native_container": {"present": True, "type": 11, "is_state": False},
            }
        )
        self.assertTrue(
            evaluate_condition(
                "GetTriggeringEffectActionId() == 400 and GetTriggeringEffectActionId(2) == 400 and GetTriggeringContainerStateId() == 0",
                c,
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetTriggeringEffectActionId("caster") == 400', c)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringContainerStateId(1) == 0", c)

    def test_source_fyw_signed_short_and_real_event_roundtrip(self):
        class Retention:
            def container(self, invocation):
                return {"container_present": True, "container_type": 1}, (
                    40000 << 16
                ) | 200

        fields = source_identifiers(Retention(), {"effect_class": 82}, None)
        event = NativeEventSource(
            123,
            987654,
            10,
            7,
            -7,
            (0, 0, 0),
            (0, 1),
            3,
            -7,
            None,
            False,
            False,
            False,
            True,
            **fields,
        )
        event.validate()
        c = self.context(asdict(event))
        self.assertTrue(
            evaluate_condition(
                "GetTriggeringContainerStateId() == -25536 and GetTriggeringEffectActionId() == 82",
                c,
            )
        )
        self.assertEqual(asdict(event)["generic_effect"], 987654)

    def test_explicit_null_container_and_boolean_shortcircuit(self):
        c = self.context(
            {"native_container": {"present": False}, "effect_action_id": 81}
        )
        self.assertTrue(evaluate_condition("GetTriggeringContainerStateId() == 0", c))
        self.assertFalse(
            evaluate_condition(
                "False and GetTriggeringEffectActionId() == 81", self.context({})
            )
        )

    def test_source_value_signed_and_absence_not_unknown_zero(self):
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectValue() == 0", self.context(None))
        )
        self.assertTrue(
            evaluate_condition(
                "GetTriggeringEffectValue() == -25", self.context({"value": -25})
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectValue() == 0", self.context({}))
        with self.assertRaises(ValueError):
            self.context({"value": 1 << 31})

    def test_source_definition_id_is_not_uid_or_action(self):
        c = self.context(
            {"generic_effect": 987654, "effect_action_id": 400, "uid": 123}
        )
        self.assertTrue(
            evaluate_condition(
                "GetTriggeringEffectId() == 987654 and GetTriggeringEffectId(2) == 987654 and GetTriggeringEffectActionId() == 400",
                c,
            )
        )
        for depth in (0, -1):
            self.assertTrue(
                evaluate_condition(
                    f"GetTriggeringEffectId({depth}) == -1 and GetTriggeringEffectActionId({depth}) == -1",
                    c,
                )
            )
        self.assertTrue(
            evaluate_condition("GetTriggeringEffectId() == -1", self.context(None))
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetTriggeringEffectId() == 0", self.context({}))
