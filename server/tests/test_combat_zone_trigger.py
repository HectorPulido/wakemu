import unittest
from dataclasses import asdict
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_trigger_identifiers import (
    condition_identifiers,
    zone_trigger_policies,
)


class NativeZoneTriggerTests(unittest.TestCase):
    def test_native_source_flag_and_area_branches(self):
        for flag in (False, True):
            for point in (False, True):
                source = {
                    "zone_trigger_policy": dict(
                        definition_present=True, zone_flag=flag, point_area=point
                    )
                }
                context = ConditionContext(actors={}, **condition_identifiers(source))
                self.assertEqual(
                    evaluate_condition("IsTriggeredByZoneEffect()", context),
                    flag or not point,
                )
        for source in (None, {"zone_trigger_policy": {"definition_present": False}}):
            self.assertFalse(
                evaluate_condition(
                    "IsTriggeredByZoneEffect()",
                    ConditionContext(actors={}, **condition_identifiers(source)),
                )
            )

    def test_unknown_source_definition_and_invalid_arguments_reject(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsTriggeredByZoneEffect()",
                ConditionContext(actors={}, **condition_identifiers({})),
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsTriggeredByZoneEffect(1)", ConditionContext(actors={})
            )
        self.assertEqual(len(zone_trigger_policies()), 178337)

    def test_event_snapshot_keeps_actual_source_policy(self):
        event = NativeEventSource(
            uid=123,
            generic_effect=367719,
            value=12,
            caster_id=7,
            target_id=7,
            cell=(0, 0, 0),
            event_ids=(1000,),
            channel=6,
            manager_actor_id=7,
            source_parent_uid=None,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
            native_events_verified=True,
            zone_trigger_policy=dict(
                definition_present=True, zone_flag=False, point_area=False
            ),
        )
        event.validate()
        self.assertTrue(
            evaluate_condition(
                "IsTriggeredByZoneEffect()",
                ConditionContext(actors={}, **condition_identifiers(asdict(event))),
            )
        )
