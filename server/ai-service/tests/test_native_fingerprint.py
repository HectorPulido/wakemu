from datetime import datetime, timezone
from decimal import Decimal
from collections import deque
from types import SimpleNamespace
import unittest

from wakfu_ai.context.native_fingerprint import fingerprint


class NativeFingerprintTests(unittest.TestCase):
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
