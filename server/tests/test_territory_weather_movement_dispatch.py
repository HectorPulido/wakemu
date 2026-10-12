import ast
from pathlib import Path
import unittest
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def production_function(name, namespace):
    tree = ast.parse(SERVER_SOURCE.read_text())
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
    return namespace[name]


def refresh_bonuses(character, packets):
    character["territory_stat_bonuses"] = {}
    character["_published_territory_stat_bonuses"] = {}
    return packets


class TerritoryWeatherMovementDispatchTests(unittest.TestCase):
    def test_only_an_accepted_region_transition_requests_a_weather_snapshot(self):
        from wakfu_server import territory_cells

        transition = production_function("territory_weather_region_changed", {})
        old = {"x": 10, "y": 20, "z": 0}
        new = {"x": 11, "y": 20, "z": 0}
        with patch.object(
            territory_cells,
            "region_at",
            side_effect=lambda map_id, x, y: 100 if x == 10 else 200,
        ):
            self.assertTrue(transition(1134, old, new))
        with patch.object(territory_cells, "region_at", return_value=100):
            self.assertFalse(transition(1134, old, new))

    def test_unknown_destination_does_not_invent_or_publish_weather(self):
        from wakfu_server import territory_cells

        transition = production_function("territory_weather_region_changed", {})
        old = {"x": 10, "y": 20}
        new = {"x": 11, "y": 20}

        def region_at(map_id, x, y):
            if x == 11:
                raise ValueError("unknown region")
            return 100

        with patch.object(territory_cells, "region_at", side_effect=region_at):
            self.assertFalse(transition(1134, old, new))

    def test_same_region_movement_keeps_ecology_without_repeating_weather(self):
        from wakfu_server import ecology_context, territory_bonuses, territory_weather

        sent = []
        namespace = {
            "STORE": object(),
            "OPEN_PLANTING": False,
            "send": lambda connection, service, opcode, payload: sent.append(
                (opcode, payload)
            ),
            "record": lambda **entry: None,
            "send_native_planting_bonus": lambda *_args: None,
            "WORLD": SimpleNamespace(lock=RLock(), players={}),
            "REGIONAL_BONUSES": SimpleNamespace(
                mark_context_refreshed=lambda *_args: None
            ),
        }
        publish = production_function("send_planting_context", namespace)
        with (
            patch.object(ecology_context, "packet", return_value=(12789, b"ecology")),
            patch.object(
                territory_bonuses,
                "refresh_world",
                side_effect=lambda store, character: refresh_bonuses(character, []),
            ),
        ):
            with patch.object(territory_weather, "context") as weather:
                publish(
                    "peer",
                    {
                        "id": 3,
                        "map_id": 1134,
                        "instance_id": 17,
                        "x": 10,
                        "y": 20,
                        "z": 0,
                    },
                    include_weather=False,
                )
        self.assertEqual(sent, [(12789, b"ecology")])
        weather.assert_not_called()

    def test_same_region_satisfaction_change_publishes_stats_without_weather(self):
        from wakfu_server import ecology_context, territory_bonuses, territory_weather

        sent = []
        store = object()
        character = {
            "id": 3,
            "map_id": 1134,
            "instance_id": 17,
            "x": 10,
            "y": 20,
            "z": 0,
        }
        publish = production_function(
            "send_planting_context",
            {
                "STORE": store,
                "OPEN_PLANTING": False,
                "send": lambda connection, service, opcode, payload: sent.append(
                    (opcode, payload)
                ),
                "record": lambda **entry: None,
                "send_native_planting_bonus": lambda *_args: None,
                "WORLD": SimpleNamespace(lock=RLock(), players={}),
                "REGIONAL_BONUSES": SimpleNamespace(
                    mark_context_refreshed=lambda *_args: None
                ),
            },
        )
        with (
            patch.object(ecology_context, "packet", return_value=(12789, b"ecology")),
            patch.object(
                territory_bonuses,
                "refresh_world",
                side_effect=lambda store, character: refresh_bonuses(
                    character, [(13046, b"updated-characteristics")]
                ),
            ) as bonuses,
            patch.object(territory_weather, "context") as weather,
        ):
            publish("peer", character, include_weather=False)
        bonuses.assert_called_once()
        self.assertIs(bonuses.call_args.args[0], store)
        self.assertEqual(bonuses.call_args.args[1], character)
        self.assertEqual(
            sent, [(12789, b"ecology"), (13046, b"updated-characteristics")]
        )
        weather.assert_not_called()

    def test_normal_world_movement_checks_region_after_validation_and_commit(self):
        tree = ast.parse(SERVER_SOURCE.read_text())
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        movement = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 13331 and loaded"
        )
        calls = [
            node
            for node in ast.walk(movement)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "territory_weather_region_changed"
        ]
        self.assertEqual(len(calls), 1)
        commit_index = next(
            index
            for index, node in enumerate(movement.body)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "commit"
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "movement_state"
        )
        call_index = next(
            index
            for index, node in enumerate(movement.body)
            if any(child is calls[0] for child in ast.walk(node))
        )
        self.assertGreater(call_index, commit_index)


if __name__ == "__main__":
    unittest.main()
