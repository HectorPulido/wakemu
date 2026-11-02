"""Public storage hook ordering and shipped movement/recovery wiring."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server import fight_store
from wakfu_server import dungeon_optional_ground_items as ground


class StopOwner(Exception):
    pass


class OptionalGroundHookTests(unittest.TestCase):
    def capture_create(self, preflight):
        events = []
        db = SimpleNamespace(execute=lambda *args: events.append("account"))

        class Store:
            @contextmanager
            def connection(self):
                yield db

            def lock_character(self, *args):
                events.append("owner")
                raise StopOwner

        with self.assertRaises(StopOwner):
            fight_store.create(
                Store(),
                54,
                "lease",
                76,
                before_owner_lock=(lambda db: events.append("run"))
                if preflight
                else None,
            )
        return events

    def test_optional_run_precedes_actual_create_account_and_owner_locks(self):
        self.assertEqual(self.capture_create(True), ["run", "account", "owner"])

    def test_main_default_create_keeps_its_original_owner_order(self):
        self.assertEqual(self.capture_create(False), ["account", "owner"])

    def test_transition_poll_is_scoped_and_movement_uses_real_step_adapter(self):
        source = Path(__file__).parents[1].joinpath("local_game_server.py").read_text()
        tree = ast.parse(source)
        poll = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "deliver_dungeon_transitions"
        )
        self.assertTrue(
            any(
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and "e.encounter_scope='main'" in n.value
                for n in ast.walk(poll)
            )
        )
        self.assertTrue(
            any(
                isinstance(n, ast.If)
                and "scene_enabled" in ast.unparse(n.test)
                and any(
                    isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and c.func.attr == "publish_pending"
                    for c in ast.walk(n)
                )
                for n in ast.walk(poll)
            )
        )
        self.assertIn("step_on_target(", source)
        self.assertIn("publish_native_scene(WORLD", source)

    def test_unrelated_maps_and_non_target_movement_have_no_db_access(self):
        store = SimpleNamespace(
            connection=lambda: self.fail("Non-target movement queried DB")
        )
        self.assertFalse(ground.scene_enabled(1134))
        self.assertTrue(ground.scene_enabled(910))
        self.assertIsNone(
            ground.step_on_target(
                store, None, 54, "lease", 76, dict(map_id=1134, x=21, y=51, z=0)
            )
        )
        self.assertIsNone(
            ground.step_on_target(
                store, None, 54, "lease", 76, dict(map_id=910, x=20, y=51, z=0)
            )
        )

    def test_farmer_override_is_exclusive_to_one_reviewed_seed_action(self):
        rule = ground.rules()[0]
        self.assertEqual(ground.use_criterion(rule), "")
        self.assertEqual(rule["native_use_criterion"], "GetCraftLevel(64) >= 35")
        for altered in (dict(rule, action_id=7953), dict(rule, item_reference=11388)):
            with self.assertRaises(ValueError):
                ground.use_criterion(altered)


if __name__ == "__main__":
    unittest.main()
