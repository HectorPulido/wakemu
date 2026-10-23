"""Pure admission checks for the existing native damage implementation."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_equipment_owned_operation_parsers import parse
from wakfu_server.combat_equipment_damage_capability import (
    execution_context,
    verify_initialized,
)


class EquipmentDamageCapabilityTests(unittest.TestCase):
    def effect(self, parameters, **changes):
        return dict(
            effect_class=1,
            parameters=parameters,
            _capability_level=4,
            native_effect_flags=[],
            native_localization_enabled=False,
            **changes
        )

    def test_classic_and_percent_modes_keep_native_parameter_authority(self):
        for parameters, expected in (([10, 2], 18), ([1000, 0, 0, 0], 1000)):
            parsed, needs, dependencies, error = parse(self.effect(parameters), {}, {})
            self.assertIsNone(error)
            self.assertEqual(parsed["base"], expected)
            self.assertIn("native_damage_execution", needs)
            self.assertIn("native_runner_lifecycle", needs)
            self.assertEqual(dependencies, ())
        for kind in range(1, 7):
            parsed, needs, _, error = parse(self.effect([25, 0, 3, 0, kind, 0]), {}, {})
            self.assertIsNone(error)
            self.assertNotIn("base", parsed)
            self.assertEqual(parsed["base_parameter"], 25)
            self.assertEqual(parsed["base_kind"], kind)
            self.assertIn("native_damage_hp_and_rounding", needs)
        parsed, _, _, error = parse(self.effect([9, 0, 3, 0, 255, 0]), {}, {})
        self.assertIsNone(error)
        self.assertEqual(parsed["base_kind"], 0)

    def test_malformed_shapes_flags_and_missing_providers_do_not_gain_admission(self):
        from wakfu_server.combat_damage_handler import NativeDamageHandler

        for parameters in ([], [1], [1, 0, 4, 0], [-1, 0], [1, 0] * 4):
            self.assertIsNotNone(parse(self.effect(parameters), {}, {})[3])
        for flags in ([True], [2, 2], [999]):
            effect = self.effect([1, 0])
            effect["native_effect_flags"] = flags
            self.assertIsNotNone(parse(effect, {}, {})[3])
        effect = self.effect([1, 0])
        effect["native_effect_flags"] = [8]
        self.assertIn("native_damage_ordering_identity", parse(effect, {}, {})[1])
        self.assertFalse(
            execution_context(SimpleNamespace(), SimpleNamespace(handler_type=object))
        )
        self.assertIsNone(
            execution_context(
                SimpleNamespace(contexts=SimpleNamespace()),
                SimpleNamespace(handler_type=NativeDamageHandler),
            )
        )
        self.assertFalse(verify_initialized(SimpleNamespace(), object(), {}))
