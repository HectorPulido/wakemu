"""Opt-in recovery searches retain finite, independent native witnesses."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_monster_validation_budget import MonsterValidationBudgetTests, validator


class MonsterRecoveryWitnessSearchTests(MonsterValidationBudgetTests):
    def recovery_case(self, cells, limit=1, **caps):
        fixtures = []

        def build_fixture(*args, **kwargs):
            fixtures.append((args, kwargs))
            return self.fake_fight()

        with patch.dict(sys.modules, self.modules), patch.object(
            validator, "fixture", side_effect=build_fixture
        ):
            result = validator.run_case(
                100, 5, 123, 1, cells, limit, recovery_search=True, **caps
            )
        return result, fixtures

    def test_failed_first_distance_does_not_exhaust_later_witness(self):
        self.prepare_error = ValueError("first target rejected")
        self.failures_remaining = 2
        result, fixtures = self.recovery_case([(-7, -7), (-6, -7)])
        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(fixtures), 2)
        self.assertEqual(result["successful_targets"][0]["enemy_cell"], [-6, -7])

    def test_caster_failure_does_not_exhaust_empty_cell_target(self):
        self.prepare_error = ValueError("occupied target rejected")
        self.failures_remaining = 2
        original = self.fake_fight

        def with_empty_cell():
            context = original()
            context[0].walkable = {(-7, -7), (-6, -7)}
            context[0].actors[7].position = (-7, -7)
            return context

        with patch.object(self, "fake_fight", side_effect=with_empty_cell):
            result, fixtures = self.recovery_case([(-7, -7), (-6, -7)])
        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(fixtures), 1)
        self.assertIsNone(result["successful_targets"][0]["target_id"])
        self.assertEqual(result["attempts"], 3)

    def test_attempt_cap_stops_before_additional_cast_or_fixture(self):
        self.prepare_error = ValueError("rejected")
        result, fixtures = self.recovery_case(
            [(-7, -7), (-6, -7), (-5, -7)],
            recovery_attempt_cap=1,
        )
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(result["search_budget"]["attempt_cap"], 1)

    def test_scene_cap_counts_initialization_failures(self):
        with patch.dict(sys.modules, self.modules), patch.object(
            validator, "fixture", side_effect=ValueError("initialization failed")
        ) as fixture:
            result = validator.run_case(
                100,
                5,
                123,
                1,
                [(-7, -7), (-6, -7), (-5, -7)],
                1,
                recovery_search=True,
                recovery_scene_cap=2,
            )
        self.assertEqual(fixture.call_count, 2)
        self.assertEqual(result["scenes_attempted"], 2)
        self.assertEqual(result["attempts"], 0)

    def test_round_robin_gives_preparation_scene_a_bounded_probe(self):
        self.prepare_error = ValueError("rejected")
        recipe = {"kind": "fixture_case"}
        self.modules["monster_pending_scenarios"].scenario_recipes = lambda *args: [
            recipe
        ]
        result, fixtures = self.recovery_case(
            [(-7, -7), (-6, -7), (-5, -7)],
            recovery_scene_cap=2,
        )
        self.assertEqual([f[1]["scenario"] for f in fixtures], [recipe, None])
        self.assertEqual([f[0][2] for f in fixtures], [(-7, -7), (-7, -7)])
        self.assertEqual(result["scenes_attempted"], 2)

    def test_invalid_or_nonrecovery_caps_are_rejected(self):
        for recovery, attempt, scene in [
            (False, 1, None),
            (True, 0, None),
            (True, True, None),
            (True, None, -1),
        ]:
            with self.subTest(values=(recovery, attempt, scene)), self.assertRaises(
                ValueError
            ):
                validator.validate_recovery_caps(recovery, attempt, scene)

    def test_native_failed_hook_diagnostic_is_retained(self):
        error = ValueError("rejected")
        error.native_casting_result = "twV"
        error.native_casting_diagnostic = {"criterion_cell": False}
        self.prepare_error = error
        result, _ = self.recovery_case([(-7, -7)])
        self.assertEqual(result["status"], "pending")
        self.assertEqual(
            result["cast_diagnostics"][0]["details"]["native_casting_result"], "twV"
        )
        self.assertEqual(
            result["cast_diagnostics"][0]["details"]["native_casting_diagnostic"],
            {"criterion_cell": False},
        )


class MonsterRecoveryPolicyPropagationTests(unittest.TestCase):
    def test_reference_api_passes_opt_in_to_native_case_runner(self):
        for recovery_search in (False, True):
            with self.subTest(recovery_search=recovery_search), patch.object(
                validator, "run_case", return_value={"status": "validated"}
            ) as run:
                result = validator.evaluate_reference_cases(
                    {"ref": 872, "min_level": 75, "max_level": 75},
                    lambda reference, level: [{"spell_id": 1582, "spell_level": level}],
                    (),
                    2,
                    recovery_search=recovery_search,
                )
                self.assertEqual(result, [{"status": "validated"}])
                self.assertIs(
                    run.call_args.kwargs.get("recovery_search", False), recovery_search
                )

    def test_cli_advertises_recovery_as_optional_flag(self):
        import contextlib
        import io

        output = io.StringIO()
        with patch.object(
            sys, "argv", ["validator", "--help"]
        ), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                validator.main()
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--recovery-search", output.getvalue())


class NativeRecoveryFootprintTests(unittest.TestCase):
    def fight(self, radius=1, enemy_radius=0):
        import types

        return types.SimpleNamespace(
            actors={
                -200: types.SimpleNamespace(position=(0, 0, 0), physical_radius=radius),
                7: types.SimpleNamespace(
                    position=(1, 0, 0), physical_radius=enemy_radius
                ),
            }
        )

    def test_large_native_caster_excludes_adjacent_enemy_placement(self):
        fight = self.fight()
        self.assertTrue(validator.native_scene_footprints_overlap(fight, -200, 7))
        cells = [(1, 0, 0), (2, 0, 0), (0, 2, 0), (4, 0, 0)]
        candidates = validator.native_nonoverlapping_enemy_cells(
            fight, -200, 7, cells, 1
        )
        self.assertEqual(set(candidates), {(2, 0, 0), (0, 2, 0)})
        self.assertEqual(fight.actors[7].position, (1, 0, 0))
        self.assertEqual(fight.actors[-200].physical_radius, 1)

    def test_both_actual_actor_radii_are_respected_and_budget_is_finite(self):
        fight = self.fight(enemy_radius=1)
        candidates = validator.native_nonoverlapping_enemy_cells(
            fight, -200, 7, [(2, 0, 0), (3, 0, 0), (4, 0, 0)], 1, limit=1
        )
        self.assertEqual(candidates, [(3, 0, 0)])

    def test_zero_radius_actor_preserves_adjacent_native_witness(self):
        fight = self.fight(radius=0)
        self.assertFalse(validator.native_scene_footprints_overlap(fight, -200, 7))

    def test_requested_target_identity_diagnostic_is_preserved(self):
        error = ValueError("NPC target identity differs from native cell target")
        error.native_target_diagnostic = {
            "requested_target_id": 7,
            "native_target_id": -200,
        }
        diagnostic = validator.native_witness_diagnostic(error, (1, 0, 0), 7, (1, 0, 0))
        self.assertEqual(
            diagnostic["details"]["native_target_diagnostic"],
            error.native_target_diagnostic,
        )


if __name__ == "__main__":
    unittest.main()
