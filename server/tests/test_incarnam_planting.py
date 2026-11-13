"""Tutorial-specific planting cannot authorize other owners, seeds or maps."""
import unittest
from unittest.mock import patch
from wakfu_server.incarnam_planting import authorize_if_tutorial


class IncarnamPlantingTests(unittest.TestCase):
    def test_other_maps_preserve_normal_policy(self):
        self.assertFalse(authorize_if_tutorial(None, {"map_id": 1385}, {}, {}))

    def test_requires_exact_seed_tree_and_active_owned_quest(self):
        character = {"id": 12, "map_id": 1361, "instance_id": (1 << 62) + 12}
        seed = {"item_reference": 30938, "action_id": 13435, "resource_reference": 824}
        resource = {"resource_reference": 824}
        with patch(
            "wakfu_server.achievements.incarnam_resources.active", return_value=True
        ) as active:
            self.assertTrue(authorize_if_tutorial(None, character, seed, resource))
            active.assert_called_once_with(None, character, 5136)
            for mutation in (
                {"item_reference": 1},
                {"action_id": 1},
                {"resource_reference": 1},
            ):
                with self.assertRaises(ValueError):
                    authorize_if_tutorial(
                        None, character, dict(seed, **mutation), resource
                    )
            with self.assertRaises(ValueError):
                authorize_if_tutorial(None, character, seed, {"resource_reference": 1})
        with patch(
            "wakfu_server.achievements.incarnam_resources.active", return_value=False
        ):
            with self.assertRaises(ValueError):
                authorize_if_tutorial(None, character, seed, resource)

    def test_actual_owned_scene_and_active_mission_are_enforced(self):
        character = {"id": 12, "map_id": 1361, "instance_id": (1 << 62) + 12}
        seed = {"item_reference": 30938, "action_id": 13435, "resource_reference": 824}
        resource = {"resource_reference": 824}
        with patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value={"running": {5136: {}}},
        ):
            self.assertTrue(authorize_if_tutorial(None, character, seed, resource))
            with self.assertRaises(ValueError):
                authorize_if_tutorial(
                    None, dict(character, instance_id=(1 << 62) + 13), seed, resource
                )
        with patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value={"running": {5137: {}}},
        ):
            with self.assertRaises(ValueError):
                authorize_if_tutorial(None, character, seed, resource)


if __name__ == "__main__":
    unittest.main()
