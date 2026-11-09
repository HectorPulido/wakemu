"""Focused fingerprint contracts for native pointer checkpoint lineage."""
import gc
import unittest
import weakref
from copy import copy
import json

from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint
from wakfu_server.wakia_bridge.wakfu_ai.context.native_fingerprint import (
    NativeLineages,
    fingerprint,
    lineage_scope,
)
from wakfu_server.wakia_bridge.wakfu_ai.context.native_context import (
    NativeGraph,
    encode,
    encode_bytes,
)


def checkpoint(lineage=None):
    """Build the exact checkpoint type without constructing a Fight or QI."""
    value = NativePointerCheckpoint.__new__(NativePointerCheckpoint)
    dict.__init__(value)
    value._qi = None
    value._lineage = object() if lineage is None else lineage
    return value


def scoped_fingerprint(value, scope):
    with lineage_scope(scope):
        return fingerprint(value)


class NativePointerLineageFingerprintTests(unittest.TestCase):
    def test_lineage_identity_clone_replacement_and_scope_lifetime(self):
        scope = NativeLineages()
        original = checkpoint()
        original_fingerprint = scoped_fingerprint(original, scope)

        # A shallow clone is sufficient here: this test exercises the exact
        # checkpoint reducer and lineage registry without constructing a Fight.
        clone = copy(original)
        self.assertIs(clone._lineage, original._lineage)
        self.assertEqual(scoped_fingerprint(clone, scope), original_fingerprint)

        original_ref = weakref.ref(original)
        del original
        gc.collect()
        self.assertIsNone(original_ref())
        self.assertEqual(scoped_fingerprint(clone, scope), original_fingerprint)

        clone._lineage = object()
        self.assertNotEqual(scoped_fingerprint(clone, scope), original_fingerprint)
        clone._lineage = []
        with self.assertRaisesRegex(ValueError, "Invalid native pointer lineage"):
            scoped_fingerprint(clone, scope)

        scope_ref = weakref.ref(scope)
        del clone, scope
        gc.collect()
        self.assertIsNone(scope_ref())

    def test_lineage_capacity_fails_closed(self):
        scope = NativeLineages(maximum=1)
        first = checkpoint()
        self.assertTrue(scoped_fingerprint(first, scope))

        second = checkpoint()
        with self.assertRaisesRegex(ValueError, "capacity exceeded"):
            scoped_fingerprint(second, scope)

    def test_checkpoint_lineage_graph_preserves_aliases_without_instantiation(self):
        shared = object()
        first, second = checkpoint(shared), checkpoint(shared)
        independent = checkpoint()

        encoded = encode([first, second, independent])
        encoded_bytes = encode_bytes([first, second, independent])
        self.assertEqual(encoded, json.loads(encoded_bytes))
        graph = NativeGraph(encoded)
        checkpoint_refs = [graph.resolve(ref) for ref in graph.root["items"]]
        first_lineage = checkpoint_refs[0]["fields"]["_lineage"]
        second_lineage = checkpoint_refs[1]["fields"]["_lineage"]
        independent_lineage = checkpoint_refs[2]["fields"]["_lineage"]
        self.assertEqual(first_lineage, second_lineage)
        self.assertNotEqual(first_lineage, independent_lineage)
        self.assertEqual(
            graph.resolve(first_lineage),
            {"type": "object", "module": "builtins", "name": "object", "fields": {}},
        )
        with self.assertRaisesRegex(
            ValueError, "Native object requires field/reference navigation"
        ):
            graph.plain(first_lineage)
        self.assertEqual(len(checkpoint_refs), 3)

        first._lineage = object()
        replaced = NativeGraph(encode([first, second, independent]))
        replaced_refs = [replaced.resolve(ref) for ref in replaced.root["items"]]
        self.assertNotEqual(
            replaced_refs[0]["fields"]["_lineage"],
            replaced_refs[1]["fields"]["_lineage"],
        )

    def test_unrelated_container_subclasses_do_not_gain_object_token_exception(self):
        class UnrelatedList(list):
            pass

        graph = NativeGraph(encode(UnrelatedList([1, 2])))
        self.assertEqual(
            graph.root["nativeClass"],
            {
                "module": __name__,
                "name": "NativePointerLineageFingerprintTests.test_unrelated_container_subclasses_do_not_gain_object_token_exception.<locals>.UnrelatedList",
            },
        )
        self.assertEqual(graph.plain({"ref": 0}), [1, 2])

    def test_graph_rejects_invalid_checkpoint_and_unrelated_objects(self):
        invalid = checkpoint(None)
        invalid._lineage = None
        with self.assertRaisesRegex(ValueError, "Invalid native pointer lineage"):
            encode(invalid)
        with self.assertRaisesRegex(ValueError, "Unsupported native context type"):
            encode(object())

    def test_graph_rejects_unrelated_live_and_dead_weakrefs(self):
        class Target:
            pass

        target = Target()
        reference = weakref.ref(target)
        with self.assertRaisesRegex(ValueError, "Unsupported native context type"):
            encode(reference)
        del target
        gc.collect()
        with self.assertRaisesRegex(ValueError, "Unsupported native context type"):
            encode(reference)


if __name__ == "__main__":
    unittest.main()
