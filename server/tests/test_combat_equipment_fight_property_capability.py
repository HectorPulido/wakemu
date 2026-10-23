import unittest
from unittest.mock import patch

from wakfu_server.combat_effect_runtime import (
    NativeEffectRuntimeFactory,
    NativeRuntimeContexts,
)
from wakfu_server.combat_equipment_fight_property_parser import parse
from wakfu_server.combat_equipment_operation_capability import validate_effect
from wakfu_server.combat_fight_property import (
    NativeFightPropertyHandler,
    property_registry,
)
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority


def _effect(parameters):
    return dict(
        effect_class=447,
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


class CombatEquipmentFightPropertyCapabilityTests(unittest.TestCase):
    def test_parser_uses_native_parameter_arithmetic_and_one_value_shape(self):
        parsed = parse(
            {"parameters": (69.0, 0.25)},
            {"parameters": (69,)},
            4,
        )
        self.assertEqual({"property_id": 70}, parsed)
        with_extras = parse(
            {"parameters": (69.0, 0.25, 11.0, 0.0)},
            {"parameters": (70, 11)},
            4,
        )
        self.assertEqual({"property_id": 70}, with_extras)
        with self.assertRaisesRegex(ValueError, "one value"):
            parse(
                {"parameters": ()},
                {"parameters": ()},
                1,
            )

    def test_real_factory_accepts_published_counter_enum_and_defers_special_context(
        self,
    ):
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
        self.assertIs(routes.routes[447].handler_type, NativeFightPropertyHandler)

        # Select a counter operation from the active native enum instead of
        # assuming a particular property ID has no transaction side effects.
        rows = property_registry()
        counter_ids = sorted(
            identity
            for identity, row in rows.items()
            if row.get("application_branch") == "counter"
        )
        self.assertTrue(counter_ids, "native property catalog has no counter row")
        counter_id = counter_ids[0]
        with patch(
            "wakfu_server.combat_equipment_retained_lifecycle.preflight",
            return_value=True,
        ):
            result = validate_effect(
                _effect((counter_id, 0)),
                1,
                {},
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container={"present": True},
            )
        self.assertEqual("supported", result.status, result.reasons)
        self.assertEqual("fight.property", result.operation_id)
        self.assertEqual({"property_id": counter_id}, result.parameters[0])

        # A recognized branch that needs live transaction state stays deferred
        # even though the factory has an executor method for that branch.
        special_ids = sorted(
            identity
            for identity, row in rows.items()
            if row.get("application_branch") != "counter"
        )
        self.assertTrue(special_ids, "native property catalog has no special row")
        with patch(
            "wakfu_server.combat_equipment_retained_lifecycle.preflight",
            return_value=True,
        ):
            deferred = validate_effect(
                _effect((special_ids[0], 0)),
                1,
                {},
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container={"present": True},
            )
        self.assertEqual("unknown", deferred.status)
        self.assertIn("native_fight_property_context", deferred.reasons[0])

        # A well-shaped but non-enum operand is malformed/unsupported rather
        # than an unknown context, preserving the handler's native lookup.
        with patch(
            "wakfu_server.combat_equipment_retained_lifecycle.preflight",
            return_value=True,
        ):
            rejected = validate_effect(
                _effect((2**30, 0)),
                1,
                {},
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container={"present": True},
            )
        self.assertEqual("unsupported", rejected.status)
        self.assertIn("native_fight_property_context", rejected.reasons[0])

    def test_missing_authority_defers_property_execution(self):
        callback = lambda *_args, **_kwargs: None
        factory = NativeEffectRuntimeFactory(
            effects={},
            state_catalog={"states": {}, "effects": {}},
            characteristic_registry={"effects": {}},
            action_id=1,
            contexts=NativeRuntimeContexts(*([callback] * 13)),
        )
        routes, provider = factory.equipment_operation_capability()
        with patch(
            "wakfu_server.combat_equipment_retained_lifecycle.preflight",
            return_value=True,
        ):
            result = validate_effect(
                _effect((69, 0)),
                1,
                {},
                runtime_bindings=routes,
                criteria_capability=provider,
                retained_container={"present": True},
            )
        self.assertEqual("unknown", result.status)
        self.assertIn("native_fight_property_context", result.reasons[0])
