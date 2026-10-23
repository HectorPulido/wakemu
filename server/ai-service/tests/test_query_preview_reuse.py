"""Decision-local reuse of native sampled outcomes across exact runtime aliases."""
from collections import Counter
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession
from wakfu_ai.context.native_context import encode
from wakfu_ai.planning import query_search


def cast(identity):
    return dict(type="cast", spellId=identity, level=1, target=[3, 0, 0], targetId=9)


def convergent_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    if state["stage"] == "root":
        yield dict(type="move", path=[[1, 0, 0]])
        yield cast(11)  # A rejected probe lets the first branch finish.
        yield cast(10)
    elif state["stage"] == "joined":
        yield cast(99)


class ConvergentSession(FakeNativeSession):
    """Explicit synthetic engine: no retained history beyond declared facts.

    A move and a displacement cast can produce the same complete fixture state.
    Native Wakfu ledgers may prevent such convergence; this is not a claim
    that visually identical real positions have equivalent native identities.
    """

    def __init__(self, *, split_identity=False, missing_identity=False, border=False):
        cells = [(x, 0, 0) for x in range(4)]
        edges = [(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1]
        super().__init__(
            spells=[dict(spellId=10, level=1), dict(spellId=99, level=1)],
            cells=cells,
            edges=edges,
        )
        self.split_identity = split_identity
        self.missing_identity = missing_identity
        self.root_state["stage"] = "root"
        if border:
            self.root_graph = encode(
                dict(
                    runtime=SimpleNamespace(
                        fight=SimpleNamespace(
                            walkable=frozenset(cells),
                            edges=frozenset(edges),
                            native_border_cells=frozenset({(1, 0, 0)}),
                        )
                    )
                )
            )
            self.root_state["nativeContext"] = self.store.put_json(self.root_graph)
        self.envelope["policy"]["limits"].update(
            nodes=32, depth=2, beam=2, probeQuantum=1
        )
        self.calls = Counter()
        self.repertoires = Counter()
        self._stamp(self.root_state)

    def _stamp(self, public, private_nonce="same"):
        if not self.missing_identity:
            facts = {
                key: value
                for key, value in public.items()
                if key not in ("key", "stateRevision", "runtimeIdentity")
            }
            payload = json.dumps([facts, private_nonce], sort_keys=True).encode()
            public["runtimeIdentity"] = hashlib.sha256(payload).hexdigest()

    def request(self, query):
        if query["operation"] != "preview":
            self.repertoires[query["state"]] += 1
            return super().request(query)
        action = query["action"]
        self.calls[(query["state"], json.dumps(action, sort_keys=True))] += 1
        self.preview_actions.append(deepcopy(action))
        if action.get("spellId") == 11:
            return dict(
                id=query["id"], supported=False, unknownDependencies=["fixture_illegal"]
            )
        public = deepcopy(self.states[query["state"]]["public"])
        public.update(
            key="alias-" + str(len(self.states)), stateRevision=len(self.states)
        )
        ai = next(row for row in public["actors"] if row["id"] == 1)
        if public["stage"] == "root":
            public["stage"] = "joined"
            ai.update(position=[1, 0, 0], ap=5, mp=2)
        else:
            public["stage"] = "leaf"
            public["phase"] = "finished"
            enemy = next(row for row in public["actors"] if row["id"] == 9)
            enemy["hp"] -= 5
            ai["ap"] -= 1
            public["damageContextEvidence"] = [
                dict(
                    basis="native_damage_context_callback",
                    casterId=1,
                    targetId=9,
                    observedLocalization="FRONT",
                    localizationEnabled=True,
                )
            ]
        nonce = str(action["type"]) if self.split_identity else "same"
        self._stamp(public, private_nonce=nonce)
        self.states[public["key"]] = dict(public=public, used=False)
        return dict(id=query["id"], supported=True, result=public)


def run(
    session,
    *,
    cache=True,
    candidate_factory=convergent_candidates,
    namespace_updates=None
):
    namespace = dict(vars(query_search), candidates=candidate_factory)
    namespace.update(namespace_updates or {})
    source = inspect.getsource(query_search.search)
    if not cache:
        marker = 'preview_cache_capacity = min(256, limits["nodes"])'
        if source.count(marker) != 1:
            raise AssertionError("Ablation no longer matches the generic preview table")
        source = source.replace(marker, "preview_cache_capacity = 0")
    exec(compile(source, __file__, "exec"), namespace)
    coroutine = namespace["search"](session.envelope, session.store)
    response = None
    while True:
        try:
            request = next(coroutine) if response is None else coroutine.send(response)
        except StopIteration as completed:
            return completed.value
        response = session.request(request)


class CyclicSession(ConvergentSession):
    def request(self, query):
        if query["operation"] == "preview" and query["action"].get("spellId") == 12:
            action = query["action"]
            self.calls[(query["state"], json.dumps(action, sort_keys=True))] += 1
            self.preview_actions.append(deepcopy(action))
            public = deepcopy(self.root_state)
            public.update(
                key="alias-" + str(len(self.states)),
                stage="joined",
                stateRevision=len(self.states),
            )
            public["actors"][0].update(position=[1, 0, 0], ap=5, mp=2)
            self._stamp(public)
            self.states[public["key"]] = dict(public=public, used=False)
            return dict(id=query["id"], supported=True, result=public)
        response = super().request(query)
        if query["operation"] == "preview" and response.get("supported"):
            public = response["result"]
            if query["action"].get("spellId") in (10, 99):
                public.update(stage="sink", phase="active")
                public.pop("damageContextEvidence", None)
                public["actors"][0].update(ap=4, mp=2)
                public["actors"][-1]["hp"] = 25
                self._stamp(public)
        return response


class PreviewReuseTests(unittest.TestCase):
    def test_cached_outcome_is_still_rejected_when_visited_on_current_path(self):
        session = CyclicSession()
        session.envelope["policy"]["limits"]["depth"] = 4

        def candidates(graph, state, *args, **kwargs):
            if state["stage"] == "sink":
                yield cast(12)
            else:
                yield from convergent_candidates(graph, state, *args, **kwargs)

        result = run(session, candidate_factory=candidates)
        self.assertGreaterEqual(result["searchBudgetEvidence"]["previewCacheHits"], 2)
        self.assertLessEqual(len(result["plan"]), 2)
        self.assertEqual(result["components"]["damage"], 5)
        self.assertTrue(all(count == 1 for count in session.calls.values()))

    def test_complete_runtime_alias_reuses_sample_with_equal_decision(self):
        sessions = [ConvergentSession(), ConvergentSession()]
        before, after = run(sessions[0], cache=False), run(sessions[1])
        self.assertEqual(before["action"], after["action"])
        self.assertEqual(before["score"], after["score"])
        self.assertEqual(len(sessions[0].preview_actions), 5)
        self.assertEqual(len(sessions[1].preview_actions), 4)
        self.assertEqual(after["searchBudgetEvidence"]["previewCacheHits"], 1)
        # Source-bound repertoire certificates are deliberately not relabeled.
        self.assertEqual(
            sum(sessions[0].repertoires.values()), sum(sessions[1].repertoires.values())
        )

    def test_cached_outcome_recomputes_parent_path_penalty_and_plan(self):
        session = ConvergentSession(border=True)
        result = run(
            session,
            namespace_updates={"_remaining_border_exposure": lambda *args: None},
        )
        self.assertEqual(result["searchBudgetEvidence"]["previewCacheHits"], 1)
        self.assertEqual([step.get("spellId") for step in result["plan"]], [10, 99])
        self.assertEqual(result["components"].get("battleground_border_exposure", 0), 0)
        self.assertEqual(result["components"]["damage"], 5)
        evidence = result["orientationEvidence"][-1]
        self.assertNotEqual(evidence["sourceState"], evidence["reusedForState"])
        self.assertEqual(
            session.states[evidence["sourceState"]]["public"]["runtimeIdentity"],
            session.states[evidence["reusedForState"]]["public"]["runtimeIdentity"],
        )
        self.assertEqual(evidence["sourceState"], "alias-1")

    def test_private_runtime_change_prevents_visually_identical_state_reuse(self):
        session = ConvergentSession(split_identity=True)
        result = run(session)
        self.assertEqual(result["searchBudgetEvidence"]["previewCacheHits"], 0)
        self.assertEqual(len(session.preview_actions), 5)

    def test_legacy_missing_runtime_identity_uses_exact_receipts(self):
        session = ConvergentSession(missing_identity=True)
        result = run(session)
        self.assertEqual(result["searchBudgetEvidence"]["previewCacheHits"], 0)
        self.assertEqual(len(session.preview_actions), 5)

    def test_distinct_target_identity_and_path_order_are_distinct_actions(self):
        state = dict(key="a", runtimeIdentity="a" * 64)
        original = cast(99)
        self.assertNotEqual(
            query_search._preview_cache_key(state, original),
            query_search._preview_cache_key(state, dict(original, targetId=2)),
        )
        first = dict(type="move", path=[[1, 0, 0], [1, 1, 0]])
        second = dict(type="move", path=list(reversed(first["path"])))
        self.assertNotEqual(
            query_search._preview_cache_key(state, first),
            query_search._preview_cache_key(state, second),
        )

    def test_failure_reuse_is_bounded_and_evicted_entries_are_requeried(self):
        session = FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0)],
            edges=[],
            reject_all=True,
        )
        session.envelope["policy"]["limits"].update(nodes=512, depth=1, probeQuantum=64)
        actions = [
            dict(type="cast", spellId=1, level=1, target=[x, 0, 0]) for x in range(257)
        ]

        def candidates(*args, **kwargs):
            yield from actions
            yield actions[0]  # Evicted from the 256-entry table.
            yield actions[-1]  # Still retained: no additional native query.

        result = run(session, candidate_factory=candidates)
        evidence = result["searchBudgetEvidence"]
        self.assertEqual(evidence["previewCacheEntries"], 256)
        self.assertEqual(evidence["previewCacheCapacity"], 256)
        self.assertEqual(evidence["previewCacheEvictions"], 2)
        self.assertEqual(evidence["previewCacheHits"], 1)
        self.assertEqual(len(session.preview_actions), 258)
        self.assertEqual(result["action"], dict(type="end_turn"))

    def test_tables_do_not_survive_a_second_decision(self):
        samples = [run(ConvergentSession()) for _ in range(2)]
        for sample in samples:
            self.assertEqual(sample["searchBudgetEvidence"]["previewCacheHits"], 1)
            self.assertEqual(sample["expanded"], 4)

    def test_cooperative_allowance_failure_keeps_incumbent_without_caching_timeout(
        self,
    ):
        session = ConvergentSession()
        original = session.request

        def request(query):
            if query["operation"] == "preview" and len(session.preview_actions) >= 1:
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["native_search_allowance_exhausted"],
                )
            return original(query)

        session.request = request
        result = run(session)
        self.assertEqual(result["action"]["type"], "move")
        evidence = result["searchBudgetEvidence"]
        self.assertEqual(evidence["previewCacheEntries"], 1)
        self.assertIn("native_search_allowance_exhausted", evidence["stopReasons"])


if __name__ == "__main__":
    unittest.main()
