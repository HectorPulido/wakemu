import unittest

from wakfu_server.combat_equipment_owned_operation_parsers import parse


class EquipmentOwnedOperationParserTests(unittest.TestCase):
    def test_state_decurse_321_accepts_native_shapes_and_rejects_malformed_values(self):
        effect = {"effect_class": 321}
        for values, expected in (([3442], (3442, None)), ([3442, 7], (3442, 7))):
            with self.subTest(values=values):
                parameters, contexts, dependencies, error = parse(
                    effect, {"parameters": values}, {}
                )
                self.assertIsNone(error)
                self.assertEqual(
                    parameters, dict(reference=expected[0], reduction=expected[1])
                )
                self.assertEqual(
                    contexts,
                    (
                        "owned_state_removal_and_reapplication",
                        "native_runner_lifecycle",
                    ),
                )
                self.assertEqual(dependencies, ())

        for values in ([], [3442, 7, 1], [True], [3442, False]):
            with self.subTest(values=values):
                parameters, contexts, dependencies, error = parse(
                    effect, {"parameters": values}, {}
                )
                self.assertIsNone(parameters)
                self.assertEqual(contexts, ())
                self.assertEqual(dependencies, ())
                self.assertIsNotNone(error)

    def test_321_execution_parser_uses_the_same_parameter_contract(self):
        from wakfu_server.combat_state_decurse import NativeStateDecurseHandler
        from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution

        handler = object.__new__(NativeStateDecurseHandler)
        self.assertEqual(
            handler._parameters({"effect_class": 321}, {"parameters": [2288, 4]}),
            [2288, 4],
        )
        for values in ([2288, 4, 2], [2288, True], []):
            with self.subTest(values=values), self.assertRaises(
                UnsupportedEffectExecution
            ):
                handler._parameters({"effect_class": 321}, {"parameters": values})

    def test_dispel_421_validates_selection_variants_and_known_flags(self):
        for parameters in ([], [41], [421, 3]):
            for flags in ([], [17], [3, 17], [5], [6]):
                with self.subTest(parameters=parameters, flags=flags):
                    parsed, contexts, dependencies, error = parse(
                        {"effect_class": 421, "native_effect_flags": flags},
                        {"parameters": parameters},
                        {},
                    )
                    self.assertIsNone(error)
                    self.assertEqual(
                        parsed, {"selection_parameters": tuple(parameters)}
                    )
                    self.assertEqual(
                        contexts,
                        ("native_dispel_retention", "native_runner_lifecycle"),
                    )
                    self.assertEqual(dependencies, ())

        for parameters, flags in (
            ([41, 3, 4], []),
            ([True], []),
            ([41], [999]),
            ([41], [17, 17]),
            ([41], [False]),
        ):
            with self.subTest(parameters=parameters, flags=flags):
                parsed, contexts, dependencies, error = parse(
                    {"effect_class": 421, "native_effect_flags": flags},
                    {"parameters": parameters},
                    {},
                )
                self.assertIsNone(parsed)
                self.assertEqual(contexts, ())
                self.assertEqual(dependencies, ())
                self.assertIsNotNone(error)

    def test_healing_25_keeps_flat_signed_and_masked_native_contracts(self):
        for parameters, expected in (
            ([10, 0], 10),
            ([10, 0, 3, 0], 10),
            ([-3, 0], -3),
        ):
            with self.subTest(parameters=parameters):
                parsed, contexts, dependencies, error = parse(
                    {
                        "effect_class": 25,
                        "_capability_level": 1,
                        "parameters": parameters,
                    },
                    {"parameters": parameters},
                    {},
                )
                self.assertIsNone(error)
                self.assertEqual(parsed["base"], expected)
                self.assertEqual(
                    contexts, ("native_healing_execution", "native_runner_lifecycle")
                )
                self.assertEqual(dependencies, ())

        for effect, profile in (
            (
                {
                    "effect_class": 25,
                    "_capability_level": 1,
                    "parameters": [10, 0, 4, 0],
                },
                {"parameters": [10, 0, 4, 0]},
            ),
            (
                {"effect_class": 25, "_capability_level": True, "parameters": [10, 0]},
                {"parameters": [10, 0]},
            ),
        ):
            with self.subTest(effect=effect):
                parsed, contexts, dependencies, error = parse(effect, profile, {})
                self.assertIsNone(parsed)
                self.assertEqual(contexts, ())
                self.assertEqual(dependencies, ())
                self.assertIsNotNone(error)

    def test_far_healing_25_returns_source_spec_and_requires_live_hp_rng(self):
        parameters = [10, 0, 3, 0, 1, 0]
        parsed, contexts, dependencies, error = parse(
            {"effect_class": 25, "_capability_level": 1, "parameters": parameters},
            {"parameters": parameters},
            {},
        )
        self.assertIsNone(error)
        self.assertEqual(parsed["base_parameter"], 10)
        self.assertEqual(parsed["base_kind"], 1)
        self.assertEqual(
            contexts,
            (
                "native_healing_execution",
                "native_runner_lifecycle",
                "native_healing_hp_and_rounding",
            ),
        )
        self.assertEqual(dependencies, ())

    def test_healing_specification_matches_interpreter_shape_and_arithmetic(self):
        from wakfu_server.combat_healing_parameters import (
            healing_parameter_specification,
            interpret_healing_parameters,
        )

        hp = dict(source_hp=300, source_max_hp=1000, target_hp=600, target_max_hp=2000)
        for parameters in (
            [10, 0],
            [10, 0, 3, 0],
            [10, 0, 3, 0, 0, 0],
            [10, 0, 3, 0, 1, 0],
        ):
            with self.subTest(parameters=parameters):
                spec = healing_parameter_specification(parameters, 1)
                interpreted = interpret_healing_parameters(
                    parameters, 1, hp_context=hp, rng=lambda: 0.99
                )
                self.assertEqual(
                    (spec["coefficient_mask"], spec["base_kind"], spec["level"]),
                    (
                        interpreted["coefficient_mask"],
                        interpreted["base_kind"],
                        interpreted["level"],
                    ),
                )
                if spec["base_kind"] == 0:
                    self.assertEqual(spec["base"], interpreted["base"])


if __name__ == "__main__":
    unittest.main()
