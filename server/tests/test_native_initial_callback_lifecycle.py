import unittest
from native_initial_callback_lifecycle import source_plans


def fixture():
    native = dict(
        native_execution_mode=2,
        parameters=[99.0, 0.0],
        parameter0_by_level=[99, 99],
        criteria="GetFightCurrentTableTurn() >= 2",
    )
    subscription = dict(
        effect_class=330, target_masks=[None, None, None, None, None, [1001], None]
    )
    path = dict(
        spell_id=99,
        route_kind="native426_cast_callback",
        callback_effect_id=11,
        path=[["states", 8], ["effects", 10], ["effects", 11]],
        native_subscriptions=[subscription],
    )
    row = dict(
        ref=7,
        zero_range_owned_spell_ids=[99],
        native_initial_state_triples=[8, 1, 0],
        native_initialization=dict(source_paths=[path]),
    )
    return dict(
        schema="native-zero-range-constant-caller-index-v1",
        rows=[row],
        constant_native_callers=[
            dict(effect_id=11, family=426, spell_id=99, native_definition=native)
        ],
    )


class InitialCallbackPlanTests(unittest.TestCase):
    def test_normal_turn_plan_exact_native_path(self):
        plan = source_plans(fixture(), 7, 99)[0]
        self.assertTrue(plan["normal_turn_lifecycle_supported"])
        self.assertEqual(plan["callback_effect_id"], 11)
        self.assertFalse(plan["ordinary_cast_eligibility_override"])

    def test_nonowned_query_absent(self):
        self.assertEqual(source_plans(fixture(), 7, 100), [])

    def test_initial_constructor_must_own_path(self):
        x = fixture()
        x["rows"][0]["native_initial_state_triples"] = [9, 1, 0]
        with self.assertRaises(ValueError):
            source_plans(x, 7, 99)

    def test_unknown_event_stays_nonexecutable(self):
        x = fixture()
        x["rows"][0]["native_initialization"]["source_paths"][0][
            "native_subscriptions"
        ][0]["target_masks"][5] = [1010]
        self.assertFalse(source_plans(x, 7, 99)[0]["normal_turn_lifecycle_supported"])

    def test_nonconstant_spell_reference_rejected(self):
        x = fixture()
        x["constant_native_callers"][0]["native_definition"]["parameter0_by_level"] = [
            99,
            100,
        ]
        with self.assertRaises(ValueError):
            source_plans(x, 7, 99)

    def test_wrong_callback_family_rejected(self):
        x = fixture()
        x["constant_native_callers"][0]["family"] = 400
        with self.assertRaises(ValueError):
            source_plans(x, 7, 99)

    def test_plans_do_not_mutate_native_sources(self):
        x = fixture()
        plan = source_plans(x, 7, 99)[0]
        plan["source_path"].clear()
        self.assertEqual(len(source_plans(x, 7, 99)[0]["source_path"]), 3)


class InitialCallbackCLIIntegrationTests(unittest.TestCase):
    def test_cli_source_plan_remains_unexecuted_and_level_unknown(self):
        import json, tempfile
        from pathlib import Path
        from native_initial_callback_lifecycle import main

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "index.json"
            output = Path(directory) / "plan.json"
            source.write_text(json.dumps(fixture()))
            self.assertEqual(
                main(
                    [
                        "--index",
                        str(source),
                        "--reference",
                        "7",
                        "--spell",
                        "99",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result = json.loads(output.read_text())
            self.assertFalse(result["execution_verified"])
            self.assertFalse(result["admission"])
            self.assertIsNone(result["nested_spell_level"])
            self.assertTrue(result["plans"][0]["normal_turn_lifecycle_supported"])
            with self.assertRaises(SystemExit):
                main(
                    [
                        "--index",
                        str(source),
                        "--reference",
                        "7",
                        "--spell",
                        "99",
                        "--output",
                        str(output),
                    ]
                )

    def test_cli_rejects_unbounded_turn_budget(self):
        from native_initial_callback_lifecycle import main

        with self.assertRaises(SystemExit):
            main(
                [
                    "--index",
                    "unused",
                    "--reference",
                    "7",
                    "--spell",
                    "99",
                    "--max-boundaries",
                    "25",
                    "--output",
                    "unused",
                ]
            )
