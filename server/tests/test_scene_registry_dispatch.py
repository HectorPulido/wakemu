import ast
import struct
import unittest
from types import SimpleNamespace

from test_static_map_sync_dispatch import _session_function, SERVER_SOURCE
from wakfu_server.maps.world_scene_sync import refresh_snapshots, snapshot_ids


class IdentityProfiler:
    """Avoid instrumenting the extracted scene-sync function."""

    @staticmethod
    def profile(_name):
        return lambda function: function


class SceneRegistryDispatchTests(unittest.TestCase):
    def test_registry_moves_before_state_is_applied_after_walking_back(self):
        body = struct.pack(">hqH", 1, 26865, 19) + bytes.fromhex(
            "01020000000602000101010000000000000000"
        )
        sent = []
        character = {"id": 6, "map_id": 527, "instance_id": 0, "x": -217, "y": -39}
        namespace = {
            "PROFILER": IdentityProfiler(),
            "loaded": True,
            "character": character,
            "fight": None,
            "spectator_session": None,
            "connection": object(),
            "service": "world",
            "scene_sync": SimpleNamespace(poll=lambda *args: (body,)),
            "time": SimpleNamespace(monotonic=lambda: 1.0),
            "struct": struct,
            "is_dungeon_run": lambda value: False,
            "refresh_snapshots": refresh_snapshots,
            "snapshot_ids": snapshot_ids,
            "send": lambda connection, service, opcode, payload: sent.append(
                (opcode, payload)
            ),
            "record": lambda **kwargs: None,
        }
        module = ast.Module(
            body=[_session_function("sync_scene_world")], type_ignores=[]
        )
        ast.fix_missing_locations(module)
        exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
        namespace["sync_scene_world"]()
        self.assertEqual([opcode for opcode, _ in sent], [12318, 13984, 12344])
        self.assertEqual(struct.unpack(">ii", sent[0][1]), (-217, -39))
        self.assertEqual(struct.unpack_from(">q", sent[2][1])[0], 26865)


if __name__ == "__main__":
    unittest.main()
