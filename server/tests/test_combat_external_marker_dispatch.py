import ast
import unittest
from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _function(tree, name):
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name} definition, got {len(matches)}")
    return matches[0]


def _calls(function, attribute):
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


class ExternalMarkerDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVER.read_text(encoding="utf8")
        cls.tree = ast.parse(cls.source)

    def test_join_and_world_resync_replay_only_current_map_markers(self):
        join = _function(self.tree, "join_world")
        snapshots = _calls(join, "snapshots")
        self.assertTrue(snapshots)
        self.assertTrue(
            any(
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "EXTERNAL_FIGHT_MARKERS"
                for node in snapshots
            )
        )

        refresh = _function(self.tree, "refresh_owned_world_after_spectating")
        self.assertTrue(
            any(
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "EXTERNAL_FIGHT_MARKERS"
                for node in _calls(refresh, "snapshots")
            )
        )

    def test_marker_changes_are_drained_from_current_shared_fight_only(self):
        drain = _function(self.tree, "drain_shared_combat")
        self.assertTrue(
            any(
                isinstance(node.func, ast.Name)
                and node.func.id == "publish_external_marker"
                for node in ast.walk(drain)
                if isinstance(node, ast.Call)
            )
        )
        publisher = _function(self.tree, "publish_external_marker")
        self.assertTrue(_calls(publisher, "emit_location"))
        self.assertTrue(
            any(
                keyword.arg == "exclude_sessions"
                for call in _calls(publisher, "emit_location")
                for keyword in call.keywords
            )
        )

    def test_initial_placement_captures_starter_world_cell_for_marker(self):
        self.assertIn(
            '"world_marker_cells": ((character["x"], character["y"]),)', self.source
        )
        self.assertIn("EXTERNAL_FIGHT_MARKERS = ExternalFightMarkers()", self.source)


if __name__ == "__main__":
    unittest.main()
