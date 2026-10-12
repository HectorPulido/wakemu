import ast
import struct
import unittest
from types import SimpleNamespace

from test_static_map_sync_dispatch import _session_function, SERVER_SOURCE
from wakfu_server.maps.world_scene_sync import refresh_snapshots, snapshot_ids
from wakfu_server.interactive_publication import InteractivePublication


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
        publication = InteractivePublication(
            lambda _: [dict(id=26865, x=-217, y=-39, auto=False)]
        )
        scope = dict(
            session_id="test",
            generation=1,
            account_id=1,
            character_id=6,
            map_id=527,
            instance_id=0,
        )

        def wire_send(connection, service, opcode, payload):
            data = publication.transform(
                struct.pack(">IH", 6 + len(payload), opcode) + payload, scope
            )
            offset = 0
            while offset < len(data):
                length, code = struct.unpack_from(">IH", data, offset)
                sent.append((code, data[offset + 6 : offset + length]))
                offset += length

        namespace = {
            "publish_environment_scene": lambda **kwargs: None,
            "PROFILER": IdentityProfiler(),
            "PLANTINGS": SimpleNamespace(snapshots=lambda *args, **kwargs: []),
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
            "send": wire_send,
            "record": lambda **kwargs: None,
        }
        module = ast.Module(
            body=[_session_function("sync_scene_world")], type_ignores=[]
        )
        ast.fix_missing_locations(module)
        exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
        namespace["sync_scene_world"]()
        namespace["sync_scene_world"]()
        self.assertEqual([opcode for opcode, _ in sent], [12318, 13984, 12318, 12344])
        self.assertEqual(struct.unpack(">ii", sent[0][1]), (-217, -39))
        self.assertEqual(struct.unpack_from(">q", sent[3][1])[0], 26865)


if __name__ == "__main__":
    unittest.main()
