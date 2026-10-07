import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import ecology_context, territory_weather, territory_weather_forecast


SERVER_ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = SERVER_ROOT / "local_game_server.py"


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


class PlantingWeatherDispatchTests(unittest.TestCase):
    def test_production_plantings_wires_the_required_resolver_and_current_provider(
        self,
    ):
        tree = ast.parse(SERVER_SOURCE.read_text())
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "PLANTINGS"
                for target in node.targets
            )
        )
        self.assertIsInstance(assignment.value, ast.Call)
        self.assertIsInstance(assignment.value.func, ast.Name)
        self.assertEqual(assignment.value.func.id, "Plantings")
        resolver_arg = next(
            keyword.value
            for keyword in assignment.value.keywords
            if keyword.arg == "probability_context"
        )
        self.assertIsInstance(resolver_arg, ast.Call)
        self.assertIsInstance(resolver_arg.func, ast.Name)
        self.assertEqual(resolver_arg.func.id, "planting_probability_resolver")
        provider_keyword = next(
            keyword
            for keyword in resolver_arg.keywords
            if keyword.arg == "profession_bonus"
        )
        open_policy_keyword = next(
            keyword
            for keyword in resolver_arg.keywords
            if keyword.arg == "open_test_policy"
        )
        self.assertIsInstance(open_policy_keyword.value, ast.Name)
        self.assertEqual(open_policy_keyword.value.id, "OPEN_PLANTING")
        provider = provider_keyword.value
        self.assertIsInstance(provider, ast.Name)
        self.assertEqual(provider.id, "current_planting_bonus")

    def test_join_publishes_current_ecology_then_exact_weather_payload(self):
        ecology = (12789, b"current-region-ecology")
        weather_payload = bytes(range(37))
        forecast_payload = b"\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00"
        weather_context = unittest.mock.Mock(
            return_value={
                "weather": "LIGHT",
                "native_payload": weather_payload,
                "region_id": 79301,
            }
        )
        sent = []
        records = []
        store = object()
        namespace = {
            "STORE": store,
            "OPEN_PLANTING": False,
            "send": lambda connection, service, opcode, payload: sent.append(
                (connection, service, opcode, payload)
            ),
            "record": lambda **entry: records.append(entry),
        }
        publish = production_function("send_planting_context", namespace)
        character = {
            "id": 41,
            "map_id": 1134,
            "instance_id": 7,
            "x": -39,
            "y": -72,
            "z": 47,
        }

        with patch.object(
            ecology_context, "packet", return_value=ecology
        ) as ecology_packet:
            with patch.object(territory_weather, "context", weather_context):
                with patch.object(
                    territory_weather_forecast,
                    "packet_for_territory",
                    return_value=forecast_payload,
                ) as forecast_context:
                    publish("peer", character)

        ecology_packet.assert_called_once_with(store, character, open_test_policy=False)
        weather_context.assert_called_once_with(store, character, x=-39, y=-72, z=47)
        forecast_context.assert_called_once_with(
            store, map_id=1134, instance_id=7, region_id=79301
        )
        self.assertEqual(
            sent,
            [
                ("peer", "world", 12789, ecology[1]),
                ("peer", "world", 13948, weather_payload),
                ("peer", "world", 13895, forecast_payload),
            ],
        )
        self.assertEqual(records, [])

    def test_bootstrap_sends_empty_clear_packet_for_region_without_forecast(self):
        sent = []
        clear = b"\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00"
        namespace = {
            "STORE": object(),
            "OPEN_PLANTING": False,
            "send": lambda connection, service, opcode, payload: sent.append(
                (opcode, payload)
            ),
            "record": lambda **_entry: None,
        }
        publish = production_function("send_planting_context", namespace)
        character = {
            "id": 41,
            "map_id": 1134,
            "instance_id": 18,
            "x": -39,
            "y": -72,
            "z": 47,
        }
        weather = {"native_payload": bytes(range(37)), "region_id": 79301}
        with patch.object(ecology_context, "packet", return_value=(12789, b"flora")):
            with patch.object(territory_weather, "context", return_value=weather):
                with patch.object(
                    territory_weather_forecast,
                    "packet_for_territory",
                    return_value=clear,
                ) as packet:
                    publish("peer", character)
        packet.assert_called_once_with(
            namespace["STORE"], map_id=1134, instance_id=18, region_id=79301
        )
        self.assertEqual(
            sent, [(12789, b"flora"), (13948, bytes(range(37))), (13895, clear)]
        )

    def test_same_region_update_can_omit_both_weather_frames(self):
        sent = []
        namespace = {
            "STORE": object(),
            "OPEN_PLANTING": False,
            "send": lambda connection, service, opcode, payload: sent.append(opcode),
            "record": lambda **_entry: None,
        }
        publish = production_function("send_planting_context", namespace)
        character = {
            "id": 41,
            "map_id": 1134,
            "instance_id": 7,
            "x": -39,
            "y": -72,
            "z": 47,
        }
        with patch.object(ecology_context, "packet", return_value=(12789, b"flora")):
            with patch.object(territory_weather, "context") as weather:
                with patch.object(
                    territory_weather_forecast, "packet_for_territory"
                ) as forecast:
                    publish("peer", character, include_weather=False)
        weather.assert_not_called()
        forecast.assert_not_called()
        self.assertEqual(sent, [12789])

    def test_missing_weather_logs_and_never_sends_fake_weather(self):
        ecology = (12789, b"current-region-ecology")
        sent = []
        records = []
        namespace = {
            "STORE": object(),
            "OPEN_PLANTING": False,
            "send": lambda connection, service, opcode, payload: sent.append(
                (opcode, payload)
            ),
            "record": lambda **entry: records.append(entry),
        }
        publish = production_function("send_planting_context", namespace)
        character = {
            "id": 42,
            "map_id": 1134,
            "instance_id": 8,
            "x": -39,
            "y": -72,
            "z": 47,
        }

        with patch.object(ecology_context, "packet", return_value=ecology):
            with patch.object(
                territory_weather,
                "context",
                side_effect=ValueError("Authoritative territory weather unavailable"),
            ):
                publish("peer", character)

        self.assertEqual(sent, [(12789, ecology[1])])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["event"], "territory_weather_unavailable")
        self.assertEqual(records[0]["map_id"], 1134)
        self.assertEqual(records[0]["instance_id"], 8)

    def test_incomplete_ecology_snapshot_is_not_replaced_with_zero_counts(self):
        sent = []
        records = []
        namespace = {
            "STORE": object(),
            "OPEN_PLANTING": False,
            "send": lambda connection, service, opcode, payload: sent.append(opcode),
            "record": lambda **entry: records.append(entry),
        }
        publish = production_function("send_planting_context", namespace)
        character = {
            "id": 42,
            "map_id": 1134,
            "instance_id": 18,
            "x": -39,
            "y": -72,
            "z": 47,
        }
        weather = {"native_payload": bytes(range(37)), "region_id": 79301}
        with patch.object(
            ecology_context, "packet", side_effect=ValueError("population incomplete")
        ), patch.object(
            territory_weather, "context", return_value=weather
        ), patch.object(
            territory_weather_forecast,
            "packet_for_territory",
            return_value=b"forecast-clear",
        ):
            publish("peer", character)
        self.assertEqual(sent, [13948, 13895])
        self.assertEqual(records[0]["event"], "planting_context_unavailable")

    def test_replay_skips_captured_ecology_and_weather_frames(self):
        sent = []
        frames = [
            {"direction": "in", "opcode": 12789},
            {"direction": "in", "opcode": 13948},
        ]
        replay = production_function(
            "replay", {"FRAMES": frames, "send": lambda *args: sent.append(args)}
        )
        replay("peer", 0, len(frames), 9)
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
