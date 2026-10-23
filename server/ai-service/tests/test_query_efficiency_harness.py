"""Independent conformance checks for the private efficiency comparison."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from query_efficiency_harness import make_search, measure
from test_query_efficiency_quality import FAMILIES, make_case
from wakfu_ai.context.native_context import encode
from wakfu_ai.planning import query_search


class EfficiencyHarnessConformanceTests(unittest.TestCase):
    def test_enabled_clone_matches_unmodified_production_coroutine(self):
        # These families use the actual production candidate generator.
        for family in (
            "ready_attack",
            "immediate_competing",
            "rejected_competing",
            "stale_hint",
            "after_attack_retreat",
        ):
            for query_budget in (None, 8):
                with self.subTest(family=family, query_budget=query_budget):
                    original, _ = make_case(family, nodes=8)
                    cloned, _ = make_case(family, nodes=8)
                    expected = measure(
                        original, query_search.search, query_budget=query_budget
                    )
                    actual = measure(cloned, make_search(), query_budget=query_budget)
                    self.assertEqual(actual, expected)

    def test_no_hint_without_transpositions_has_identical_queries_and_decisions(self):
        for family in FAMILIES:
            for query_budget in (None, 8):
                with self.subTest(family=family, query_budget=query_budget):
                    samples = []
                    for enabled in (False, True):
                        session, factory = make_case(family, nodes=8)
                        session.envelope.pop("warmStart", None)
                        search = make_search(
                            preview_reuse=enabled,
                            frontier_reuse=enabled,
                            candidate_factory=factory,
                        )
                        samples.append(
                            measure(session, search, query_budget=query_budget)
                        )
                    self.assertEqual(
                        samples[1]["result"]["searchBudgetEvidence"][
                            "previewCacheHits"
                        ],
                        0,
                    )
                    # The new general-cache ablation also disables cache
                    # allocation without hints. Its capacity/entry counters
                    # differ even when no transition can be reused. Compare
                    # every outcome and query, excluding only those counters.
                    for sample in samples:
                        evidence = sample["result"]["searchBudgetEvidence"]
                        for name in (
                            "previewCacheHits",
                            "previewCacheEntries",
                            "previewCacheCapacity",
                            "previewCacheEvictions",
                        ):
                            evidence.pop(name)
                    self.assertEqual(samples[0], samples[1])

    def test_identity_ignores_receipts_but_retains_game_and_hidden_facts(self):
        for difference in ("receipt_only", "used_repertoire", "ap", "native_graph"):
            with self.subTest(difference=difference):
                session, _ = make_case("ready_attack")
                other = deepcopy(session.states[session.envelope["rootState"]])
                other["public"].update(key="different-receipt", stateRevision=123456)
                if difference == "used_repertoire":
                    other["used"] = True
                elif difference == "ap":
                    other["public"]["actors"][0]["ap"] -= 1
                elif difference == "native_graph":
                    graph = encode(
                        dict(
                            runtime=SimpleNamespace(
                                fight=SimpleNamespace(
                                    walkable=frozenset(map(tuple, session.cells)),
                                    edges=frozenset(session.edges),
                                    future_native_field={
                                        "version": 8,
                                        "unknown": b"retained",
                                    },
                                ),
                                future_runtime_field="preserved",
                            )
                        )
                    )
                    other["public"]["nativeContext"] = session.store.put_json(graph)
                session.states["different-receipt"] = other

                def inspect_sources(envelope, store, *, clock):
                    for index, state in enumerate(
                        (envelope["rootState"], "different-receipt")
                    ):
                        yield dict(
                            id="inspect-" + str(index),
                            operation="repertoire",
                            state=state,
                        )
                    return dict(action=dict(type="end_turn"))

                measured = measure(session, inspect_sources)
                self.assertEqual(measured["totalQueries"], 2)
                self.assertEqual(
                    measured["uniqueSources"], 1 if difference == "receipt_only" else 2
                )


if __name__ == "__main__":
    unittest.main()
