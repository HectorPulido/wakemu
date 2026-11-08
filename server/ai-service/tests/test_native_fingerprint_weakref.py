"""Exact weak-reference fingerprints retain target semantics and alias graphs."""
import gc
import unittest
from weakref import ref

from wakfu_ai.context.native_fingerprint import fingerprint


class Node:
    pass


class NativeWeakFingerprintTests(unittest.TestCase):
    def test_targets_aliases_cycles_callbacks_and_dead_references(self):
        calls = []

        def callback(reference):
            calls.append(reference)

        target = Node()
        target.value = 1
        pointer = ref(target, callback)
        target.pointer = pointer
        graph = {"target": target, "pointer": pointer, "alias": pointer}
        before = fingerprint(graph)
        self.assertEqual(fingerprint(graph), before)
        self.assertEqual(calls, [])
        target.value = 2
        self.assertNotEqual(fingerprint(graph), before)
        target.value = 1
        self.assertEqual(fingerprint(graph), before)
        sibling = Node()
        sibling.value, sibling.pointer = 1, pointer
        changed_alias = dict(graph, target=sibling)
        self.assertNotEqual(fingerprint(changed_alias), before)

        def other_callback(reference):
            calls.append(reference)

        self.assertNotEqual(
            fingerprint(ref(target, other_callback)), fingerprint(pointer)
        )
        transient = Node()
        dead = ref(transient)
        del transient
        gc.collect()
        self.assertIsNone(dead())
        self.assertEqual(fingerprint(dead), fingerprint(dead))
        self.assertNotEqual(fingerprint(dead), fingerprint(pointer))
        self.assertEqual(calls, [])

        class OpaqueRef(ref):
            def __call__(self):
                raise AssertionError("Custom weak reference executed")

        with self.assertRaisesRegex(
            ValueError, "Unsupported complete fingerprint type"
        ):
            fingerprint(OpaqueRef(target))


if __name__ == "__main__":
    unittest.main()
