from datetime import datetime, timezone
from decimal import Decimal
from collections import deque
from types import SimpleNamespace
import unittest
import hashlib
import io
import tracemalloc
from unittest.mock import patch

from wakfu_ai.context.native_fingerprint import fingerprint, _CompletePickler
from wakfu_ai.native.native_deadline import bounded


class NativeFingerprintTests(unittest.TestCase):
    def test_streaming_digest_matches_legacy_complete_pickle_bytes(self):
        shared = [b"payload", {"revision": 7}]
        graph = SimpleNamespace(left=shared, right=shared)
        graph.parent = graph
        for value in (graph, {"raw": bytes(200000), "graph": graph}):
            stream = io.BytesIO()
            _CompletePickler(stream, protocol=5).dump(value)
            self.assertEqual(
                fingerprint(value), hashlib.sha256(stream.getbuffer()).hexdigest()
            )
        before = fingerprint(graph)
        shared[1]["revision"] = 8
        self.assertNotEqual(before, fingerprint(graph))
        before = fingerprint(graph)
        graph.right = list(shared)
        self.assertNotEqual(before, fingerprint(graph))

    def test_large_raw_payload_does_not_allocate_another_serialized_graph(self):
        payload = bytes(8 * 1024 * 1024)
        tracemalloc.start()
        try:
            fingerprint({"payload": payload})
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, len(payload) // 2)

    def test_large_builtin_graph_honors_deadline_mid_serialization(self):
        graph = {str(index): [index] * 4 for index in range(20000)}
        now = [0.0]
        checks = [0]
        from wakfu_ai.native.native_deadline import check as deadline_check

        def elapsed():
            checks[0] += 1
            if checks[0] > 4:
                now[0] = 2.0
            deadline_check()

        with bounded(1.0, clock=lambda: now[0]), patch(
            "wakfu_ai.context.native_fingerprint.check", side_effect=elapsed
        ), self.assertRaisesRegex(TimeoutError, "Native AI turn deadline"):
            fingerprint(graph)
        self.assertGreater(checks[0], 4)
        self.assertEqual(fingerprint(graph), fingerprint(graph))

    def test_deque_guard_includes_capacity_order_aliases_and_hidden_fields(self):
        class FutureQueue(deque):
            def __reduce__(self):
                raise AssertionError("Never execute a custom native reducer")

        queue = FutureQueue([1, 2], maxlen=3)
        queue.future = {"self": queue, "revision": 1}
        before = fingerprint(queue)
        queue.future["revision"] = 2
        self.assertNotEqual(before, fingerprint(queue))
        self.assertNotEqual(
            fingerprint(deque([1, 2], maxlen=3)), fingerprint(deque([1, 2], maxlen=4))
        )

    def test_complete_fields_slots_cycles_aliases_and_private_changes(self):
        class Native:
            __slots__ = ("__private", "__dict__")

            def __init__(self):
                self.__private = 3
                self.future = [b"complete"]
                self.alias = self.future
                self.cycle = self

            def __reduce__(self):
                raise AssertionError("Native reducer must never execute")

        value = Native()
        before = fingerprint(value)
        equivalent = Native()
        self.assertEqual(before, fingerprint(equivalent))
        value._Native__private = 4
        self.assertNotEqual(before, fingerprint(value))
        before = fingerprint(value)
        value.alias = list(value.future)
        self.assertNotEqual(before, fingerprint(value))

    def test_container_subclass_keeps_future_fields_and_self_references(self):
        class FutureList(list):
            pass

        value = FutureList([1, 2])
        value.future = {"parent": value, "revision": 7}
        before = fingerprint(value)
        value.future["revision"] = 8
        self.assertNotEqual(before, fingerprint(value))
        before = fingerprint(value)
        value.append(3)
        self.assertNotEqual(before, fingerprint(value))

    def test_hostile_dict_hooks_are_not_called_and_physical_entries_are_fingerprinted(
        self,
    ):
        class HostileDict(dict):
            __slots__ = ("__hidden", "__dict__")

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.__hidden = ["slot", b"preserved"]

            def items(self):
                raise AssertionError("custom items must not run")

            def __iter__(self):
                raise AssertionError("custom iteration must not run")

            def __getitem__(self, key):
                raise AssertionError("custom lookup must not run")

        stored = {"revision": 1}
        value = HostileDict({"stored": stored})
        value.alias = stored
        stored["owner"] = value
        before = fingerprint(value)
        dict.__setitem__(value, "stored", {"revision": 2})
        self.assertNotEqual(before, fingerprint(value))

    def test_callable_descriptors_and_data_are_not_executed(self):
        def forbidden():
            raise AssertionError("Do not execute callbacks")

        value = SimpleNamespace(
            callback=forbidden,
            date=datetime.now(timezone.utc),
            decimal=Decimal("1.3"),
            bytes=bytearray(b"raw"),
            view=memoryview(b"view"),
        )
        self.assertEqual(fingerprint(value), fingerprint(value))
        before = fingerprint(value)
        value.bytes[0] = 0
        self.assertNotEqual(before, fingerprint(value))


if __name__ == "__main__":
    unittest.main()
