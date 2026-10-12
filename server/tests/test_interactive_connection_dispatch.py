"""Exercise the production Connection serializer with native interactive frames."""
import ast
from contextlib import nullcontext
from pathlib import Path
import struct
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from wakfu_server.interactive_publication import InteractivePublication


def frame(opcode, body):
    return struct.pack(">IH", 6 + len(body), opcode) + body


def snapshot(payload=b"state"):
    return frame(13984, struct.pack(">hqH", 1, 34644, len(payload)) + payload)


class InteractiveConnectionTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(
            (Path(__file__).parents[1] / "local_game_server.py").read_text()
        )
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "Connection"
        )
        self.events = []
        namespace = dict(
            threading=threading,
            PROFILER=SimpleNamespace(span=lambda _: nullcontext()),
            record=lambda **event: self.events.append(event),
        )
        exec(
            compile(
                ast.Module(body=[node], type_ignores=[]),
                "production_connection",
                "exec",
            ),
            namespace,
        )
        self.writes = []
        self.socket = SimpleNamespace(sendall=self.writes.append)
        self.connection = namespace["Connection"](self.socket)
        self.connection.interactive_publication = InteractivePublication(
            lambda _: [dict(id=34644, x=3, y=-23, auto=False)],
            trace=self.connection.interactive_trace.append,
            trace_ids={34644},
        )
        self.connection.interactive_scope = lambda: dict(
            session_id="peer",
            generation=2,
            account_id=24,
            character_id=42,
            map_id=1385,
            instance_id=0,
        )
        self.connection.sendall(frame(12318, struct.pack(">ii", 3, -21)))
        self.writes.clear()

    def test_actual_wire_first_attach_then_changed_state_update(self):
        self.connection.sendall(snapshot(b"first"))
        self.connection.sendall(snapshot(b"changed"))
        self.assertEqual(struct.unpack_from(">H", self.writes[0], 4)[0], 13984)
        self.assertEqual(struct.unpack_from(">H", self.writes[1], 4)[0], 12344)
        self.assertTrue(self.writes[1].endswith(b"changed"))
        self.assertEqual([e["operation"] for e in self.events], ["attach", "update"])
        self.assertTrue(
            all(e["event"] == "interactive_wire_publication" for e in self.events)
        )

    def test_instance_tracker_receives_only_successfully_transformed_bytes(self):
        tracker = Mock()
        self.connection.instance_publications = tracker
        scope = (24, "generation", 42, 1385, 0)
        self.connection.native_instance_scope = lambda: scope
        self.connection.sendall(snapshot(b"first"))
        self.connection.sendall(snapshot(b"changed"))
        self.assertEqual(
            tracker.after_write.call_args_list[1].args, (self.writes[1], scope)
        )
        self.assertEqual(struct.unpack_from(">H", self.writes[1], 4)[0], 12344)
        tracker.invalidate.assert_not_called()

    def test_both_publication_trackers_invalidate_after_failed_write(self):
        tracker = Mock()
        self.connection.instance_publications = tracker
        self.socket.sendall = Mock(side_effect=OSError("closed"))
        with self.assertRaises(OSError):
            self.connection.sendall(snapshot())
        tracker.invalidate.assert_called_once_with()
        tracker.after_write.assert_not_called()
        self.assertEqual(self.connection.interactive_publication.attached, set())

    def test_concurrent_writes_have_one_attachment(self):
        threads = [
            threading.Thread(target=self.connection.sendall, args=(snapshot(),))
            for _ in range(12)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        codes = [struct.unpack_from(">H", data, 4)[0] for data in self.writes]
        self.assertEqual(codes.count(13984), 1)
        self.assertEqual(codes.count(12344), 11)

    def test_failed_write_has_no_success_trace_and_invalidates_membership(self):
        def fail(_):
            raise OSError("closed")

        self.socket.sendall = fail
        with self.assertRaises(OSError):
            self.connection.sendall(snapshot())
        self.assertEqual(self.events, [])
        self.assertEqual(self.connection.interactive_publication.attached, set())
        self.assertEqual(self.connection.interactive_trace, [])

    def test_unrelated_combat_and_resource_bytes_are_preserved(self):
        data = frame(12608, b"combat actors") + frame(13948, b"resources")
        self.connection.sendall(data)
        self.assertEqual(self.writes, [data])
        self.assertEqual(self.events, [])

    def test_non_world_connection_has_unchanged_transport(self):
        self.connection.interactive_publication = None
        data = snapshot()
        self.connection.sendall(data)
        self.assertEqual(self.writes, [data])


if __name__ == "__main__":
    unittest.main()
