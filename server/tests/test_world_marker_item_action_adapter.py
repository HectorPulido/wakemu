"""Exercise the production World marker adapter without duplicating its logic."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch


class WorldMarkerItemActionAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        cls.source = cls.path.read_text()
        cls.tree = ast.parse(cls.source, filename=str(cls.path))
        cls.helper = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "mark_inventory_destination"
        )

    def _helper(self, *, in_fight=False, private=False):
        character = {
            "id": 77,
            "account_id": 4,
            "map_id": 527,
            "instance_id": 82,
            "x": 12,
            "y": 19,
            "z": 0,
            "direction": 3,
        }
        events = []
        context = {
            "STORE": object(),
            "account_id": 4,
            "generation": "lease-A",
            "character": character,
            "fight": object() if in_fight else None,
            "combat_session": None,
            "active_private_session": lambda: {"instance_id": 82} if private else None,
            "record": lambda **event: events.append(event),
        }
        module = ast.Module(body=[self.helper], type_ignores=[])
        exec(compile(module, str(self.path), "exec"), context)
        return context["mark_inventory_destination"], character, events, context

    def test_unclassified_body_is_transparent(self):
        from wakfu_server import world_marker_item_actions

        helper, _character, events, _context = self._helper()
        with patch.object(
            world_marker_item_actions, "action_class", return_value=None
        ), patch.object(world_marker_item_actions, "use") as use:
            self.assertFalse(helper(b"unrelated"))
        use.assert_not_called()
        self.assertEqual(events, [])

    def test_marker_validation_records_without_world_or_character_mutation(self):
        from wakfu_server import world_marker_item_actions

        helper, character, events, context = self._helper(in_fight=True)
        original = dict(character)
        result = {
            "actor_id": 77,
            "source_reference": 16942,
            "consumed": 0,
            "marker": {"map_id": 527, "x": 8, "y": 9},
        }
        body = b"native marker body"
        with patch.object(
            world_marker_item_actions, "action_class", return_value="bHA"
        ), patch.object(world_marker_item_actions, "use", return_value=result) as use:
            self.assertTrue(helper(body))

        use.assert_called_once_with(
            context["STORE"],
            4,
            "lease-A",
            77,
            body,
            in_fight=True,
            native_map_id=527,
            private_context=False,
        )
        self.assertEqual(character, original)
        self.assertEqual(
            events,
            [
                {
                    "event": "inventory_destination_marked",
                    "actor_id": 77,
                    "source_reference": 16942,
                    "consumed": 0,
                    "marker": {"map_id": 527, "x": 8, "y": 9},
                }
            ],
        )

    def test_private_context_is_forwarded_for_domain_rejection(self):
        from wakfu_server import world_marker_item_actions

        helper, _character, _events, context = self._helper(private=True)
        with patch.object(
            world_marker_item_actions, "action_class", return_value="bHA"
        ), patch.object(
            world_marker_item_actions, "use", side_effect=ValueError("private")
        ) as use:
            with self.assertRaisesRegex(ValueError, "private"):
                helper(b"marker")
        self.assertTrue(use.call_args.kwargs["private_context"])
        self.assertEqual(use.call_args.kwargs["native_map_id"], 527)

    def test_router_calls_marker_after_spawn_handler_and_before_generic_domains(self):
        route = self.source.index("elif opcode == 13220 and loaded:")
        ordered = [
            self.source.index(token, route)
            for token in (
                "spawn_inventory_test_actor(body)",
                "mark_inventory_destination(body)",
                "scenario_item_action_class(body)",
                "request_action_class(body)",
            )
        ]
        self.assertEqual(ordered, sorted(ordered))


if __name__ == "__main__":
    unittest.main()
