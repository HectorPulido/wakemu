import struct
import unittest
import ast
import json
from pathlib import Path
from unittest.mock import patch

from wakfu_server.global_tasks import GlobalTasks
from wakfu_server import territory_weather
from wakfu_server import territory_weather_forecast
from wakfu_server.territory_weather import publish_to_world


class TerritoryWeatherPublicationTests(unittest.TestCase):
    @staticmethod
    def payload(weather_id):
        return struct.pack(
            ">qb6fi", 123456789, -7, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, weather_id
        )

    def test_routes_only_to_the_exact_native_map_instance_and_region(self):
        # Native grid cells in map 1134: (-4,-7) belongs to 79201 and
        # (-3,3) belongs to 79001. Same-map sessions in another territory
        # must not receive this weather snapshot.
        players = [
            {"id": 1, "map_id": 1134, "instance_id": 17, "x": -72, "y": -126},
            {"id": 2, "map_id": 1134, "instance_id": 17, "x": -54, "y": 54},
            {"id": 3, "map_id": 1134, "instance_id": 18, "x": -72, "y": -126},
            {"id": 4, "map_id": 1135, "instance_id": 17, "x": -72, "y": -126},
            {"id": 5, "map_id": 1134, "instance_id": 17, "x": 10000, "y": 10000},
        ]

        class FakeWorld:
            def __init__(self):
                self.sent = []

            def snapshot(self):
                return [dict(player) for player in players]

            def live_identity(self, *, character_id):
                player = next((p for p in players if p["id"] == character_id), None)
                return None if player is None else (character_id + 100, dict(player))

            def send_to(self, character_id, generation, opcode, body):
                self.sent.append((character_id, generation, opcode, body))
                return True

        world = FakeWorld()
        payload = self.payload(3)
        event = dict(
            map_id=1134,
            instance_id=17,
            region_id=79201,
            revision=2,
            weather="STORM",
            native_payload=payload,
        )
        self.assertEqual(publish_to_world(world, event), 1)
        self.assertEqual(world.sent, [(1, 101, 13948, payload)])

    def test_rechecks_live_position_after_snapshot_and_does_not_send_stale_region(self):
        player = {
            "id": 1,
            "map_id": 1134,
            "instance_id": 17,
            "x": -72,
            "y": -126,
        }

        class MovingWorld:
            def __init__(self):
                self.sent = []

            def snapshot(self):
                return [dict(player)]

            def live_identity(self, *, character_id):
                # The session crossed the native territory boundary after the
                # membership snapshot but before publication.
                return 9, dict(player, x=-54, y=54)

            def send_to(self, *args):
                self.sent.append(args)
                return True

        world = MovingWorld()
        event = dict(
            map_id=1134,
            instance_id=17,
            region_id=79201,
            revision=2,
            weather="STORM",
            native_payload=self.payload(3),
        )
        self.assertEqual(publish_to_world(world, event), 0)
        self.assertEqual(world.sent, [])

    def test_current_session_send_failure_raises_for_durable_outbox_retry(self):
        player = {
            "id": 1,
            "map_id": 1134,
            "instance_id": 17,
            "x": -72,
            "y": -126,
        }

        class FailedWorld:
            def snapshot(self):
                return [dict(player)]

            def live_identity(self, *, character_id):
                return 9, dict(player)

            def send_to(self, *_args):
                return False

        with self.assertRaisesRegex(OSError, "current session"):
            publish_to_world(
                FailedWorld(),
                dict(
                    map_id=1134,
                    instance_id=17,
                    region_id=79201,
                    revision=2,
                    weather="STORM",
                    native_payload=self.payload(3),
                ),
            )

    def test_rejects_event_with_payload_enum_mismatch(self):
        event = dict(
            map_id=1134,
            instance_id=17,
            region_id=79201,
            revision=2,
            weather="LIGHT",
            native_payload=self.payload(3),
        )
        with self.assertRaisesRegex(ValueError, "Inconsistent"):
            publish_to_world(object(), event)

    def test_global_scheduler_allows_weather_tick_with_occurrence_deduplication(self):
        calls = []
        tasks = GlobalTasks({"territory_weather_tick": lambda: calls.append("tick")})
        first = tasks.run("territory_weather_tick", "territory_weather_tick:minute-1")
        replay = tasks.run("territory_weather_tick", "territory_weather_tick:minute-1")
        self.assertFalse(first["deduplicated"])
        self.assertTrue(replay["deduplicated"])
        self.assertEqual(calls, ["tick"])
        with self.assertRaises(ValueError):
            GlobalTasks({"arbitrary_weather": lambda: None})

    def test_tick_applies_transitions_then_retries_outbox_publication(self):
        event = dict(
            map_id=1134,
            instance_id=17,
            region_id=79201,
            revision=3,
            weather="STORM",
            native_payload=self.payload(3),
        )
        calls = []

        def advance(_store, *, limit):
            calls.append(("advance", limit))
            return [event]

        def publish_pending(_store, callback, *, limit):
            calls.append(("pending", limit))
            callback(event)
            return 1

        forecast_event = dict(
            map_id=1134,
            instance_id=17,
            region_id=79201,
            policy_version=4,
        )

        def publish_forecasts(_store, callback, *, limit):
            calls.append(("forecast_pending", limit))
            callback(forecast_event)
            return 1

        with patch.object(
            territory_weather, "advance_due", side_effect=advance
        ), patch.object(
            territory_weather, "publish_pending", side_effect=publish_pending
        ), patch.object(
            territory_weather,
            "publish_to_world",
            side_effect=lambda _world, _event: calls.append(("publish",)) or 1,
        ), patch.object(
            territory_weather_forecast,
            "publish_pending",
            side_effect=publish_forecasts,
        ), patch.object(
            territory_weather_forecast,
            "publish_to_world",
            side_effect=lambda _store, _world, _event: calls.append(
                ("forecast_publish",)
            )
            or 1,
        ):
            result = territory_weather.tick_weather(object(), object(), limit=7)
        self.assertEqual(
            result, {"advanced": 1, "published": 1, "forecast_published": 1}
        )
        self.assertEqual(
            calls,
            [
                ("advance", 7),
                ("pending", 7),
                ("publish",),
                ("forecast_pending", 7),
                ("forecast_publish",),
            ],
        )

    def test_server_callback_and_cron_configuration_are_connected_to_weather_tick(self):
        server_root = Path(__file__).resolve().parents[1]
        source = ast.parse((server_root / "local_game_server.py").read_text())
        main = next(
            node
            for node in source.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "main"
        )
        callback = next(
            node
            for node in main.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "tick_territory_weather"
        )
        store, world = object(), object()
        namespace = {"STORE": store, "WORLD": world}
        exec(
            compile(
                ast.Module(body=[callback], type_ignores=[]),
                "local_game_server.py",
                "exec",
            ),
            namespace,
        )
        tick_result = {"advanced": 0, "published": 0, "forecast_published": 0}
        with patch.object(
            territory_weather, "tick_weather", return_value=tick_result
        ) as tick:
            self.assertEqual(namespace[callback.name](), tick_result)
        tick.assert_called_once_with(store, world)

        registrations = [
            node
            for node in main.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "callbacks"
                for target in node.targets
            )
        ]
        self.assertEqual(len(registrations), 1)
        registration_index = main.body.index(registrations[0])
        conditional_registration = main.body[registration_index + 1]
        self.assertIsInstance(conditional_registration, ast.If)
        registration_code = compile(
            ast.Module(
                body=[registrations[0], conditional_registration], type_ignores=[]
            ),
            "local_game_server.py",
            "exec",
        )
        for mode in ("inline", "external", "disabled"):
            namespace = dict(
                ECOLOGY_MODE=mode,
                flush_positions=object(),
                tick_territory_weather=object(),
            )
            exec(registration_code, namespace)
            self.assertEqual(
                "territory_weather_tick" in namespace["callbacks"], mode == "inline"
            )
        config = json.loads((server_root / "cron-service/config.json").read_text())
        task = config["tasks"]["territory_weather_tick"]
        # Compose delegates ecology to the external worker; a simultaneous cron
        # weather loop must stay disabled. Inline still registers its callback.
        self.assertFalse(task["enabled"])
        self.assertEqual(
            task["url"], "http://world:18081/test/tasks/territory_weather_tick"
        )

    def test_validated_same_map_movement_rebootstraps_weather_only_on_region_change(
        self,
    ):
        server_root = Path(__file__).resolve().parents[1]
        source = ast.parse((server_root / "local_game_server.py").read_text())
        helper = next(
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "territory_weather_region_changed"
        )
        namespace = {}
        exec(
            compile(
                ast.Module(body=[helper], type_ignores=[]),
                "local_game_server.py",
                "exec",
            ),
            namespace,
        )
        old_position = {"x": -72, "y": -126}
        same_region = {"x": -71, "y": -125}
        adjacent_region = {"x": -54, "y": 54}
        self.assertFalse(namespace[helper.name](1134, old_position, same_region))
        self.assertTrue(namespace[helper.name](1134, old_position, adjacent_region))
        # Unknown cells must not cause a guessed weather update.
        self.assertFalse(
            namespace[helper.name](1134, old_position, {"x": 10000, "y": 10000})
        )


if __name__ == "__main__":
    unittest.main()
