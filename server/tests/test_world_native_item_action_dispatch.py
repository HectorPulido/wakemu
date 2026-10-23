"""Keep new item classifiers transparent to unrelated native 13220 families."""
import ast
from pathlib import Path
import unittest

from postgres_case import PostgresCase


class WorldNativeItemActionDispatchSourceTests(unittest.TestCase):
    def test_router_keeps_the_legacy_fallback_after_new_action_families(self):
        path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        self.assertEqual(source.count("elif opcode == 13220 and loaded:"), 1)
        route = source.index("elif opcode == 13220 and loaded:")
        legacy = source.index("request_action_class(body)", route)
        new_routes = [
            source.index(token, route)
            for token in (
                "simple_item_action_class(body)",
                "open_item_recustomization(body)",
                "play_inventory_emote(body)",
                "use_inventory_teleport(body)",
                "play_inventory_script(body)",
                "spawn_inventory_test_actor(body)",
                "mark_inventory_destination(body)",
                "scenario_item_action_class(body)",
                "book_action_class(body)",
                "random_item_action_class(body)",
            )
        ]
        self.assertEqual(new_routes, sorted(new_routes))
        self.assertLess(new_routes[-1], legacy)
        helper_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(
            {
                "open_item_recustomization",
                "play_inventory_emote",
                "use_inventory_teleport",
                "mark_inventory_destination",
            }.issubset(helper_names)
        )


class WorldNativeItemClassifierPostgresTests(PostgresCase):
    def test_real_unhandled_bii_actions_with_20_and_22_byte_suffixes_are_deferred(self):
        import struct
        from wakfu_server.book_item_actions import action_class as book_class
        from wakfu_server.emote_item_actions import action_class as emote_class
        from wakfu_server.haven_bag_furniture_knowledge import _rules
        from wakfu_server.item_teleports import action_class as teleport_class
        from wakfu_server.random_item_actions import action_class as random_class
        from wakfu_server.simple_item_actions import action_class as simple_class
        from wakfu_server.script_item_actions import action_class as script_class
        from wakfu_server.scenario_item_actions import action_class as scenario_class
        from wakfu_server.neutrality_item_actions import (
            action_class as neutrality_class,
        )
        from wakfu_server.item_test_spawns import action_class as developer_class
        from wakfu_server.captain_map_item_actions import action_class as captain_class
        from wakfu_server.journal_part_item_actions import action_class as journal_class
        from wakfu_server.world_marker_item_actions import action_class as marker_class

        row = next(
            item for item in _rules().values() if item.get("use_action_class") == "bIi"
        )
        action = row["use_action_id"]
        self.assertIsInstance(action, int)
        for size in (20, 22):
            with self.subTest(body_size=size):
                body = struct.pack(">iq", action, 987654321) + bytes(size - 12)
                self.assertEqual(len(body), size)
                for classifier in (
                    simple_class,
                    emote_class,
                    teleport_class,
                    book_class,
                    random_class,
                    script_class,
                    scenario_class,
                    neutrality_class,
                    developer_class,
                    captain_class,
                    journal_class,
                    marker_class,
                ):
                    self.assertIsNone(classifier(body))


if __name__ == "__main__":
    unittest.main()
