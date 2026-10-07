import json
import threading
import unittest
from unittest.mock import patch

from native_deadline import bounded, check, remaining
from native_context import encode_bytes
from world_bridge import ContextTransport


class NativeDeadlineTests(unittest.TestCase):
    def test_expired_scope_rejects_complete_encoding_and_restores_outer_context(self):
        now = [10.0]
        with bounded(11.0, clock=lambda: now[0]):
            self.assertEqual(remaining(), 1)
            now[0] = 12
            with self.assertRaises(TimeoutError):
                encode_bytes({"complete": b"unchanged"})
        self.assertIsNone(remaining())
        self.assertIn(b"wakfu-native-graph-1", encode_bytes({"complete": b"unchanged"}))

    def test_deadline_does_not_cancel_an_independent_encounter_thread(self):
        values = []
        with bounded(11.0, clock=lambda: 10.0):
            worker = threading.Thread(target=lambda: values.append(remaining()))
            worker.start()
            worker.join()
            self.assertEqual(remaining(), 1)
        self.assertEqual(values, [None])

    def test_http_timeout_uses_remaining_budget_and_rejects_late_reply(self):
        from io import BytesIO

        now = [10.0]

        class Reply(BytesIO):
            def read(self, *args):
                now[0] = 12.0
                return super().read(*args)

        transport = ContextTransport("http://unused", timeout=10)
        with patch(
            "urllib.request.urlopen",
            return_value=Reply(json.dumps({"ok": True}).encode()),
        ) as request:
            with bounded(11.0, clock=lambda: now[0]):
                with self.assertRaises(TimeoutError):
                    transport._retry_request("/v3/decide", {})
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["timeout"], 1)

    def test_nested_operation_cannot_extend_encounter_deadline(self):
        now = [10.0]
        with bounded(11.0, clock=lambda: now[0]):
            with bounded(20.0, clock=lambda: now[0]):
                self.assertEqual(remaining(), 1)
                now[0] = 11.0
                with self.assertRaises(TimeoutError):
                    check()
