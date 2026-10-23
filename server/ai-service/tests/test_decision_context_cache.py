"""Exact-source metadata and decision-local complete-graph cache contracts."""
from copy import deepcopy
import unittest

from wakfu_ai.context.native_context import encode
from wakfu_ai.native.native_deadline import bounded
from wakfu_ai.planning.decision_context_cache import DecisionContextCache


class Store:
    def __init__(self):
        self.graphs = {key: encode(dict(values=[key])) for key in ("a", "b", "c")}
        self.calls = []

    def json(self, digest):
        self.calls.append(digest)
        return deepcopy(self.graphs[digest])


def state(**overrides):
    return dict(key="receipt", runtimeIdentity="a" * 64, stateRevision=7, **overrides)


class DecisionContextCacheTests(unittest.TestCase):
    def test_repertoire_requires_exact_receipt_revision_actor_and_runtime(self):
        cache = DecisionContextCache(Store())
        source = state()
        value = dict(nativeMetadata="metadata", certificate=dict(sourceState="receipt"))
        cache.put_repertoire(source, 1, value)
        self.assertEqual(cache.get_repertoire(source, 1), value)
        for changed in (
            dict(source, key="other"),
            dict(source, stateRevision=8),
            dict(source, runtimeIdentity="b" * 64),
        ):
            self.assertIsNone(cache.get_repertoire(changed, 1))
        self.assertIsNone(cache.get_repertoire(source, 2))
        self.assertIsNone(DecisionContextCache(Store()).get_repertoire(source, 1))

    def test_repertoire_owns_copies_and_bounds_entries(self):
        cache = DecisionContextCache(Store(), max_repertoires=1)
        source = state()
        value = dict(nativeMetadata="metadata", future=[1])
        cache.put_repertoire(source, 1, value)
        value["future"].append(2)
        first = cache.get_repertoire(source, 1)
        self.assertEqual(first["future"], [1])
        first["future"].append(3)
        self.assertEqual(cache.get_repertoire(source, 1)["future"], [1])
        cache.put_repertoire(dict(source, key="second"), 1, value)
        self.assertIsNone(cache.get_repertoire(source, 1))

    def test_graph_and_plain_decode_reuse_without_plain_mutation_leaks(self):
        store = Store()
        cache = DecisionContextCache(store)
        graph = cache.graph("a")
        self.assertIs(cache.graph("a"), graph)
        first = cache.plain("a")
        first["values"].append("mutated")
        self.assertEqual(cache.plain("a"), dict(values=["a"]))
        self.assertEqual(store.calls, ["a"])
        self.assertEqual(DecisionContextCache(Store()).plain("a"), dict(values=["a"]))

    def test_graph_eviction_also_invalidates_plain_and_node_accounting(self):
        store = Store()
        cache = DecisionContextCache(store, max_graphs=1)
        cache.plain("a")
        cache.plain("b")
        self.assertEqual(cache.plain("a"), dict(values=["a"]))
        self.assertEqual(store.calls, ["a", "b", "a"])
        oversized = DecisionContextCache(store, max_nodes=1)
        oversized.graph("c")
        oversized.graph("c")
        self.assertEqual(store.calls[-2:], ["c", "c"])

    def test_expired_deadlines_apply_to_every_cache_hit(self):
        cache = DecisionContextCache(Store())
        source = state()
        cache.put_repertoire(source, 1, dict(nativeMetadata="metadata"))
        cache.plain("a")
        now = [0.0]
        with bounded(1.0, clock=lambda: now[0]):
            now[0] = 2.0
            for operation in (
                lambda: cache.graph("a"),
                lambda: cache.plain("a"),
                lambda: cache.get_repertoire(source, 1),
                lambda: cache.put_repertoire(source, 1, {}),
            ):
                with self.assertRaises(TimeoutError):
                    operation()


if __name__ == "__main__":
    unittest.main()
