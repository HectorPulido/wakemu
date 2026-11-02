"""Configured-family paid scenes preserve their plan and avoid Tower mutation."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server import native_scene_start as scene_start


class TroolSceneProfileTests(unittest.TestCase):
    def rule_and_config(self):
        plan = dict(
            rooms=[
                dict(
                    order=1,
                    monsters=[
                        dict(ref_id=ref, count=1) for ref in (2440, 2441, 2442, 2443)
                    ],
                )
            ]
        )
        rule = dict(
            policy_id="reviewed-trool-test",
            map_id=483,
            definition_id=13,
            template_id=16,
            source_id=33318,
            gates=[],
            competitive_ceiling=95,
            profile=dict(
                kind="configured_native_roster_v1",
                compiled_plan_sha256=scene_start.digest(plan),
            ),
        )
        config = dict(
            compiled_plan=plan,
            topology=dict(
                asset_map_id=483,
                native_scene_start=dict(policy_id=rule["policy_id"], source_id=33318),
            ),
        )
        return rule, config

    def test_configured_profile_is_exact_and_never_reads_binary_state_choices(self):
        rule, config = self.rule_and_config()
        with patch(
            "wakfu_server.native_catalog.record",
            side_effect=AssertionError("Fixed roster must not synthesize states"),
        ), patch.object(
            scene_start.secrets,
            "randbelow",
            side_effect=AssertionError("Fixed roster must not roll Tower choices"),
        ):
            profile = scene_start._profile(rule)
        self.assertEqual(
            profile,
            dict(
                schema="configured_native_roster_scene_v1",
                compiled_plan_sha256=scene_start.digest(config["compiled_plan"]),
            ),
        )
        scene_start._validate_profile(rule, profile)
        for changed in (
            dict(profile, native_states=[dict(id=5279, level=1)]),
            dict(profile, compiled_plan_sha256="0" * 64),
            {},
        ):
            with self.subTest(profile=changed), self.assertRaises(ValueError):
                scene_start._validate_profile(rule, changed)
        for malformed in ("", None, "f" * 63, "z" * 64):
            with self.subTest(digest=malformed), self.assertRaises(ValueError):
                scene_start._profile(
                    dict(
                        rule,
                        profile=dict(
                            kind="configured_native_roster_v1",
                            compiled_plan_sha256=malformed,
                        ),
                    )
                )

    def test_receipt_unlocks_exact_plan_without_tower_states_glyphs_or_door_packets(
        self,
    ):
        rule, config = self.rule_and_config()
        profile = scene_start._profile(rule)
        row = dict(
            policy_sha256=scene_start.digest(rule),
            policy=rule,
            map_id=483,
            policy_id=rule["policy_id"],
            profile=profile,
        )
        db = SimpleNamespace(execute=lambda *_: SimpleNamespace(fetchone=lambda: row))
        run = dict(definition_id=13, template_id=16, instance_id=99)
        with patch.object(scene_start, "_rules", return_value=[rule]), patch.object(
            scene_start, "_published_rule", return_value=rule
        ):
            self.assertFalse(scene_start.can_spawn(config["topology"]))
            projected = scene_start.project_configuration(db, run, config)
            self.assertTrue(scene_start.can_spawn(projected["topology"]))
            room = dict(order=1, cells=[[-61, -76, 0]], anchor=[-61, -76, 0])
            self.assertEqual(scene_start.scene_room(projected["topology"], room), room)
            self.assertEqual(scene_start.packets(projected["topology"]), ())
            scene_start.validate_movement(
                config["topology"],
                dict(start_position=dict(x=-61, y=-76, z=0), steps=[]),
            )
            changed = deepcopy(config)
            changed["compiled_plan"]["rooms"][0]["monsters"][0]["count"] = 2
            with self.assertRaisesRegex(ValueError, "pinned roster"):
                scene_start.project_configuration(db, run, changed)
