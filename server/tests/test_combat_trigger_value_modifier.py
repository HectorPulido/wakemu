import unittest
from wakfu_server.combat_trigger_value_modifier import (
    modify_runner_amount,
    NativeRunnerAmount,
    mutate_triggering_runner,
)
from wakfu_server.combat_final_modifier import final_modifier_source
from types import SimpleNamespace


class TriggerValueModifierTests(unittest.TestCase):
    def test_damage_auxiliary_modes_replace_separate_fields_and_survive_c(self):
        runner = NativeRunnerAmount(1, 2, rng=lambda: 0.5, value=100)
        self.assertEqual(runner.owner, "eXt")
        for mode in (5, 6):
            runner.mutate(mode, 20, False)
            runner.mutate(mode, 7, False)
        runner.set_calculated(55)
        self.assertEqual(
            (runner.value, runner.additional_mastery, runner.additional_resistance),
            (55, 7, 7),
        )
        runner.mutate(6, -3, True)
        self.assertEqual(runner.additional_resistance, -3)

    def test_scoped_source_identity_and_nested_reaction_do_not_leak(self):
        first = NativeRunnerAmount(1, 1013, rng=lambda: 0.5, value=100)
        second = NativeRunnerAmount(2, 1013, rng=lambda: 0.5, value=50)

        def source(runner):
            return SimpleNamespace(
                uid=runner.uid, effect_action_id=runner.family, runner_modifier=runner
            )

        with final_modifier_source(source(first)):
            mutate_triggering_runner(1, 25, False)
            with final_modifier_source(source(second)):
                mutate_triggering_runner(1, 10, False)
            mutate_triggering_runner(1, 5, False)
        self.assertEqual((first.value, second.value), (130, 60))
        self.assertFalse(mutate_triggering_runner(1, 100, True))
        with final_modifier_source(
            SimpleNamespace(uid=99, effect_action_id=1013, runner_modifier=first)
        ):
            with self.assertRaises(ValueError):
                mutate_triggering_runner(1, 1, False)

    def test_original_sticky_notification_flag_is_not_application_cancellation(self):
        runner = NativeRunnerAmount(1, 1013, rng=lambda: 0.5, value=100)
        runner.mutate(1, 0, True)
        runner.mutate(1, 10, True)
        self.assertEqual(runner.value, 10)
        self.assertTrue(runner.notification_suppressed)
        runner.finish_application()
        self.assertFalse(runner.notification_suppressed)
        runner.set_applied(7)
        runner.mutate(1, 25, False)
        self.assertEqual(runner.value, 32)

    def test_calculation_overwrites_amount_and_new_clone_does_not_share_it(self):
        runner = NativeRunnerAmount(1, 1013, rng=lambda: 0.5, value=0)
        runner.mutate(1, 10, True)
        runner.set_calculated(100)
        clone = NativeRunnerAmount(2, 1013, rng=lambda: 0.5)
        self.assertEqual(runner.value, 100)
        self.assertEqual(clone.value, 0)

    def test_original_damage_healing_and_characteristic_contracts(self):
        rows = [
            ("eXt", 100, 0, 25, False, 125),
            ("eXt", 100, 0, 25, True, 25),
            ("eXt", 100, 1, -150, False, 0),
            ("eXt", 100, 1, 17, True, 17),
            ("eXs", 3, 0, -50, False, 1),
            ("eXs", -3, 0, 50, True, -2),
            ("eWW", 100, 0, 25, False, 125),
            ("eWW", 100, 0, 25, True, 100),
            ("eWW", 100, 1, 17, True, 17),
            ("eWW", 100, 1, -150, False, -50),
        ]
        for owner, current, mode, value, replace, expected in rows:
            with self.subTest(owner=owner, mode=mode, replace=replace):
                self.assertEqual(
                    modify_runner_amount(
                        owner, current, mode, value, replace, rng=lambda: 0.99
                    ),
                    expected,
                )

    def test_stochastic_damage_and_deterministic_healing_are_distinct(self):
        self.assertEqual(
            modify_runner_amount("eXt", 3, 0, 50, True, rng=lambda: 0.1), 2
        )
        self.assertEqual(
            modify_runner_amount("eXt", 3, 0, 50, True, rng=lambda: 0.9), 1
        )

        def no_draw():
            raise AssertionError("Healing must not sample probabilistic rounding")

        self.assertEqual(modify_runner_amount("eXs", 3, 0, 50, True, rng=no_draw), 1)

    def test_base_noop_and_unimplemented_auxiliary_contracts_remain_explicit(self):
        self.assertEqual(modify_runner_amount("Qe", 7, 1, 100, True, rng=None), 7)
        for owner, mode in [("eWu", 4), ("eXt", 5), ("eXt", 6)]:
            with self.assertRaises(ValueError):
                modify_runner_amount(owner, 7, mode, 100, True, rng=None)
