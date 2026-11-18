"""Sufokian storehouse discovery retains original entry and earned predecessor."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_controller as controller
from wakfu_server import (
    owned_story_generic_entry,
    dungeon_runtime_config,
    owned_story_mechanics,
)

ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
CONFIGURATION = json.loads(
    (ROOT / "wild-estate-sufokia-715.configuration.json").read_text()
)


class WildSufokiaDiscoveryTests(unittest.TestCase):
    def test_native_door_preserves_earned_treasure_gate_and_usable_exit(self):
        route = CONFIGURATION["route"]
        (
            source,
            group,
            action,
            effect,
            target,
            _,
        ) = owned_story_generic_entry.validate_route(route)
        self.assertEqual(
            (source["map_id"], source["id"], effect["action_reference"]),
            (711, 20448, 475),
        )
        self.assertEqual(effect["criterion"], "IsAchievementComplete(1677)")
        self.assertEqual(
            (target["map_id"], target["x"], target["y"], target["z"]), (715, 0, -1, 0)
        )
        self.assertEqual((group["cod"], group["coe"]), (0, 0))
        topology = CONFIGURATION["topology"]
        exit_row = next(
            r for r in topology["native_story_exits"] if r["source_id"] == 20538
        )
        self.assertEqual(exit_row["destination_id"], 1419)
        self.assertEqual(CONFIGURATION["compiled_plan"]["rooms"], [])

    def test_discovery_requires_the_exact_committed_native_entrance(self):
        selected = CONFIGURATION["topology"]["owned_story_controller"]
        route = CONFIGURATION["route"]
        admitted = dict(
            context_route_key=route["key"],
            context_policy_version=1,
            entry_map_id=711,
            entry_object_id=20448,
            entry_destination_id=475,
        )
        for changed in (
            None,
            "entry_map_id",
            "entry_object_id",
            "entry_destination_id",
        ):
            actual = deepcopy(admitted)
            if changed:
                actual[changed] += 1
            db = Mock()
            db.execute.return_value.fetchone.return_value = actual
            with self.subTest(changed=changed), patch.object(
                controller, "_scope", return_value=(selected, set())
            ), patch.object(
                dungeon_runtime_config,
                "pinned_configuration",
                return_value=CONFIGURATION,
            ), patch.object(
                owned_story_mechanics, "executor", return_value=Mock()
            ), patch.object(
                controller, "_settle", return_value={"applied": True}
            ) as settle:
                if changed:
                    with self.assertRaisesRegex(ValueError, "exact native entrance"):
                        controller.on_world_ready(
                            db, object(), dict(id=10, map_id=715, instance_id=20)
                        )
                    settle.assert_not_called()
                else:
                    controller.on_world_ready(
                        db, object(), dict(id=10, map_id=715, instance_id=20)
                    )
                    self.assertEqual(settle.call_args.kwargs["kind"], "world_ready")
                    self.assertEqual(
                        settle.call_args.kwargs["evidence"]["source_id"], 20448
                    )


if __name__ == "__main__":
    unittest.main()
