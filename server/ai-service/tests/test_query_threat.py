"""Threat forecast coroutine tests against a complete fake native provider."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.context.native_context import encode
from wakfu_ai.planning.query_threat import forecast
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS
from wakfu_ai.bridge.world_bridge import _json_bytes


AI_ID, ALLY_ID = 1, 2


def actor(identity, team, position, hp=30, *, max_hp=30, ap=6, mp=3, wp=2, armor=0):
    return dict(
        id=identity,
        team=team,
        controlled=identity in (AI_ID, ALLY_ID),
        position=list(position),
        hp=hp,
        max_hp=max_hp,
        armor=armor,
        ap=ap,
        mp=mp,
        wp=wp,
    )


def geometry(cells, edges):
    fight = SimpleNamespace(
        walkable=frozenset(tuple(cell) for cell in cells),
        edges=frozenset((tuple(start), tuple(end)) for start, end in edges),
        futureGeometryExtension=b"all cells and edges",
    )
    return encode({"runtime": SimpleNamespace(fight=fight)})


class FakeStore:
    def __init__(self):
        self.values = {}

    def save(self, value):
        raw = _json_bytes(value)
        digest = hashlib.sha256(raw).hexdigest()
        self.values[digest] = deepcopy(value)
        return digest

    def json(self, digest):
        return deepcopy(self.values[digest])


class FakeProvider:
    def __init__(
        self,
        *,
        rivals=(9,),
        spells=None,
        effects=None,
        projection_unsupported=(),
        move_then_cast=False,
        omit_actor=None,
        mismatch_id=False,
        unsupported_targets=(),
    ):
        self.store = FakeStore()
        self.rivals = list(rivals)
        self.spells = spells or {
            identity: [{"spellId": 700 + identity, "level": 1}]
            for identity in self.rivals
        }
        self.effects = effects or {
            identity: {700 + identity: ("hurt_ai", 6)} for identity in self.rivals
        }
        self.projection_unsupported = set(projection_unsupported)
        self.move_then_cast = move_then_cast
        self.omit_actor = omit_actor
        self.mismatch_id = mismatch_id
        self.unsupported_targets = set(unsupported_targets)
        self.cells = [(x, 0, 0) for x in range(5)] + [(0, 0, 1)]
        self.edges = [((3, 0, 0), (2, 0, 0))]
        self.graph_key = self.store.save(geometry(self.cells, self.edges))
        self.actors = [actor(AI_ID, 1, (0, 0, 0)), actor(ALLY_ID, 1, (0, 0, 1))]
        for index, identity in enumerate(self.rivals):
            position = (3 - index, 0, 0)
            self.actors.append(actor(identity, 0, position, hp=30))
        self.source = {row["id"]: row for row in self.actors}
        self.state = dict(
            key="source-state",
            nativeContext=self.graph_key,
            actors=deepcopy(self.actors),
            phase="active",
            currentId=AI_ID,
            turnId=5,
            stateRevision=97,
        )
        self.states = {}
        self.preview_log = []
        self.sequence = 0
        self.metadata = {}

    def query(self, query):
        query_id = "invalid" if self.mismatch_id else query["id"]
        operation, key = query["operation"], query["state"]
        if operation == "project_turn":
            rival = query["actorId"]
            if rival in self.projection_unsupported:
                return {
                    "id": query_id,
                    "supported": False,
                    "unknownDependencies": ["initiative_projection_unavailable"],
                }
            result_key = f"projected-{rival}"
            result = dict(
                key=result_key,
                nativeContext=self.graph_key,
                actors=deepcopy(self.actors),
                phase="active",
                currentId=rival,
                turnId=6,
                stateRevision=98,
            )
            self.states[result_key] = dict(public=result, rival=rival, used=False)
            return {"id": query_id, "supported": True, "result": result}
        if operation == "repertoire":
            current = self.states[key]
            rival = query.get("actorId", current["rival"])
            spells = [] if current["used"] else deepcopy(self.spells.get(rival, []))
            metadata_key = self.store.save(encode({"spells": spells}))
            return {
                "id": query_id,
                "supported": True,
                "result": {"nativeMetadata": metadata_key},
            }
        if operation == "preview":
            current = self.states[key]
            rival = current["rival"]
            action = deepcopy(query["action"])
            self.preview_log.append((key, action))
            if action.get("targetId") in self.unsupported_targets:
                return {
                    "id": query_id,
                    "supported": False,
                    "unknownDependencies": ["candidate_native_rule_unknown"],
                }
            rows = deepcopy(current["public"]["actors"])
            caster = next(row for row in rows if row["id"] == rival)
            ai = next(row for row in rows if row["id"] == AI_ID)
            used = current["used"]
            if action["type"] == "end_turn":
                used = True
            elif action["type"] == "move":
                caster["position"] = list(action["path"][-1])
                caster["mp"] -= 1
            elif action["type"] == "cast":
                # The fake oracle models one certified useful result. Before
                # moving, the same spell preview is supported but ineffective.
                for spell in self.effects.get(rival, {}):
                    if action["spellId"] != spell:
                        continue
                    kind, amount = self.effects[rival][spell]
                    expected_target = (
                        AI_ID
                        if kind == "hurt_ai"
                        else ALLY_ID
                        if kind == "hurt_ally"
                        else AI_ID
                    )
                    if action.get("targetId") == expected_target:
                        if not self.move_then_cast or caster["position"] == [2, 0, 0]:
                            if kind == "hurt_ai":
                                ai["hp"] = max(0, ai["hp"] - amount)
                            elif kind == "hurt_ally":
                                ally = next(row for row in rows if row["id"] == ALLY_ID)
                                ally["hp"] = max(0, ally["hp"] - amount)
                used = True
            self.sequence += 1
            result_key = f"result-{rival}-{self.sequence}"
            result_rows = (
                rows
                if self.omit_actor is None
                else [r for r in rows if r["id"] != self.omit_actor]
            )
            result = dict(
                key=result_key,
                nativeContext=self.graph_key,
                actors=result_rows,
                phase="active",
                currentId=rival,
                turnId=6,
                stateRevision=98 + self.sequence,
            )
            self.states[result_key] = dict(public=result, rival=rival, used=used)
            return {"id": query_id, "supported": True, "result": result}
        raise AssertionError(query)


def run_forecast(provider, state=None, **limits):
    state = state or provider.state
    coroutine = forecast(state, AI_ID, provider.store, DEFAULT_WEIGHTS, **limits)
    query = next(coroutine)
    while True:
        answer = provider.query(query)
        try:
            query = coroutine.send(answer)
        except StopIteration as completed:
            return completed.value


class QueryThreatTests(unittest.TestCase):
    def test_exact_native_cast_reports_effective_risk(self):
        provider = FakeProvider(rivals=(9,), effects={9: {709: ("hurt_ai", 7)}})

        result = run_forecast(provider, nodes=64, beam=16)

        # A certified cast supplies a lower bound, but the provider leaves
        # the rival active at the search horizon with possible continuations.
        self.assertFalse(result["complete"])
        self.assertIsNone(result["risk"])
        self.assertEqual(result["knownLowerBound"], 7)
        self.assertEqual(result["rivals"][0]["actorId"], 9)
        self.assertEqual(result["rivals"][0]["mode"], "approximate")
        self.assertEqual(result["rivals"][0]["risk"], 7)

    def test_native_move_then_cast_is_explored_within_two_ply(self):
        provider = FakeProvider(
            rivals=(9,), effects={9: {709: ("hurt_ai", 6)}}, move_then_cast=True
        )

        result = run_forecast(provider, depth=2, beam=16, nodes=64)

        self.assertEqual(result["knownLowerBound"], 6)
        self.assertIsNone(result["risk"])
        self.assertFalse(result["complete"])
        projected = "projected-9"
        self.assertIn(
            (projected, {"type": "move", "path": [[2, 0, 0]]}), provider.preview_log
        )
        self.assertTrue(
            any(
                key != projected and action["type"] == "cast"
                for key, action in provider.preview_log
            )
        )

    def test_every_living_rival_gets_independent_response_and_risk_sums(self):
        provider = FakeProvider(
            rivals=(9, 10),
            effects={9: {709: ("hurt_ai", 3)}, 10: {710: ("hurt_ally", 5)}},
        )

        result = run_forecast(provider, depth=1, beam=16, nodes=64)

        self.assertEqual([entry["actorId"] for entry in result["rivals"]], [9, 10])
        self.assertEqual(result["knownLowerBound"], 8)
        self.assertIsNone(result["risk"])
        self.assertFalse(result["complete"])

    def test_depth_exhaustion_does_not_certify_move_only_zero_risk(self):
        provider = FakeProvider(move_then_cast=True)

        result = run_forecast(provider, depth=1, nodes=64, beam=64)

        self.assertEqual(result["knownLowerBound"], 0)
        self.assertIsNone(result["risk"])
        self.assertFalse(result["complete"])
        self.assertIn("rival_response_depth_exhausted", result["unknownDependencies"])
        self.assertNotIn(
            "rival_candidate_budget_exhausted", result["unknownDependencies"]
        )

    def test_beam_pruning_keeps_observed_risk_and_reports_unexplored_responses(self):
        provider = FakeProvider()

        result = run_forecast(provider, depth=1, nodes=64, beam=1)

        self.assertEqual(result["knownLowerBound"], 6)
        self.assertIsNone(result["risk"])
        self.assertIn("rival_response_beam_pruned", result["unknownDependencies"])

    def test_terminal_native_outcomes_can_complete_within_depth_limit(self):
        class TerminalProvider(FakeProvider):
            def query(self, query):
                answer = super().query(query)
                if query["operation"] == "preview" and answer["supported"]:
                    # This oracle certifies that each action ends the turn.
                    # No live outgoing continuation remains to truncate.
                    answer["result"]["currentId"] = AI_ID
                return answer

        result = run_forecast(TerminalProvider(), depth=1, nodes=64, beam=1)

        self.assertTrue(result["complete"])
        self.assertEqual(result["risk"], 6)
        self.assertEqual(result["unknownDependencies"], [])

    def test_unsupported_projection_reports_unknown_instead_of_zero_risk(self):
        provider = FakeProvider(rivals=(9,), projection_unsupported=(9,))

        result = run_forecast(provider)

        self.assertIsNone(result["risk"])
        self.assertEqual(result["knownLowerBound"], 0)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["rivals"][0]["risk"])
        self.assertIn(
            "initiative_projection_unavailable", result["unknownDependencies"]
        )

    def test_candidate_budget_adds_explicit_dependency_and_keeps_lower_bound(self):
        provider = FakeProvider(rivals=(9,), effects={9: {709: ("hurt_ai", 4)}})

        result = run_forecast(provider, nodes=1)

        self.assertIsNone(result["risk"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["knownLowerBound"], 4)
        self.assertIn("rival_candidate_budget_exhausted", result["unknownDependencies"])

    def test_supported_outcome_and_other_unsupported_previews_keep_lower_bound_unknown(
        self,
    ):
        provider = FakeProvider(
            rivals=(9,),
            effects={9: {709: ("hurt_ai", 4)}},
            unsupported_targets=(ALLY_ID,),
        )

        result = run_forecast(provider, nodes=64, depth=1, beam=16)

        self.assertIsNone(result["risk"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["knownLowerBound"], 4)
        self.assertEqual(result["rivals"][0]["risk"], 4)
        self.assertIn("candidate_native_rule_unknown", result["unknownDependencies"])

    def test_mismatched_native_query_response_id_is_fatal(self):
        provider = FakeProvider(rivals=(9,), mismatch_id=True)

        with self.assertRaisesRegex(ValueError, "Invalid native rival response"):
            run_forecast(provider)

    def test_preview_that_omits_source_roster_actor_is_fatal(self):
        provider = FakeProvider(
            rivals=(9,), omit_actor=ALLY_ID, effects={9: {709: ("hurt_ai", 2)}}
        )

        with self.assertRaisesRegex(ValueError, "omitted existing actor"):
            run_forecast(provider, depth=1, nodes=1)


if __name__ == "__main__":
    unittest.main()
