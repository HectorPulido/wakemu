"""Production movement checkpoints must hydrate resource-only partitions."""
import ast
from contextlib import contextmanager
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import Mock
import unittest


class ResourceSceneDispatchTests(unittest.TestCase):
    def test_actual_scene_checkpoint_replays_resources_without_interactives(self):
        from wakfu_server.planting_runtime import Plantings
        from wakfu_server.planting import resource_packet

        rows = [
            dict(
                resource_uid=index + 1,
                map_id=1385,
                instance_id=0,
                x=x,
                y=0,
                z=0,
                resource_reference=3000,
                stage=1,
            )
            for index, x in enumerate((0, 19, 180, 360))
        ]

        class Store:
            queries = 0

            @contextmanager
            def connection(self):
                self.queries += 1
                yield self

            def execute(self, sql, parameters):
                self.asserted_scope = parameters
                return rows

        store = Store()
        plantings = Plantings(store)
        character = dict(id=42, map_id=1385, instance_id=0, x=180, y=0)
        path = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(path.read_text())
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "sync_scene_world"
        )
        node.decorator_list = []
        sent = []
        ns = dict(
            loaded=True,
            character=character,
            fight=None,
            spectator_session=None,
            scene_sync=SimpleNamespace(
                poll=lambda *a: (), last_regions=[(0, 0), (1, 0), (0, 0)]
            ),
            time=SimpleNamespace(monotonic=lambda: 1),
            struct=struct,
            send=lambda peer, service, opcode, body: sent.append((opcode, body)),
            connection=object(),
            service="world",
            PLANTINGS=plantings,
            publish_environment_scene=Mock(),
            is_dungeon_run=lambda _: False,
            record=Mock(),
            snapshot_ids=lambda _: [],
        )
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
        ns["sync_scene_world"]()
        self.assertEqual(sent[0], (12318, struct.pack(">ii", 180, 0)))
        self.assertEqual(
            [packet for packet in sent if packet[0] == 13135],
            [resource_packet(row) for row in rows[:2]],
        )
        self.assertEqual(store.asserted_scope, (1385, 0))
        self.assertEqual(store.queries, 1)
        self.assertEqual(
            plantings.snapshots(1385, 0, chunks=[(0, 0), (1, 0)]),
            [resource_packet(row) for row in rows[:2]],
        )
        # Endpoint-only and complete-map offline APIs retain their contracts.
        self.assertEqual(
            plantings.snapshots(1385, 0, position=character), [resource_packet(rows[2])]
        )
        self.assertEqual(
            plantings.snapshots(1385, 0), [resource_packet(row) for row in rows]
        )
        queries = store.queries
        for malformed in (
            1,
            "0,0",
            [(0,)],
            [(0, 0, 0)],
            [(True, 0)],
            [[0, 0]],
            [(0.5, 0)],
        ):
            with self.subTest(chunks=malformed), self.assertRaises(ValueError):
                plantings.snapshots(1385, 0, position=character, chunks=malformed)
        for foreign in (dict(character, map_id=1386), dict(character, instance_id=1)):
            with self.subTest(position=foreign), self.assertRaises(ValueError):
                plantings.snapshots(1385, 0, position=foreign, chunks=[(0, 0)])
        for map_id, instance in ((True, 0), (1385, -1), (1385, True)):
            with self.subTest(scope=(map_id, instance)), self.assertRaises(ValueError):
                plantings.snapshots(map_id, instance, chunks=[(0, 0)])
        self.assertEqual(store.queries, queries)
        self.assertEqual(plantings.snapshots(1385, 0, chunks=[]), [])
        self.assertEqual(store.queries, queries)
        sent.clear()
        ns["scene_sync"].last_regions = set()
        ns["sync_scene_world"]()
        self.assertEqual(sent, [])
        self.assertEqual(store.queries, queries)


if __name__ == "__main__":
    unittest.main()
