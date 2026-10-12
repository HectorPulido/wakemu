"""Production movement checkpoints must hydrate resource-only partitions."""
import ast
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import Mock
import unittest


class ResourceSceneDispatchTests(unittest.TestCase):
    def test_actual_scene_checkpoint_replays_resources_without_interactives(self):
        path = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(path.read_text())
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "sync_scene_world"
        )
        node.decorator_list = []
        character = dict(id=42, map_id=1385, instance_id=0, x=3, y=-21)
        resource = (13135, b"persisted-current-state")
        snapshots = Mock(return_value=[resource])
        sent = []
        ns = dict(
            loaded=True,
            character=character,
            fight=None,
            spectator_session=None,
            scene_sync=SimpleNamespace(poll=lambda *a: (), last_regions={(0, -2)}),
            time=SimpleNamespace(monotonic=lambda: 1),
            struct=struct,
            send=lambda peer, service, opcode, body: sent.append((opcode, body)),
            connection=object(),
            service="world",
            PLANTINGS=SimpleNamespace(snapshots=snapshots),
            publish_environment_scene=Mock(),
            is_dungeon_run=lambda _: False,
            record=Mock(),
            snapshot_ids=lambda _: [],
        )
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
        ns["sync_scene_world"]()
        self.assertEqual(sent[0], (12318, struct.pack(">ii", 3, -21)))
        self.assertIn(resource, sent)
        snapshots.assert_called_once_with(1385, 0, position=character)
        sent.clear()
        snapshots.reset_mock()
        ns["scene_sync"].last_regions = set()
        ns["sync_scene_world"]()
        self.assertEqual(sent, [])
        snapshots.assert_not_called()


if __name__ == "__main__":
    unittest.main()
