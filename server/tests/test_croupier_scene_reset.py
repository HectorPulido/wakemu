"""A rejected same-map transport resets native attachment membership."""
import ast
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

from wakfu_server.maps.interactive_publication import InteractivePublication
from test_static_map_sync_dispatch import (
    IdentityProfiler,
    SERVER_SOURCE,
    _session_function,
)


def frame(opcode, body=b""):
    return struct.pack(">IH", 6 + len(body), opcode) + body


def decode(data):
    packets = []
    while data:
        size, opcode = struct.unpack_from(">IH", data)
        packets.append((opcode, data[6:size]))
        data = data[size:]
    return packets


class CroupierSceneResetTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(id=65, map_id=527, instance_id=0, x=-1, y=27, z=0)
        self.record_body = bytes.fromhex("01020000000602000101010001010000000000")
        self.rows = [dict(id=34600, x=-1, y=27, auto=False)]
        self.publication = InteractivePublication(lambda _map: self.rows)
        self.scope = dict(
            session_id="scene-reset-test",
            generation=1,
            account_id=7,
            character_id=65,
            map_id=527,
            instance_id=0,
        )
        self.sent = []

    def publish_send(self, _connection, _service, opcode, body):
        wire = self.publication.transform(frame(opcode, body), self.scope)
        self.sent.extend(decode(wire))

    def rejected_transport(self):
        tree = ast.parse(SERVER_SOURCE.read_text())
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        handler = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.ExceptHandler)
            and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "record"
                and any(
                    keyword.arg == "event"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == "transport_rejected"
                    for keyword in child.keywords
                )
                for child in ast.walk(node)
            )
            and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "send"
                and len(child.args) >= 3
                and isinstance(child.args[2], ast.Constant)
                and child.args[2].value == 13974
                for child in ast.walk(node)
            )
        )
        function = ast.FunctionDef(
            name="rejected_transport",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="error")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=handler.body,
            decorator_list=[],
        )
        ast.fix_missing_locations(function)
        namespace = dict(
            account_id=7,
            character=self.character,
            connection=object(),
            service="world",
            send=self.publish_send,
            record=lambda **_kwargs: None,
            is_dungeon_run=lambda _instance: False,
            fixture=lambda opcode: (opcode, b"fixture"),
            wire=SimpleNamespace(adapt=lambda opcode, *_args: b"native-ready"),
            owned_native_bootstrap=lambda *_args: (),
        )
        ast.fix_missing_locations(function)
        exec(
            compile(
                ast.Module(body=[function], type_ignores=[]), str(SERVER_SOURCE), "exec"
            ),
            namespace,
        )
        namespace["rejected_transport"](ValueError("No route"))

    def sync_scene_world(self):
        payload = (
            struct.pack(">h", 1)
            + struct.pack(">qH", 34600, len(self.record_body))
            + self.record_body
        )
        namespace = dict(
            publish_environment_scene=lambda **_kwargs: None,
            PROFILER=IdentityProfiler(),
            loaded=True,
            character=self.character,
            fight=None,
            spectator_session=None,
            scene_sync=SimpleNamespace(
                poll=lambda *_args: (payload,), last_regions={(-1, 1)}
            ),
            time=SimpleNamespace(monotonic=lambda: 1.0),
            struct=struct,
            send=self.publish_send,
            connection=object(),
            service="world",
            PLANTINGS=SimpleNamespace(snapshots=lambda *_args, **_kwargs: ()),
            is_dungeon_run=lambda _instance: False,
            record=lambda **_kwargs: None,
            snapshot_ids=lambda _packets: [34600],
        )
        function = _session_function("sync_scene_world")
        ast.fix_missing_locations(function)
        exec(
            compile(
                ast.Module(body=[function], type_ignores=[]), str(SERVER_SOURCE), "exec"
            ),
            namespace,
        )
        namespace["sync_scene_world"]()

    def test_rejected_transport_starts_a_fresh_attachment_epoch(self):
        loader_body = struct.pack(">ii", self.character["x"], self.character["y"])
        record = struct.pack(">qH", 34600, len(self.record_body)) + self.record_body
        snapshot_body = struct.pack(">h", 1) + record

        # The exact production rejection branch sends 13974 by itself.
        self.rejected_transport()
        self.assertEqual([code for code, _ in self.sent], [13974])
        self.sent.clear()

        # The actual scene sync sends 12318 then 13984; the attachment is
        # emitted once in this epoch, then subsequent state is an in-place
        # 12344 update rather than a second attachment.
        self.sync_scene_world()
        self.assertEqual(
            self.sent,
            [(12318, loader_body), (13984, snapshot_body)],
        )
        self.sent.clear()
        self.sync_scene_world()
        self.assertEqual([code for code, _ in self.sent], [12318, 12344])
        self.assertEqual(self.sent[-1][1][:8], struct.pack(">q", 34600))
        self.sent.clear()

        # A second rejection resets the same-map registry again, allowing one
        # new attachment in the next epoch.
        self.rejected_transport()
        self.assertEqual([code for code, _ in self.sent], [13974])
        self.sent.clear()
        self.sync_scene_world()
        self.assertEqual(
            self.sent,
            [(12318, loader_body), (13984, snapshot_body)],
        )

    def test_legacy_13974_passthrough_witness_would_suppress_reattachment(self):
        # Causal test-only baseline: before 13974 cleared membership, the
        # publication layer treated it as an unrelated passthrough frame.
        self.sync_scene_world()
        self.assertEqual(self.sent[-1][0], 13984)
        self.sent.clear()
        original = self.publication.transform

        def legacy_transform(data, scope=None):
            if len(data) >= 6 and struct.unpack_from(">H", data, 4)[0] == 13974:
                data = data[:4] + struct.pack(">H", 13975) + data[6:]
            return original(data, scope)

        self.publication.transform = legacy_transform
        try:
            self.rejected_transport()
            self.sent.clear()
            self.sync_scene_world()
        finally:
            self.publication.transform = original
        self.assertEqual([opcode for opcode, _ in self.sent], [12318, 12344])


if __name__ == "__main__":
    unittest.main()
