"""Exercise the actual owned-native bootstrap wrapper without loading the server."""
import ast
from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _extract_bootstrap(source):
    module = ast.parse(source.read_text(encoding="utf8"))
    node = next(
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name == "owned_native_bootstrap"
    )
    isolated = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {}
    exec(compile(isolated, str(source), "exec"), namespace)
    return namespace["owned_native_bootstrap"]


class _Database:
    def __init__(self, progress):
        self.progress = progress
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if "combat_fights" in sql:
            row = {"fighting": False}
        elif "FROM dungeon_instances" in sql:
            row = {"context_route_key": "jalato_normal", "context_policy_version": 4}
        elif "SELECT catalog_hash FROM dungeon_room_runs" in sql:
            row = {"catalog_hash": "d" * 64} if self.progress is not None else None
        elif "current_room, status FROM dungeon_room_runs" in sql:
            row = self.progress
        else:
            raise AssertionError(f"Unexpected bootstrap query: {sql}")
        return Mock(fetchone=Mock(return_value=row))


class _Store:
    def __init__(self, db):
        self.db = db
        self.connections = 0

    @contextmanager
    def connection(self):
        self.connections += 1
        yield self.db


class OwnedNativeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 701,
            "map_id": 12344,
            "instance_id": 144115188075855873,
            "x": 4,
            "y": -12,
            "z": 0,
        }
        self.sources = [
            {"map_id": 12344, "id": 90},
            {"map_id": 12344, "id": 91},
            {"map_id": 1086, "id": 92},
        ]

    def _modules(self):
        from wakfu_server import (
            dungeon_object_states,
            dungeon_runtime,
            generic_transports,
            native_transports,
        )
        from wakfu_server.maps import dungeon_context

        return (
            dungeon_object_states,
            dungeon_context,
            dungeon_runtime,
            generic_transports,
            native_transports,
        )

    def test_ordinary_native_bootstrap_keeps_existing_behavior(self):
        (
            dungeon_object_states,
            dungeon_context,
            dungeon_runtime,
            generic_transports,
            native_transports,
        ) = self._modules()
        ordinary = ((13974, b"native"),)
        with patch.object(
            native_transports, "bootstrap", return_value=ordinary
        ) as native, patch.object(
            dungeon_context, "for_instance"
        ) as context, patch.object(
            dungeon_runtime.dungeon_runtime_config, "pinned_configuration"
        ) as pinned, patch.object(
            dungeon_object_states, "packets"
        ) as states:
            for source in (SERVER,):
                bootstrap = _extract_bootstrap(source)
                with patch.dict(
                    bootstrap.__globals__,
                    {
                        "STORE": object(),
                        "is_dungeon_run": lambda _instance: False,
                        "native_transports": native_transports,
                    },
                ):
                    self.assertEqual(
                        ordinary, bootstrap(self.character, feature="unchanged")
                    )

        self.assertEqual(1, native.call_count)
        native.assert_called_with(self.character, feature="unchanged")
        context.assert_not_called()
        pinned.assert_not_called()
        states.assert_not_called()

    def test_active_run_uses_pinned_configuration_and_filters_native_catalog(self):
        (
            dungeon_object_states,
            dungeon_context,
            dungeon_runtime,
            generic_transports,
            native_transports,
        ) = self._modules()
        for source in (SERVER,):
            with self.subTest(source=str(source)):
                db = _Database({"current_room": 2, "status": "active"})
                store = _Store(db)
                config = {"topology": {"asset_map_id": 12344, "rooms": []}}
                base_packets = ((13974, b"native"),)
                room_packets = ((72001, b"room-state"),)
                with patch.object(
                    native_transports, "bootstrap", return_value=base_packets
                ) as native, patch.object(
                    dungeon_context, "for_instance", return_value={"policy": "pinned"}
                ) as context, patch.object(
                    dungeon_runtime.dungeon_runtime_config,
                    "pinned_configuration",
                    return_value=config,
                ) as pinned, patch.object(
                    generic_transports, "_CATALOG", self.sources
                ), patch.object(
                    dungeon_object_states, "packets", return_value=room_packets
                ) as states:
                    bootstrap = _extract_bootstrap(source)
                    with patch.dict(
                        bootstrap.__globals__,
                        {
                            "STORE": store,
                            "is_dungeon_run": lambda instance: instance
                            == self.character["instance_id"],
                            "native_transports": native_transports,
                        },
                    ):
                        result = bootstrap(self.character)

                self.assertEqual(base_packets + room_packets, result)
                native.assert_called_once_with(
                    self.character, dungeon_context={"policy": "pinned"}
                )
                context.assert_called_once_with(
                    store, self.character["instance_id"], fight_in_progress=False
                )
                pinned.assert_called_once_with(
                    db, "jalato_normal", 4, expected_plan_hash="d" * 64
                )
                self.assertEqual(2, store.connections)
                self.assertEqual(4, len(db.queries))
                self.assertEqual(
                    [self.sources[0], self.sources[1]], states.call_args.args[1]
                )
                self.assertEqual(
                    {
                        "map_id": 12344,
                        "instance_id": self.character["instance_id"],
                        "unlocked_room": 2,
                        "completed": False,
                    },
                    states.call_args.kwargs,
                )

    def test_active_run_without_committed_room_progress_fails_closed(self):
        (
            dungeon_object_states,
            dungeon_context,
            dungeon_runtime,
            generic_transports,
            native_transports,
        ) = self._modules()
        for source in (SERVER,):
            with self.subTest(source=str(source)):
                db = _Database(None)
                store = _Store(db)
                with patch.object(
                    native_transports, "bootstrap", return_value=()
                ), patch.object(
                    dungeon_context, "for_instance", return_value={}
                ), patch.object(
                    dungeon_runtime.dungeon_runtime_config,
                    "pinned_configuration",
                    return_value={"topology": {}},
                ), patch.object(
                    generic_transports, "_CATALOG", self.sources
                ), patch.object(
                    dungeon_object_states, "packets"
                ) as states:
                    bootstrap = _extract_bootstrap(source)
                    with patch.dict(
                        bootstrap.__globals__,
                        {
                            "STORE": store,
                            "is_dungeon_run": lambda _instance: True,
                            "native_transports": native_transports,
                        },
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "no committed room progress"
                        ):
                            bootstrap(self.character)
                states.assert_not_called()


if __name__ == "__main__":
    unittest.main()
