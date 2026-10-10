"""The actual background dispatchers must not fence an entire ecology tick."""

import ast
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from wakfu_server.performance_profiler import PROFILER


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


class EcologyDispatchCoordinationTests(unittest.TestCase):
    def exercise_dispatcher(self, name, module_name):
        tree = ast.parse(SERVER.read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        group_lock, harvest_lock = RLock(), RLock()
        players = [{"id": 7, "map_id": 1134, "instance_id": 0}]
        stop_calls, ticks = [], []

        def stopping(_seconds):
            stop_calls.append(True)
            return len(stop_calls) > 1

        def tick(_store, locations, previous, **arguments):
            # This assertion catches reintroduction of the original outer
            # fence, even if the per-operation helper still exists.
            self.assertFalse(group_lock._is_owned())
            self.assertFalse(harvest_lock._is_owned())
            self.assertEqual(locations, {(1134, 0)})
            for stage in ("observe", "attempt", "publish"):
                with arguments["coordination"](stage, 1134, 0) as facts:
                    self.assertTrue(group_lock._is_owned())
                    self.assertTrue(harvest_lock._is_owned())
                    self.assertEqual(facts, (players, {-9}))
                self.assertFalse(group_lock._is_owned())
                self.assertFalse(harvest_lock._is_owned())
            ticks.append(locations)
            return locations

        scope = {
            "PROFILER": PROFILER,
            "STOPPING": SimpleNamespace(wait=stopping),
            "COMBAT_GROUPS": SimpleNamespace(lock=group_lock),
            "HARVESTS": SimpleNamespace(lock=harvest_lock, targets={-9: 7}),
            "WORLD": SimpleNamespace(
                snapshot=lambda: list(players), emit_location=lambda *_: None
            ),
            "STORE": object(),
            "time": time,
            "record": lambda **fields: self.fail(str(fields)),
        }
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        with patch(module_name + ".tick", side_effect=tick), patch(
            "wakfu_server.combat_terrain.map_geometry", return_value={"edges": []}
        ), patch("wakfu_server.monster_wander.edge_index", return_value=({}, {})):
            scope[name]()
        self.assertEqual(ticks, [{(1134, 0)}])

    def test_reproduction_dispatch_releases_between_operations(self):
        self.exercise_dispatcher(
            "reproduce_monsters", "wakfu_server.monster_reproduction"
        )

    def test_maturation_dispatch_releases_between_operations(self):
        self.exercise_dispatcher("mature_monsters", "wakfu_server.monster_maturation")
