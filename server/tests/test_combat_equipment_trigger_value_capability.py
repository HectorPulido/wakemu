import unittest
from unittest.mock import patch

from wakfu_server.combat_effect_runtime import (
    NativeEffectRuntimeFactory,
    NativeRuntimeContexts,
)
from wakfu_server.combat_equipment_operation_capability import validate_effect
from wakfu_server.combat_trigger_value_handler import NativeTriggerValueHandler
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_native_timing_context import native_time_payload


def _effect(parameters):
    return dict(
        effect_class=430,
        parameters=tuple(parameters),
        parameter_count=len(parameters) // 2,
        variant=0,
        native_execution_mode=0,
        native_definition_class="eVE",
        native_target_selector={"class": "fcE", "mask": 2},
        area_native="empty",
        area_class="anA",
        target_masks=(None,) * 7,
        native_effect_flags=(),
        native_timing_definition={"clock_on_caster": False, "clock_on_target": True},
        native_hmi_actions={
            "rzc": (),
            "rzd": (),
            "rze": (),
            "rzf": (),
            "rzg": (),
            "rzh": (),
        },
        application_flag="NONE",
        removal_flag="NONE",
        probability_base=100,
        probability_per_level=0,
        minimum_level=0,
        maximum_level=32767,
        children=(),
        criteria="",
    )


class CombatEquipmentTriggerValueCapabilityTests(unittest.TestCase):
    def test_parser_evaluates_mode_amount_and_replace_with_native_level(self):
        from wakfu_server.combat_equipment_trigger_value_parser import parse

        self.assertEqual(
            {"mode": 0, "amount": -100, "replace": False},
            parse(_effect((0, 0, -100, 0, 0, 0)), {"parameters": (0, -100, 0)}, 3),
        )
        self.assertEqual(
            {"mode": 1, "amount": 25, "replace": True},
            parse(
                _effect((1, 0, 25, 0, 1, 0, 777, 888)),
                {"parameters": (1, 25, 1, 777)},
                3,
            ),
        )
        with self.assertRaisesRegex(ValueError, "three parameter pairs"):
            parse(_effect((0, 0)), {"parameters": (0,)}, 0)

    def test_factory_route_accepts_exact_ezl_handler_and_real_replay_lifecycle(self):
        callback = lambda *_args, **_kwargs: None
        contexts = NativeRuntimeContexts(*([callback] * 13))
        authority = OrdinaryActorAuthority(
            characters={}, monsters={}, decks={}, excluded_decks={}
        )
        factory = NativeEffectRuntimeFactory(
            effects={},
            state_catalog={"states": {}, "effects": {}},
            characteristic_registry={"effects": {}},
            action_id=1,
            contexts=contexts,
            displacement_authority=authority,
        )
        routes, provider = factory.equipment_operation_capability()
        self.assertIs(routes.routes[430].handler_type, NativeTriggerValueHandler)
        with patch(
            "wakfu_server.combat_equipment_retained_lifecycle.preflight",
            return_value=True,
        ):
            result = validate_effect(
                _effect((1, 0, 25, 0, 0, 0)),
                1,
                {},
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container={"present": True},
            )
        self.assertEqual("supported", result.status, result.reasons)
        self.assertEqual("effect.triggering_amount", result.operation_id)
        self.assertEqual(
            {"mode": 1, "amount": 25, "replace": False}, result.parameters[0]
        )

        extra_pairs = _effect((1, 0, 25, 0, 0, 0, 777, 888))
        with patch(
            "wakfu_server.combat_equipment_retained_lifecycle.preflight",
            return_value=True,
        ):
            extra_result = validate_effect(
                extra_pairs,
                1,
                {"parameters": (1, 25, 0, 777)},
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container={"present": True},
            )
        self.assertEqual("supported", extra_result.status, extra_result.reasons)

    def test_initial_dispatch_without_qe_source_keeps_native_retained_uid_without_mutation(
        self,
    ):
        from types import SimpleNamespace

        fight = SimpleNamespace(
            phase="active", actors={7: object(), 8: object()}, owned_stat_effects={}
        )
        context = StatExecutionContext(
            True, True, None, True, native_time_payload(), None
        )
        handler = NativeTriggerValueHandler(
            fight, allocate_uid=lambda: 99, context=lambda *_args: context
        )
        result = handler(
            _effect((1, 0, 25, 0, 0, 0)),
            {"parameters": (1, 25, 0)},
            EffectInvocation(123, 200, 7, 8, (0, 0, 0)),
        )
        self.assertTrue(result)
        self.assertEqual(
            ("eZL", None, 25),
            (
                fight.owned_stat_effects[99]["family"],
                fight.owned_stat_effects[99]["stat_id"],
                fight.owned_stat_effects[99]["actual"],
            ),
        )

    def test_event_source_eWu_runner_uses_state_level_modes_independent_of_amount(self):
        from types import SimpleNamespace
        from wakfu_server.combat_event_replay import NativeEventSource
        from wakfu_server.combat_final_modifier import final_modifier_source
        from wakfu_server.combat_state_runner import NativeRunnerStateLevel

        fight = SimpleNamespace(
            phase="active", actors={7: object(), 8: object()}, owned_stat_effects={}
        )
        context = StatExecutionContext(
            True, True, None, False, native_time_payload(), None
        )
        handler = NativeTriggerValueHandler(
            fight, allocate_uid=lambda: 99, context=lambda *_args: context
        )
        runner = NativeRunnerStateLevel(
            77, 304, rng=lambda: 0, reference=200, level=5, value=123
        )
        source = NativeEventSource(
            uid=77,
            generic_effect=200,
            value=123,
            caster_id=7,
            target_id=8,
            cell=(0, 0, 0),
            event_ids=(1001,),
            channel=5,
            manager_actor_id=7,
            source_parent_uid=None,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
            native_events_verified=True,
            effect_action_id=304,
            runner_modifier=runner,
        )
        invocation = EffectInvocation(123, 200, 7, 8, (0, 0, 0))

        with final_modifier_source(source):
            self.assertTrue(
                handler(
                    _effect((4, 0, 3, 0, 0, 0)), {"parameters": (4, 3, 0)}, invocation
                )
            )
        self.assertEqual(
            (200, 8, 123), (runner.reference, runner.pending_level, runner.value)
        )

        with final_modifier_source(source):
            self.assertTrue(
                handler(
                    _effect((7, 0, 50, 0, 0, 0)), {"parameters": (7, 50, 0)}, invocation
                )
            )
        self.assertEqual(
            (200, 12, 123), (runner.reference, runner.pending_level, runner.value)
        )
