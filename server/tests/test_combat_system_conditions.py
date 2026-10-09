import unittest
from types import SimpleNamespace
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_system_conditions import (
    boolean_system_configuration,
    fight_is_pvp,
    fresh_system_configuration,
    system_predicate_catalog,
)


class SystemConditionsTests(unittest.TestCase):
    def fight(self):
        return SimpleNamespace(native_system_configuration=fresh_system_configuration())

    def test_native_boolean_defaults_include_true_and_false_values(self):
        fight = self.fight()
        boolean = {
            key: row
            for key, row in system_predicate_catalog()["configurations"].items()
            if row["boolean"]
        }
        self.assertEqual(len(boolean), 120)
        self.assertEqual({row["default"] for row in boolean.values()}, {False, True})
        for key, row in boolean.items():
            with self.subTest(key=key):
                self.assertIs(boolean_system_configuration(fight, key), row["default"])

    def test_actual_override_is_used_without_overwriting_native_default(self):
        fight = self.fight()
        self.assertFalse(boolean_system_configuration(fight, "beta.mode"))
        fight.native_system_configuration["overrides"]["beta.mode"] = True
        self.assertTrue(boolean_system_configuration(fight, "beta.mode"))
        self.assertFalse(
            system_predicate_catalog()["configurations"]["beta.mode"]["default"]
        )

    def test_unknown_name_false_precedes_configuration_authority_lookup(self):
        self.assertFalse(
            boolean_system_configuration(SimpleNamespace(), "no.such.native.key")
        )
        self.assertFalse(
            evaluate_condition(
                'GetBooleanSystemConfiguration("no.such.native.key")',
                ConditionContext({}),
            )
        )

    def test_known_missing_legacy_configuration_and_non_boolean_values_reject(self):
        with self.assertRaises(ValueError):
            boolean_system_configuration(SimpleNamespace(), "beta.mode")
        fight = self.fight()
        fight.native_system_configuration["overrides"]["beta.mode"] = 0
        with self.assertRaises(ValueError):
            boolean_system_configuration(fight, "beta.mode")
        non_boolean = next(
            key
            for key, row in system_predicate_catalog()["configurations"].items()
            if not row["boolean"]
        )
        with self.assertRaises(ValueError):
            boolean_system_configuration(fight, non_boolean)

    def test_pvp_uses_full_native_category_table_including_duels(self):
        for key, row in system_predicate_catalog()["fight_models"].items():
            with self.subTest(model=row["name"]):
                self.assertIs(fight_is_pvp(int(key)), row["is_pvp"])
        self.assertTrue(fight_is_pvp(65))  # Native DUEL category, not fcz.fVT().
        self.assertTrue(fight_is_pvp(23))  # ARENA also has DUEL category.
        self.assertFalse(fight_is_pvp(2))
        self.assertFalse(fight_is_pvp(None))
        with self.assertRaises(ValueError):
            fight_is_pvp(127)

    def test_predicates_support_native_boolean_and_numeric_routes(self):
        fight = self.fight()
        context = ConditionContext(
            {},
            pvp_query=lambda: fight_is_pvp(65),
            boolean_system_configuration_query=lambda key: boolean_system_configuration(
                fight, key
            ),
        )
        self.assertTrue(evaluate_condition("IsPvp()", context))
        self.assertTrue(evaluate_condition("IsPvp() == 0", context))
        self.assertTrue(
            evaluate_condition("IsPvp(123) == 0", context)
        )  # eOL ignores arguments.
        self.assertFalse(
            evaluate_condition('GetBooleanSystemConfiguration("beta.mode")', context)
        )
        self.assertTrue(
            evaluate_condition(
                'GetBooleanSystemConfiguration("beta.mode") == -1', context
            )
        )

    def test_wrong_signature_missing_callback_and_wrong_boolean_reject(self):
        for expression in (
            "GetBooleanSystemConfiguration()",
            "GetBooleanSystemConfiguration(1)",
            'GetBooleanSystemConfiguration("beta.mode", "other")',
            "IsPvp()",
            'GetBooleanSystemConfiguration("beta.mode")',
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression, ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsPvp()", ConditionContext({}, pvp_query=lambda: 0))

    def test_fresh_fight_serializes_explicit_default_policy_without_live_configuration(
        self,
    ):
        from wakfu_server.combat_state import Actor, Fight

        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        fight = Fight(
            77,
            actors,
            {value.position for value in actors},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.assertEqual(
            fight.native_system_configuration, fresh_system_configuration()
        )
        self.assertFalse(boolean_system_configuration(fight, "beta.mode"))
