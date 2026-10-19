"""Seasonal intents preserve exact native route and source authorization."""
import copy
import struct
import unittest
from unittest.mock import patch

from wakfu_server.objectives import seasonal_entry


class SeasonalEntryTests(unittest.TestCase):
    def setUp(self):
        self.route = dict(
            key="event",
            definition_id=100,
            template_id=8,
            entry_map_id=527,
            entry_object_id=99,
            destination_id=15,
            start_map_id=443,
            criterion="true",
        )
        self.destination = dict(
            destination_id=15,
            map_id=443,
            criterion="true",
            cyZ=8,
            native_altitude_walkable=True,
            cyX=0,
            cyW=0,
            item_reference=0,
        )
        self.source = dict(
            map_id=527,
            id=99,
            x=1,
            y=2,
            z=7,
            approach_mask=1,
            approach_orientation=0,
            approach_positions=[dict(x=1, y=3, z=0)],
            destinations=[self.destination],
        )
        self.actor = dict(map_id=527, instance_id=0, x=1, y=3, z=0)

    def test_native_approach_floor_may_differ_from_object_height(self):
        self.assertTrue(seasonal_entry.at_entrance(self.actor, self.source))
        for change in (dict(z=1), dict(x=2), dict(map_id=528), dict(instance_id=3)):
            with self.subTest(change=change):
                self.assertFalse(
                    seasonal_entry.at_entrance(dict(self.actor, **change), self.source)
                )

    def test_unreviewed_maps_are_not_admitted_by_seasonal_name(self):
        self.route["start_map_id"] = self.destination["map_id"] = 999
        self.assertIsNone(
            seasonal_entry.route_target(self.route, self.source, "revision")
        )

    def test_native_binding_and_supported_costs_are_required(self):
        for change in (
            dict(map_id=444),
            dict(criterion="false"),
            dict(cyZ=9),
            dict(native_altitude_walkable=False),
            dict(cyX=20),
        ):
            with self.subTest(change=change):
                source = copy.deepcopy(self.source)
                source["destinations"][0].update(change)
                self.assertIsNone(
                    seasonal_entry.route_target(self.route, source, "revision")
                )
        source = dict(self.source, id=98)
        self.assertIsNone(seasonal_entry.route_target(self.route, source, "revision"))

    def test_kwismas_interiors_are_reviewed_and_exterior_is_not(self):
        for map_id in (474, 476):
            self.route["start_map_id"] = self.destination["map_id"] = map_id
            self.assertIsNotNone(
                seasonal_entry.route_target(self.route, self.source, "revision")
            )
        self.route["start_map_id"] = self.destination["map_id"] = 472
        self.assertIsNone(
            seasonal_entry.route_target(self.route, self.source, "revision")
        )

    def test_item_prices_bind_native_route_for_transactional_payment(self):
        self.destination.update(cyW=1, item_reference=100)
        self.route["native_template_id"] = None
        self.assertIsNotNone(
            seasonal_entry.route_target(self.route, self.source, "revision")
        )

    def test_request_contains_server_owned_route_only(self):
        target = seasonal_entry.route_target(self.route, self.source, "revision")
        self.assertEqual(
            struct.unpack(">qiBi", seasonal_entry.request(target)), (99, 15, 0, 2)
        )
        self.assertEqual(target["catalog_revision"], "revision")
        self.assertEqual(target["criterion"], "true")

    def test_published_kwismas_workshop_index_exposes_entry_at_native_approach(self):
        # Exact active native identities, distinct from exterior map 472.
        import types
        import wakfu_server.objectives as package

        route = dict(
            key="legacy-map-474-27425-977",
            definition_id=1000474,
            template_id=1000474,
            native_template_id=122,
            entry_map_id=472,
            entry_object_id=27425,
            destination_id=977,
            start_map_id=474,
            criterion="IsAchievementComplete(836)",
        )
        source = dict(
            map_id=472,
            id=27425,
            x=6,
            y=-90,
            z=-78,
            approach_mask=1,
            approach_orientation=0,
            approach_positions=[dict(x=6, y=-90, z=-80)],
            destinations=[
                dict(
                    destination_id=977,
                    map_id=474,
                    criterion=route["criterion"],
                    cyZ=122,
                    native_altitude_walkable=True,
                    cyX=0,
                    cyW=0,
                    item_reference=0,
                )
            ],
        )
        actor = dict(map_id=472, instance_id=0, x=6, y=-90, z=-80)

        class Row:
            def __init__(self, value):
                self.value = value

            def fetchone(self):
                return self.value

            def fetchall(self):
                return self.value

        class Database:
            def execute(self, sql, params=None):
                if "FROM characters" in sql:
                    return Row(actor)
                if "FROM native_catalog_active" in sql:
                    return Row(dict(revision="revision"))
                if "FROM dungeon_runtime_configurations" in sql:
                    return Row([dict(route=route)])
                raise AssertionError(sql)

        rule = dict(key="content-v1.dungeon.1000474", title="Workshop")
        travel = types.SimpleNamespace(
            _document=lambda *args: [source],
            _eligible=lambda *args: {rule["key"]: rule},
        )
        with patch.object(package, "player_travel", travel, create=True):
            entries = seasonal_entry.actions(
                Database(), dict(character_id=1, account_id=1)
            )
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["target"]["destination_map_id"], 474)
            self.assertEqual(entries[0]["definition_key"], rule["key"])
            actor["z"] = -78
            self.assertEqual(
                seasonal_entry.actions(Database(), dict(character_id=1, account_id=1)),
                [],
            )

    def test_world_public_transport_dependency_imports_in_fresh_process(self):
        # Exercise the actual dispatcher's import statements. The legacy root
        # compatibility alias is needed for relative imports in this module.
        import ast
        import pathlib
        import subprocess
        import sys

        filename = pathlib.Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(filename.read_text())
        executor = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "execute_objectives_seasonal_entry"
        )
        imports = [
            node
            for node in ast.walk(executor)
            if isinstance(node, ast.ImportFrom)
            and any(alias.name == "generic_transports" for alias in node.names)
        ]
        self.assertEqual(len(imports), 1)
        script = (
            "from unittest.mock import patch\n"
            "from wakfu_server import native_catalog\n"
            'with patch.object(native_catalog, "load", return_value=[]):\n'
            + "    "
            + ast.unparse(imports[0])
            + "\n"
            + "    assert callable(generic_transports.resolve)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], text=True, capture_output=True, timeout=15
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_execution_re_resolves_full_immutable_target(self):
        target = seasonal_entry.route_target(self.route, self.source, "revision")
        action = dict(action_key="seasonal.enter.event", target=target)
        with patch.object(
            seasonal_entry,
            "actions",
            return_value=[dict(key=action["action_key"], target=target)],
        ):
            self.assertEqual(seasonal_entry.resolve(None, action), target)
            with self.assertRaises(ValueError):
                seasonal_entry.resolve(
                    None, dict(action, target=dict(target, source_id=2))
                )
        with patch.object(seasonal_entry, "actions", return_value=[]):
            with self.assertRaises(ValueError):
                seasonal_entry.resolve(None, action)


if __name__ == "__main__":
    unittest.main()
