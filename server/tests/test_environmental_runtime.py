"""Bulk lifecycle and matching contracts for all supported event families."""
import unittest

from wakfu_server.objectives import environmental_runtime as runtime


class EnvironmentalRuntimeTests(unittest.TestCase):
    def test_profile_requires_frozen_family_scope_and_positive_authority(self):
        profile = dict(
            profile_key="qualified-policy",
            version=1,
            family="monster_defeat",
            mode="solo",
            map_id=2,
            region_id=3,
            duration_ms=1000,
            anchor_ms=2000,
            level_min=1,
            level_max=230,
            authority="qualified-source-consumer",
            catalog_revision="fixture-revision",
            source_sha256="a" * 64,
        )
        objective = dict(
            objective_key="defeat", family="monster_defeat", required_quantity=2
        )
        self.assertEqual(runtime.validate_profile(profile, [objective]), (objective,))
        for change in (
            {"region_id": None},
            {"source_sha256": ""},
            {"mode": "competitive"},
            {"version": True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                runtime.validate_profile(dict(profile, **change), [objective])
        with self.assertRaises(ValueError):
            runtime.validate_profile(
                profile, [dict(objective, family="resource_plant")]
            )

    def test_anchored_windows_expire_offline_and_do_not_reward_gaps(self):
        rule = dict(duration_ms=1000, anchor_ms=2000, recurrence_period_ms=5000)
        expected = {
            1999: None,
            2000: (0, 2000, 3000),
            2999: (0, 2000, 3000),
            3000: None,
            6999: None,
            7000: (1, 7000, 8000),
            12000: (2, 12000, 13000),
        }
        for clock, window in expected.items():
            with self.subTest(clock=clock):
                self.assertEqual(runtime.cycle_window(clock, **rule), window)
        self.assertEqual(runtime.remaining_ms(8000, 7999), 1)
        self.assertEqual(runtime.remaining_ms(8000, 9000), 0)
        self.assertIsNone(runtime.cycle_window(3000, duration_ms=1000, anchor_ms=2000))
        for change in (
            {"duration_ms": True},
            {"recurrence_period_ms": 999},
            {"anchor_ms": -1},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                runtime.cycle_window(2000, **dict(rule, **change))

    def test_all_families_require_exact_spawn_and_native_action(self):
        kinds = dict(
            monster_defeat="monster_defeated",
            group_defeat="group_defeated",
            resource_collect="resource_collected",
            resource_plant="resource_planted",
            monster_destroy="monster_destroyed",
        )
        for family, kind in kinds.items():
            with self.subTest(family=family):
                entity = "resource" if family.startswith("resource") else "monster"
                objective = dict(
                    family=family,
                    required_quantity=2,
                    target_reference=40,
                    action_id=3,
                    resource_step=2,
                )
                fact = dict(
                    kind=kind,
                    entity_kind=entity,
                    entity_id=90,
                    reference=40,
                    action_id=3,
                    quantity=50,
                )
                stage_field = (
                    "after_step" if family == "resource_plant" else "before_step"
                )
                fact[stage_field] = 2
                member = dict(entity_kind=entity, entity_id=90, reference=40)
                self.assertEqual(
                    runtime.objective_increment(objective, fact, membership=member), 1
                )
                self.assertEqual(
                    runtime.objective_increment(objective, fact, membership=None), 0
                )
                for key, value in (
                    ("entity_id", 91),
                    ("reference", 41),
                    ("entity_kind", "unrelated"),
                ):
                    self.assertEqual(
                        runtime.objective_increment(
                            objective, fact, membership=dict(member, **{key: value})
                        ),
                        0,
                    )
                for key, value in (
                    ("action_id", 4),
                    (stage_field, 1),
                    ("kind", "monster_collected"),
                ):
                    self.assertEqual(
                        runtime.objective_increment(
                            objective, dict(fact, **{key: value}), membership=member
                        ),
                        0,
                    )

    def test_completion_requires_all_goals_and_caps_without_yield_multiplication(self):
        goals = [
            dict(objective_key="kill", required_quantity=2),
            dict(objective_key="plant", required_quantity=1),
        ]
        self.assertFalse(runtime.complete([], {}))
        self.assertFalse(runtime.complete(goals, {"kill": 2}))
        self.assertTrue(runtime.complete(goals, {"kill": 2, "plant": 1}))
        self.assertEqual(runtime.advance_progress(1, 50, 2), 2)
        with self.assertRaises(ValueError):
            runtime.advance_progress(1, -1, 2)


if __name__ == "__main__":
    unittest.main()
