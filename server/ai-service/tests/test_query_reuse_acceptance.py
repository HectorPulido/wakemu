"""Integrated reuse boundaries with explicit synthetic native outcomes."""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from test_query_search import FakeNativeSession, run_search
from test_query_warm_start import cast, hint
from wakfu_ai.context.native_context import encode


def bind_identity(public, used):
    facts = {
        key: value
        for key, value in public.items()
        if key not in {"key", "stateRevision", "runtimeIdentity"}
    }
    public["runtimeIdentity"] = hashlib.sha256(
        json.dumps(
            dict(public=facts, used=used),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


class QueryReuseAcceptanceTests(unittest.TestCase):
    def test_equal_destination_does_not_merge_different_trigger_paths(self):
        cells = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0), (0, 0, 1)]
        edges = [
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (1, 1, 0)),
            ((0, 0, 0), (0, 1, 0)),
            ((0, 1, 0), (1, 1, 0)),
            ((1, 1, 0), (2, 1, 0)),
        ]
        session = FakeNativeSession(spells=[], cells=cells, edges=edges)
        session.root_state["actors"][2]["position"] = [2, 1, 0]
        session.envelope["policy"]["limits"].update(depth=1, beam=2, nodes=2)
        bind_identity(session.root_state, False)
        dangerous = dict(type="move", path=[[1, 0, 0], [1, 1, 0]])
        safe = dict(type="move", path=[[0, 1, 0], [1, 1, 0]])
        original = session.request

        def request(query):
            response = original(query)
            if query["operation"] == "preview" and response["supported"]:
                public = response["result"]
                if query["action"] == dangerous:
                    public["actors"][0]["hp"] -= 8
                bind_identity(public, session.states[public["key"]]["used"])
            return response

        def paths(graph, state, repertoire, actor_id, *args, **kwargs):
            yield deepcopy(dangerous)
            yield deepcopy(safe)

        session.request = request
        with patch("wakfu_ai.planning.query_search.candidates", paths):
            result = run_search(session)
        self.assertEqual(session.preview_actions, [dangerous, safe])
        self.assertEqual(result["action"], safe)

    def test_same_geometry_refreshes_repertoire_after_owned_state_changes(self):
        session = FakeNativeSession(
            spells=[dict(spellId=50, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={50: "none", 51: "damage"},
            outcome_features={"owned_state_progress": 0},
            feature_deltas={50: {"owned_state_progress": 1}},
        )
        session.root_state["actors"][0]["mp"] = 0
        session.envelope["policy"]["limits"].update(depth=2, beam=4, nodes=16)
        bind_identity(session.root_state, False)
        hint(session, [cast(50, 1)])
        original, repertoire_sources = session.request, []

        def request(query):
            state = session.states[query["state"]]
            if query["operation"] == "repertoire":
                repertoire_sources.append(deepcopy(state["public"]))
                spell = 51 if state["used"] else 50
                metadata = session.store.put_json(
                    encode(dict(spells=[dict(spellId=spell, level=1)]))
                )
                return dict(
                    id=query["id"], supported=True, result=dict(nativeMetadata=metadata)
                )
            response = original(query)
            if response["supported"]:
                public = response["result"]
                bind_identity(public, session.states[public["key"]]["used"])
            return response

        session.request = request
        result = run_search(session)
        self.assertEqual([action["spellId"] for action in result["plan"]], [50, 51])
        self.assertEqual(result["components"]["damage"], 5)
        self.assertEqual(len({row["nativeContext"] for row in repertoire_sources}), 1)
        self.assertGreaterEqual(
            len({row["runtimeIdentity"] for row in repertoire_sources}), 2
        )

    def test_source_bound_service_retains_incumbent_after_bridge_query_expiry(self):
        from wakfu_ai.bridge.world_bridge import NativeSession
        from wakfu_ai.native.native_deadline import bounded, check, remaining
        from wakfu_ai.planning.query_sessions import QuerySessions

        session = FakeNativeSession(
            spells=[dict(spellId=10, level=1)],
            cells=[(0, 0, 0), (1, 0, 0), (3, 0, 0), (0, 0, 1)],
            edges=[((0, 0, 0), (1, 0, 0))],
            effects={10: "damage"},
        )
        root = session.root_state["nativeContext"]
        session.states[root] = session.states.pop(session.envelope["rootState"])
        session.root_state["key"] = root
        session.envelope.update(
            rootState=root,
            sourceKey="c" * 64,
            catalogManifest="b" * 64,
            nativeBudgetMs=1200,
        )
        session.envelope["policy"].update(searchTimeFraction=1)
        session.envelope["policy"]["limits"].update(depth=1, nodes=8)
        move = dict(type="move", path=[[1, 0, 0]])
        hint(session, [move])
        session.store.seal_manifest = lambda digest: dict(complete=digest == "b" * 64)
        bridge = NativeSession.__new__(NativeSession)
        bridge.states, bridge.policy = session.states, session.envelope["policy"]
        bridge.root = root
        bridge.request_id, bridge.source = (
            session.envelope["requestId"],
            session.envelope["sourceKey"],
        )
        bridge.guard = check
        original = session.request
        now, attempted = [0.0], []

        def native_work(operation, key, query):
            attempted.append(operation)
            duration = (
                0.6
                if operation == "repertoire"
                else 0.01
                if query["action"]["type"] == "move"
                else 0.55
            )
            finish = now[0] + duration
            while now[0] < finish:
                now[0] = min(finish, now[0] + 0.01)
                check()
            return original(query)["result"]

        bridge._query = native_work
        service = QuerySessions(clock=lambda: now[0])
        with bounded(1.2, clock=lambda: now[0]):
            reply = service.decide(deepcopy(session.envelope), session.store)
            responses = []
            while reply["status"] == "query":
                query = reply["queries"][0]
                self.assertGreaterEqual(query["searchAllowanceMs"], 0)
                response = bridge.query(query)
                responses.append(response)
                payload = dict(
                    requestId=session.envelope["requestId"],
                    sourceKey=session.envelope["sourceKey"],
                    response=response,
                )
                reply = service.decide(payload, session.store)
            self.assertGreaterEqual(remaining(), 0.4999)
            self.assertEqual(
                service.decide(payload, session.store)["decision"], reply["decision"]
            )
        decision = reply["decision"]
        self.assertEqual(decision["action"], move)
        self.assertEqual(decision["plan"], [move])
        self.assertEqual(decision["sourceKey"], session.envelope["sourceKey"])
        self.assertEqual(attempted, ["preview", "repertoire", "preview"])
        self.assertFalse(responses[-1]["supported"])
        self.assertIn(
            "native_search_allowance_exhausted", decision["unknownDependencies"]
        )
        self.assertLessEqual(now[0], 0.7001)


if __name__ == "__main__":
    unittest.main()
