"""AI-directed query search over complete, source-bound native states."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.context.native_context import NativeGraph, encode
from wakfu_ai.planning.query_search import candidates, search
from wakfu_ai.bridge.world_bridge import _json_bytes


ACTOR_ID = 1
ALLY_ID = 2
ENEMY_ID = 9


def actor(identity, team, position, hp=30, *, max_hp=30, ap=6, mp=3, wp=2):
    return dict(
        id=identity,
        team=team,
        controlled=identity != ENEMY_ID,
        position=list(position),
        hp=hp,
        max_hp=max_hp,
        armor=0,
        ap=ap,
        mp=mp,
        wp=wp,
    )


def make_graph(cells, edges, *, origin=(0, 0, 0)):
    fight = SimpleNamespace(
        walkable=frozenset(tuple(cell) for cell in cells),
        edges=frozenset((tuple(start), tuple(end)) for start, end in edges),
        future_native_field={"version": 7, "unknown": b"retained"},
    )
    runtime = SimpleNamespace(fight=fight, future_runtime_field="preserved")
    return encode({"runtime": runtime})


class FakeStore:
    def __init__(self):
        self.objects = {}

    def put_json(self, value):
        payload = _json_bytes(value)
        digest = hashlib.sha256(payload).hexdigest()
        self.objects[digest] = deepcopy(value)
        return digest

    def json(self, digest):
        if digest not in self.objects:
            raise ValueError("Missing full native graph")
        return deepcopy(self.objects[digest])


class FakeNativeSession:
    def __init__(
        self,
        *,
        spells,
        cells,
        edges,
        effects=None,
        cast_requires_move=False,
        reject_all=False,
        mismatch_id=False,
        outcome_features=None,
        feature_weights=None,
        feature_deltas=None,
        omit_features_for_spells=None,
    ):
        self.store = FakeStore()
        self.cells = [list(cell) for cell in cells]
        self.edges = list(edges)
        self.spells = spells
        self.effects = effects or {}
        self.cast_requires_move = cast_requires_move
        self.reject_all = reject_all
        self.mismatch_id = mismatch_id
        self.feature_deltas = feature_deltas or {}
        self.omit_features_for_spells = set(omit_features_for_spells or ())
        self.preview_actions = []
        self.states = {}
        self.root_actors = [
            actor(ACTOR_ID, 1, (0, 0, 0)),
            actor(ALLY_ID, 1, (0, 0, 1), hp=30),
            actor(ENEMY_ID, 0, (3, 0, 0), hp=30),
        ]
        self.root_graph = make_graph(self.cells, self.edges)
        graph_key = self.store.put_json(self.root_graph)
        self.root_state = dict(
            key="root-state",
            nativeContext=graph_key,
            actors=deepcopy(self.root_actors),
            phase="active",
            currentId=ACTOR_ID,
            turnId=4,
            stateRevision=97,
        )
        if outcome_features is not None:
            self.root_state["outcomeFeatures"] = deepcopy(outcome_features)
        self.states["root-state"] = dict(public=self.root_state, used=False)
        self.metadata = self.store.put_json(encode({"spells": deepcopy(spells)}))
        self.envelope = dict(
            protocol=3,
            requestId="query-search-test",
            sourceKey="source-bound-key",
            actor_id=ACTOR_ID,
            rootState="root-state",
            root=self.root_state,
            policy={
                "weights": {},
                "team": {},
                "limits": {"depth": 3, "beam": 8, "nodes": 96, "budgetMs": 10000},
            },
        )
        if feature_weights is not None:
            self.envelope["policy"]["featureWeights"] = deepcopy(feature_weights)

    def request(self, query):
        identity = query["id"]
        response_id = "wrong-id" if self.mismatch_id else identity
        if query["operation"] == "repertoire":
            state = self.states[query["state"]]
            spells = [] if state["used"] else self.spells
            metadata = self.store.put_json(encode({"spells": deepcopy(spells)}))
            return {
                "id": response_id,
                "supported": True,
                "result": {"nativeMetadata": metadata},
            }
        if query["operation"] != "preview":
            raise AssertionError(query)
        action = query["action"]
        self.preview_actions.append(deepcopy(action))
        if self.reject_all:
            return {
                "id": response_id,
                "supported": False,
                "unknownDependencies": ["candidate_native_rule_unknown"],
            }
        previous = self.states[query["state"]]
        actors = deepcopy(previous["public"]["actors"])
        ai = next(row for row in actors if row["id"] == ACTOR_ID)
        ally = next(row for row in actors if row["id"] == ALLY_ID)
        enemy = next(row for row in actors if row["id"] == ENEMY_ID)
        used = previous["used"]
        if action["type"] == "move":
            cell = action["path"][-1]
            ai["position"] = list(cell)
            ai["mp"] -= 1
        elif action["type"] == "cast":
            if self.cast_requires_move and ai["position"] == [0, 0, 0]:
                return {
                    "id": response_id,
                    "supported": False,
                    "unknownDependencies": ["spell_requires_positioning"],
                }
            target_id = action.get("targetId")
            effect = self.effects.get(action["spellId"], "none")
            if effect == "damage" and target_id == ENEMY_ID:
                enemy["hp"] = max(0, enemy["hp"] - 5)
            elif effect == "heal" and target_id == ALLY_ID:
                ally["hp"] = min(ally["max_hp"], ally["hp"] + 8)
            elif effect == "friendly_fire" and target_id == ENEMY_ID:
                enemy["hp"] = max(0, enemy["hp"] - 5)
                ai["hp"] -= 10
            elif effect == "safe_damage" and target_id == ENEMY_ID:
                enemy["hp"] = max(0, enemy["hp"] - 2)
            used = True
        else:
            return {
                "id": response_id,
                "supported": False,
                "unknownDependencies": ["unknown-action"],
            }
        key = f"state-{len(self.states)}"
        graph = make_graph(self.cells, self.edges, origin=tuple(ai["position"]))
        graph_key = self.store.put_json(graph)
        public = dict(
            key=key,
            nativeContext=graph_key,
            actors=actors,
            phase="active",
            currentId=ACTOR_ID if ai["hp"] > 0 else None,
            turnId=4,
            stateRevision=97 + len(self.states),
        )
        prior_features = previous["public"].get("outcomeFeatures")
        if prior_features is not None:
            public["outcomeFeatures"] = deepcopy(prior_features)
        if action["type"] == "cast":
            delta = self.feature_deltas.get(action["spellId"], {})
            if delta:
                values = public.setdefault("outcomeFeatures", {})
                for name, value in delta.items():
                    values[name] = values.get(name, 0) + value
            if action["spellId"] in self.omit_features_for_spells:
                public.pop("outcomeFeatures", None)
        self.states[key] = dict(public=public, used=used)
        return {"id": response_id, "supported": True, "result": public}


def run_search(session, *, clock=None):
    kwargs = {} if clock is None else {"clock": clock}
    coroutine = search(session.envelope, session.store, **kwargs)
    query = next(coroutine)
    while True:
        response = session.request(query)
        try:
            query = coroutine.send(response)
        except StopIteration as completed:
            return completed.value


def fixture(spells, *, cast_requires_move=False, effects=None, edges=None):
    cells = [(x, 0, 0) for x in range(4)] + [(0, 0, 1)]
    edges = [((0, 0, 0), (1, 0, 0))] if edges is None else edges
    return FakeNativeSession(
        spells=spells,
        cells=cells,
        edges=edges,
        cast_requires_move=cast_requires_move,
        effects=effects,
    )


class QuerySearchTests(unittest.TestCase):
    @staticmethod
    def _range_spell(spell_id, baseline, conditionals=()):
        return dict(
            spellId=spell_id,
            level=1,
            casting=dict(
                levels=[[baseline[0], baseline[1], []]],
                conditional=[dict(ranges=[[low, high]]) for low, high in conditionals],
            ),
        )

    def test_out_of_range_first_cast_moves_ahead_without_filtering_candidates(self):
        spell = self._range_spell(710, (1, 2))
        session = fixture([spell])
        state = deepcopy(session.root_state)
        graph = NativeGraph(session.root_graph)
        actions = list(candidates(graph, state, {"spells": [spell]}, ACTOR_ID))
        self.assertEqual([action["type"] for action in actions[:2]], ["move", "cast"])
        self.assertEqual(actions[1]["target"], [3, 0, 0])

        without_ranges = dict(spellId=710, level=1)
        fallback = list(
            candidates(graph, state, {"spells": [without_ranges]}, ACTOR_ID)
        )
        self.assertEqual([action["type"] for action in fallback[:2]], ["cast", "move"])
        self.assertEqual(
            Counter(json.dumps(action, sort_keys=True) for action in actions),
            Counter(json.dumps(action, sort_keys=True) for action in fallback),
        )

    def test_conditional_range_keeps_cast_first_when_it_can_cover_first_target(self):
        spell = self._range_spell(711, (1, 2), ((3, 3),))
        session = fixture([spell])
        actions = list(
            candidates(
                NativeGraph(session.root_graph),
                session.root_state,
                {"spells": [spell]},
                ACTOR_ID,
            )
        )
        self.assertEqual([action["type"] for action in actions[:2]], ["cast", "move"])
        self.assertEqual(actions[0]["target"], [3, 0, 0])

    def test_every_cast_stream_must_be_out_of_range_and_all_casts_remain(self):
        first = self._range_spell(715, (1, 2))
        second = self._range_spell(716, (1, 2))
        session = fixture([first, second])
        graph = NativeGraph(session.root_graph)
        state = session.root_state
        actions = list(candidates(graph, state, {"spells": [first, second]}, ACTOR_ID))
        self.assertEqual(
            [action["type"] for action in actions[:3]], ["move", "cast", "cast"]
        )
        actual = Counter(json.dumps(action, sort_keys=True) for action in actions)
        occupied = {
            tuple(row["position"]): row["id"]
            for row in state["actors"]
            if row["hp"] > 0
        }
        expected = Counter(
            json.dumps(
                dict(
                    type="cast",
                    spellId=spell["spellId"],
                    level=1,
                    target=cell,
                    **(
                        {"targetId": occupied[tuple(cell)]}
                        if tuple(cell) in occupied
                        else {}
                    ),
                ),
                sort_keys=True,
            )
            for spell in (first, second)
            for cell in session.cells
        )
        expected.update(
            json.dumps(action, sort_keys=True)
            for action in [{"type": "move", "path": [[1, 0, 0]]}]
        )
        self.assertEqual(actual, expected)

        conditionally_reachable = self._range_spell(716, (1, 2), ((3, 3),))
        actions = list(
            candidates(
                graph, state, {"spells": [first, conditionally_reachable]}, ACTOR_ID
            )
        )
        self.assertEqual([action["type"] for action in actions[:2]], ["cast", "move"])

    def test_missing_malformed_and_unknown_range_metadata_keep_cast_first(self):
        session = fixture([])
        graph = NativeGraph(session.root_graph)
        state = session.root_state
        variants = [
            dict(spellId=712, level=1),
            dict(
                spellId=712,
                level=1,
                casting={"levels": [[1, 2, []]], "conditional": "bad"},
            ),
            dict(
                spellId=712,
                level=1,
                casting={
                    "levels": [[1, 2, []]],
                    "conditional": [],
                    "futureRangeModel": "unknown",
                },
            ),
            dict(
                spellId=712,
                level=1,
                casting={
                    "levels": [[1, 2, []]],
                    "conditional": [dict(ranges=[[3, 3]], futureRule=True)],
                },
            ),
            dict(
                spellId=712,
                level=2,
                casting={"levels": [[1, 2, []]], "conditional": []},
            ),
        ]
        for spell in variants:
            with self.subTest(spell=spell):
                actions = list(candidates(graph, state, {"spells": [spell]}, ACTOR_ID))
                self.assertEqual(
                    [action["type"] for action in actions[:2]], ["cast", "move"]
                )

    def test_self_range_zero_and_heal_target_priority_are_preserved(self):
        session = fixture([])
        graph = NativeGraph(session.root_graph)
        state = deepcopy(session.root_state)
        self_spell = self._range_spell(713, (0, 0))
        actions = list(
            candidates(
                graph,
                state,
                {"spells": [self_spell]},
                ACTOR_ID,
                capability_evidence={(713, 1): {"protection"}},
            )
        )
        self.assertEqual([action["type"] for action in actions[:2]], ["cast", "move"])
        self.assertEqual(actions[0]["target"], [0, 0, 0])
        self.assertEqual(actions[0]["targetId"], ACTOR_ID)

        state["actors"][1]["position"] = [0, 0, 2]
        state["actors"][1]["hp"] = 20
        cells = session.cells + [[0, 0, 2]]
        heal_spell = self._range_spell(714, (1, 1))
        actions = list(
            candidates(
                NativeGraph(make_graph(cells, session.edges)),
                state,
                {"spells": [heal_spell]},
                ACTOR_ID,
                capability_evidence={(714, 1): {"healing"}},
            )
        )
        # Native allows-self is condition-selected and uses XY distance, so
        # another height cannot turn this hint into an out-of-range verdict.
        self.assertEqual([action["type"] for action in actions[:2]], ["cast", "move"])
        self.assertEqual(actions[0]["target"], [0, 0, 2])
        self.assertEqual(actions[0]["targetId"], ALLY_ID)

    def test_distinct_damage_and_heal_roles_keep_targets_and_candidate_corpus(self):
        session = fixture([])
        state = deepcopy(session.root_state)
        state["actors"][1]["position"] = [1, 0, 2]
        state["actors"][1]["hp"] = 20
        cells = session.cells + [[1, 0, 2]]
        graph = NativeGraph(make_graph(cells, session.edges))
        damage = self._range_spell(717, (2, 2))
        healing = self._range_spell(718, (2, 2))
        roles = {(717, 1): {"damage"}, (718, 1): {"healing"}}
        with_metadata = list(
            candidates(
                graph,
                state,
                {"spells": [damage, healing]},
                ACTOR_ID,
                capability_evidence=roles,
            )
        )
        without_metadata = list(
            candidates(
                graph,
                state,
                {
                    "spells": [
                        {"spellId": 717, "level": 1},
                        {"spellId": 718, "level": 1},
                    ]
                },
                ACTOR_ID,
                capability_evidence=roles,
            )
        )
        self.assertEqual(
            [action["type"] for action in with_metadata[:3]], ["move", "cast", "cast"]
        )
        self.assertEqual(with_metadata[1]["spellId"], 717)
        self.assertEqual(with_metadata[1]["targetId"], ENEMY_ID)
        first_heal = next(
            action
            for action in with_metadata
            if action["type"] == "cast" and action["spellId"] == 718
        )
        self.assertEqual(first_heal["targetId"], ALLY_ID)
        self.assertEqual(
            Counter(json.dumps(action, sort_keys=True) for action in with_metadata),
            Counter(json.dumps(action, sort_keys=True) for action in without_metadata),
        )

    def test_explicit_native_features_use_signed_root_relative_delta_and_weight(self):
        spells = [dict(spellId=501, level=1), dict(spellId=502, level=1)]
        session = FakeNativeSession(
            spells=spells,
            cells=[(0, 0, 0), (2, 0, 0)],
            edges=[],
            effects={501: "none", 502: "none"},
            outcome_features={"glyph_control": 12},
            feature_weights={"glyph_control": 2},
            feature_deltas={501: {"glyph_control": 4}, 502: {"glyph_control": -3}},
        )
        result = run_search(session)
        self.assertEqual(result["action"]["type"], "cast")
        self.assertEqual(result["action"]["spellId"], 501)
        self.assertEqual(result["components"]["feature:glyph_control"], 8)
        self.assertEqual(result["unknownFeatureDependencies"], [])

    def test_unweighted_native_feature_does_not_change_search_decision(self):
        session = FakeNativeSession(
            spells=[dict(spellId=503, level=1)],
            cells=[(0, 0, 0), (2, 0, 0)],
            edges=[],
            effects={503: "none"},
            outcome_features={"glyph_control": 12},
            feature_deltas={503: {"glyph_control": 50}},
        )
        result = run_search(session)
        self.assertEqual(result["action"], {"type": "end_turn"})
        self.assertFalse(
            any(name.startswith("feature:") for name in result["components"])
        )

    def test_missing_root_or_candidate_feature_is_unknown_and_never_scored(self):
        missing_root = FakeNativeSession(
            spells=[dict(spellId=504, level=1)],
            cells=[(0, 0, 0), (2, 0, 0)],
            edges=[],
            effects={504: "none"},
            feature_weights={"glyph_control": 2},
            feature_deltas={504: {"glyph_control": 50}},
        )
        root_missing_result = run_search(missing_root)
        self.assertEqual(root_missing_result["action"], {"type": "end_turn"})
        self.assertEqual(root_missing_result["components"], {})
        self.assertIn(
            "outcome_feature_missing_root:glyph_control",
            root_missing_result["unknownFeatureDependencies"],
        )

        missing_candidate = FakeNativeSession(
            spells=[dict(spellId=505, level=1)],
            cells=[(0, 0, 0), (2, 0, 0)],
            edges=[],
            effects={505: "none"},
            outcome_features={"glyph_control": 12},
            feature_weights={"glyph_control": 2},
            omit_features_for_spells={505},
        )
        candidate_missing_result = run_search(missing_candidate)
        self.assertEqual(candidate_missing_result["action"], {"type": "end_turn"})
        self.assertNotIn(
            "feature:glyph_control", candidate_missing_result["components"]
        )
        self.assertIn(
            "outcome_feature_missing_state:glyph_control",
            candidate_missing_result["unknownFeatureDependencies"],
        )

    def test_invalid_native_features_and_feature_weights_are_rejected(self):
        from wakfu_ai.planning.query_search import _metrics

        state = dict(
            actors=[actor(ACTOR_ID, 1, (0, 0, 0)), actor(ENEMY_ID, 0, (1, 0, 0))]
        )
        for features in (
            {"Glyph": 1},
            {"glyph": float("nan")},
            {"glyph": float("inf")},
        ):
            with self.assertRaises(ValueError):
                _metrics(dict(state, outcomeFeatures=features), ACTOR_ID)
        session = fixture([dict(spellId=506, level=1)])
        session.envelope["policy"]["featureWeights"] = {"Glyph": 1}
        with self.assertRaisesRegex(ValueError, "Invalid feature name"):
            run_search(session)
        session = fixture([dict(spellId=506, level=1)])
        session.envelope["policy"]["featureWeights"] = {"glyph_control": float("nan")}
        with self.assertRaisesRegex(ValueError, "Invalid feature weights"):
            run_search(session)

    def test_large_repertoire_interleaves_movement_and_preserves_every_cast_target(
        self,
    ):
        spells = [dict(spellId=100 + index, level=1) for index in range(20)]
        session = fixture(spells)
        actions = list(
            candidates(
                NativeGraph(session.root_graph),
                session.root_state,
                {"spells": spells},
                ACTOR_ID,
            )
        )
        self.assertEqual(
            [action["type"] for action in actions[:3]], ["cast", "move", "cast"]
        )
        self.assertEqual([actions[0]["spellId"], actions[2]["spellId"]], [100, 101])
        actual = Counter(
            (action["spellId"], tuple(action["target"]))
            for action in actions
            if action["type"] == "cast"
        )
        expected = Counter(
            (spell["spellId"], tuple(cell))
            for spell in spells
            for cell in session.cells
        )
        self.assertEqual(actual, expected)
        self.assertEqual(
            [action for action in actions if action["type"] == "move"],
            [{"type": "move", "path": [[1, 0, 0]]}],
        )

    def test_large_repertoire_does_not_starve_move_cast_under_three_previews(self):
        spells = [dict(spellId=100 + index, level=1) for index in range(20)]
        session = fixture(spells, cast_requires_move=True, effects={100: "damage"})
        session.envelope["policy"]["limits"]["nodes"] = 3
        result = run_search(session)
        self.assertEqual(
            [action["type"] for action in result["plan"]], ["move", "cast"]
        )
        self.assertEqual(result["plan"][-1]["spellId"], 100)

    def test_late_supported_spell_still_competes_after_unsupported_future_spells(self):
        spells = [dict(spellId=100 + index, level=1) for index in range(20)]
        session = fixture(spells, cast_requires_move=True, effects={119: "damage"})
        session.envelope["policy"]["limits"].update(nodes=60, depth=2)
        original = session.request

        def reject_unknown(query):
            action = query.get("action", {})
            if action.get("type") == "cast" and action["spellId"] != 119:
                session.preview_actions.append(deepcopy(action))
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["future_unimplemented_spell"],
                )
            return original(query)

        session.request = reject_unknown
        result = run_search(session)
        self.assertEqual(session.preview_actions[1]["type"], "move")
        self.assertEqual(
            [action["type"] for action in result["plan"]], ["move", "cast"]
        )
        self.assertEqual(result["plan"][-1]["spellId"], 119)

    def test_geometry_decoder_matches_plain_for_all_edges_and_retains_future_context(
        self,
    ):
        from wakfu_ai.planning.query_search import _fight, _sequence

        cells = [(x, y, (x + y) % 3) for x in range(8) for y in range(8)]
        edges = [
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        ]
        graph = NativeGraph(make_graph(cells, edges))
        before = deepcopy(graph.data)
        fight = _fight(graph)
        for field in ("walkable", "edges"):
            reference = graph.field(fight, field)
            expected = [graph.plain(item) for item in graph.resolve(reference)["items"]]
            self.assertEqual(_sequence(graph, reference), expected)
        self.assertEqual(graph.data, before)
        future = graph.plain(graph.field(fight, "future_native_field"))
        self.assertEqual(future, {"version": 7, "unknown": b"retained"})

    def test_geometry_decoder_does_not_share_mutable_results_or_hide_cycles(self):
        from wakfu_ai.planning.query_search import _sequence

        mutable = [1, 2, 3]
        value = (mutable,)
        graph = NativeGraph(encode([value, value]))
        decoded = _sequence(graph, graph.data["root"])
        decoded[0][0].append(4)
        self.assertEqual(decoded[1], ([1, 2, 3],))
        cycle = []
        value = (cycle,)
        cycle.append(value)
        graph = NativeGraph(encode([value]))
        with self.assertRaisesRegex(ValueError, "Cyclic native value"):
            _sequence(graph, graph.data["root"])
        graph = NativeGraph(encode([SimpleNamespace(future_field="retained")]))
        with self.assertRaisesRegex(ValueError, "requires field/reference navigation"):
            _sequence(graph, graph.data["root"])

    def test_first_cast_does_not_wait_for_complete_movement_graph_decoding(self):
        from wakfu_ai.planning.query_search import _sequence

        session = fixture([dict(spellId=987654, level=2)], effects={987654: "damage"})
        graph = NativeGraph(session.root_graph)
        stream = candidates(
            graph, session.root_state, {"spells": session.spells}, ACTOR_ID
        )
        with patch(
            "wakfu_ai.planning.query_search._sequence", wraps=_sequence
        ) as decode:
            first = next(stream)
            self.assertEqual(first["type"], "cast")
            self.assertEqual(first["targetId"], ENEMY_ID)
            self.assertEqual(decode.call_count, 1)
            rest = list(stream)
            self.assertEqual(decode.call_count, 2)
        self.assertIn(dict(type="move", path=[[1, 0, 0]]), rest)
        self.assertEqual(len([first] + rest), len(session.cells) + 1)

    def test_complete_routes_use_real_mp_directed_xyz_edges_and_keep_prefixes(self):
        state = dict(
            actors=[actor(ACTOR_ID, 1, (0, 0, 0), mp=3), actor(ENEMY_ID, 0, (3, 0, 1))]
        )
        cells = [(0, 0, 0), (1, 0, 0), (2, 0, 1), (3, 0, 1), (2, 0, 0)]
        edges = [((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2, 0, 1)), ((2, 0, 1), (3, 0, 1))]
        graph = NativeGraph(make_graph(cells, edges))
        actions = list(candidates(graph, state, {"spells": []}, ACTOR_ID))
        self.assertEqual(actions[0], {"type": "move", "path": [[1, 0, 0], [2, 0, 1]]})
        self.assertIn({"type": "move", "path": [[1, 0, 0]]}, actions)
        self.assertFalse(any([2, 0, 0] in action["path"] for action in actions))
        self.assertFalse(any([3, 0, 1] in action["path"] for action in actions))
        state["actors"][0]["mp"] = 1
        self.assertEqual(
            list(candidates(graph, state, {"spells": []}, ACTOR_ID)),
            [{"type": "move", "path": [[1, 0, 0]]}],
        )

    def test_initial_complete_preparation_does_not_consume_exploration_budget(self):
        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["policy"]["limits"] = dict(
            depth=1, beam=4, nodes=4, budgetMs=250
        )
        now = [0.0]
        generator = search(session.envelope, session.store, clock=lambda: now[0])
        query = next(generator)
        self.assertEqual(query["operation"], "repertoire")
        now[0] = 2.0  # Complete metadata preparation exceeded 250 ms.
        while True:
            try:
                query = generator.send(session.request(query))
            except StopIteration as result:
                decision = result.value
                break
        self.assertEqual(decision["action"]["type"], "cast")
        self.assertEqual(decision["action"]["targetId"], ENEMY_ID)
        self.assertLessEqual(decision["expanded"], 4)

    def test_root_cursor_is_revisited_after_a_continuation_quantum(self):
        session = fixture(
            [{"spellId": 100, "level": 1}],
            cast_requires_move=True,
            effects={100: "damage"},
        )
        session.envelope["policy"]["limits"].update(nodes=6, depth=4, probeQuantum=2)
        source_states = []
        original = session.request

        def observe(query):
            if query["operation"] == "preview":
                source_states.append(query["state"])
            return original(query)

        session.request = observe
        result = run_search(session)
        self.assertEqual(source_states[:2], ["root-state", "root-state"])
        self.assertNotEqual(source_states[2], "root-state")
        self.assertEqual(source_states[4], "root-state")
        self.assertEqual(result["searchBudgetEvidence"]["expandedByDepth"]["1"], 4)
        self.assertEqual(
            sum(result["searchBudgetEvidence"]["expandedByDepth"].values()),
            result["expanded"],
        )

    def test_global_beam_bounds_all_continuations_while_retaining_root_cursor(self):
        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["policy"]["limits"].update(beam=2, nodes=40, depth=4)
        result = run_search(session)
        self.assertLessEqual(
            result["searchBudgetEvidence"]["peakContinuationFrames"], 2
        )
        self.assertEqual(result["action"]["type"], "cast")
        self.assertGreater(result["searchBudgetEvidence"]["expandedByDepth"]["1"], 2)

    def test_small_node_budget_explores_movement_continuation_before_empty_targets(
        self,
    ):
        session = fixture(
            [{"spellId": 100, "level": 1}],
            cast_requires_move=True,
            effects={100: "damage"},
        )
        session.envelope["policy"]["limits"]["nodes"] = 3
        result = run_search(session)
        self.assertEqual(
            [action["type"] for action in result["plan"]], ["move", "cast"]
        )
        self.assertEqual(result["expanded"], 3)
        self.assertEqual(
            [action["type"] for action in session.preview_actions],
            ["cast", "move", "cast"],
        )
        self.assertEqual(session.preview_actions[-1]["targetId"], ENEMY_ID)

    def test_depth_one_resumes_all_candidates_without_refetching_repertoire(self):
        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["policy"]["limits"].update(depth=1, probeQuantum=1)
        queries = []
        original = session.request

        def observe(query):
            queries.append(query)
            return original(query)

        session.request = observe
        result = run_search(session)
        self.assertEqual(len([q for q in queries if q["operation"] == "repertoire"]), 1)
        self.assertEqual(result["expanded"], len(session.cells) + 1)
        self.assertEqual(
            {
                tuple(a["target"])
                for a in session.preview_actions
                if a["type"] == "cast"
            },
            {tuple(c) for c in session.cells},
        )

    def test_native_wait_does_not_starve_movement_after_rejected_cast(self):
        session = fixture(
            [{"spellId": 100, "level": 1}],
            cast_requires_move=True,
            effects={100: "damage"},
        )
        now = [0.0]
        generator = search(session.envelope, session.store, clock=lambda: now[0])
        query = next(generator)
        while True:
            response = session.request(query)
            now[0] += 0.4  # Each native query takes longer than the AI work budget.
            try:
                query = generator.send(response)
            except StopIteration as result:
                decision = result.value
                break
        self.assertEqual(
            [action["type"] for action in decision["plan"]], ["move", "cast"]
        )
        self.assertGreater(decision["searchBudgetEvidence"]["nativeWaitMs"], 250)

    def test_wall_time_slice_preserves_move_cast_plan_and_does_not_renew(self):
        session = fixture(
            [{"spellId": 100, "level": 1}],
            cast_requires_move=True,
            effects={100: "damage"},
        )
        session.envelope["nativeBudgetMs"] = 5000
        session.envelope["policy"]["searchTimeFraction"] = 0.5
        now = [0.0]
        coroutine = search(session.envelope, session.store, clock=lambda: now[0])
        query = next(coroutine)
        while True:
            response = session.request(query)
            now[0] += 0.4
            # Repeated hints cannot grant a new decision slice.
            response["nativeBudgetMs"] = 5000
            try:
                query = coroutine.send(response)
            except StopIteration as stopped:
                result = stopped.value
                break
        self.assertEqual(
            [action["type"] for action in result["plan"]], ["move", "cast"]
        )
        self.assertEqual(result["searchBudgetEvidence"]["decisionWallBudgetMs"], 2250)
        self.assertIn(
            "decision_wall_budget", result["searchBudgetEvidence"]["stopReasons"]
        )
        self.assertNotIn(
            "search_work_budget", result["searchBudgetEvidence"]["stopReasons"]
        )
        self.assertLessEqual(now[0], 2.65)
        self.assertGreater(now[0], 2.25)

    def test_default_and_override_search_time_fraction_set_decision_slice(self):
        cases = ((None, 1125, 0.25), (0.5, 2250, 0.5))
        for fraction, expected_budget, expected_fraction in cases:
            with self.subTest(searchTimeFraction=fraction):
                session = fixture([])
                session.envelope["nativeBudgetMs"] = 5000
                if fraction is not None:
                    session.envelope["policy"]["searchTimeFraction"] = fraction
                result = run_search(session, clock=lambda: 0.0)
                evidence = result["searchBudgetEvidence"]
                self.assertEqual(evidence["decisionWallBudgetMs"], expected_budget)
                self.assertEqual(evidence["searchTimeFraction"], expected_fraction)

    def test_invalid_search_time_fraction_is_rejected(self):
        for value in (True, 0, -1, 1.1, float("nan"), float("inf"), "0.5"):
            with self.subTest(value=value):
                session = fixture([])
                session.envelope["policy"]["searchTimeFraction"] = value
                with self.assertRaisesRegex(ValueError, "search time fraction"):
                    next(search(session.envelope, session.store))

    def test_owner_reserve_stops_search_without_requesting_native_work(self):
        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["nativeBudgetMs"] = 400
        coroutine = search(session.envelope, session.store, clock=lambda: 0)
        with self.assertRaises(StopIteration) as result:
            next(coroutine)
        self.assertEqual(result.exception.value["action"], {"type": "end_turn"})
        self.assertEqual(result.exception.value["expanded"], 0)

    def test_decreasing_owner_budget_keeps_best_certified_action(self):
        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["nativeBudgetMs"] = 5000
        coroutine = search(session.envelope, session.store, clock=lambda: 0)
        query = next(coroutine)
        self.assertEqual(query["operation"], "repertoire")
        query = coroutine.send(session.request(query))
        self.assertEqual(query["operation"], "preview")
        response = session.request(query)
        response["nativeBudgetMs"] = 400
        with self.assertRaises(StopIteration) as result:
            coroutine.send(response)
        self.assertEqual(result.exception.value["action"]["type"], "cast")
        self.assertEqual(result.exception.value["expanded"], 1)

    def test_local_work_still_consumes_the_search_budget(self):
        from wakfu_ai.planning.query_search import evaluate

        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["policy"]["limits"]["budgetMs"] = 250
        now = [0.0]

        def expensive_evaluation(*args, **kwargs):
            now[0] += 0.3
            return evaluate(*args, **kwargs)

        with patch(
            "wakfu_ai.planning.query_search.evaluate", side_effect=expensive_evaluation
        ):
            result = run_search(session, clock=lambda: now[0])
        self.assertEqual(result["expanded"], 1)
        self.assertEqual(result["action"]["type"], "cast")
        self.assertIn(
            "search_work_budget", result["searchBudgetEvidence"]["stopReasons"]
        )
        self.assertGreaterEqual(
            result["searchBudgetEvidence"]["searchWorkMsAtLastBudgetCheck"], 250
        )

    def test_complete_continuation_preparation_does_not_starve_its_first_candidate(
        self,
    ):
        session = fixture(
            [{"spellId": 100, "level": 1}],
            cast_requires_move=True,
            effects={100: "damage"},
        )
        session.envelope["policy"]["limits"].update(budgetMs=250, nodes=3)
        now = [0.0]
        original = session.store.json

        def expensive_read(key):
            now[0] += 0.4
            return original(key)

        session.store.json = expensive_read
        result = run_search(session, clock=lambda: now[0])
        self.assertEqual(
            [action["type"] for action in result["plan"]], ["move", "cast"]
        )
        self.assertGreater(result["searchBudgetEvidence"]["contextPreparationMs"], 250)

    def test_lazy_geometry_decode_does_not_discard_first_movement(self):
        from wakfu_ai.planning.query_search import _sequence

        session = fixture(
            [{"spellId": 100, "level": 1}],
            cast_requires_move=True,
            effects={100: "damage"},
        )
        session.envelope["policy"]["limits"].update(budgetMs=250, nodes=3)
        now = [0.0]

        def slow_geometry(*args):
            now[0] += 0.4
            return _sequence(*args)

        with patch(
            "wakfu_ai.planning.query_search._sequence", side_effect=slow_geometry
        ):
            result = run_search(session, clock=lambda: now[0])
        self.assertEqual(
            [action["type"] for action in result["plan"]], ["move", "cast"]
        )
        self.assertGreater(result["searchBudgetEvidence"]["contextPreparationMs"], 800)

    def test_lazy_geometry_decode_respects_owner_deadline(self):
        from wakfu_ai.planning.query_search import _sequence

        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["nativeBudgetMs"] = 1000
        now = [0.0]

        def slow_geometry(*args):
            now[0] += 0.6
            return _sequence(*args)

        with patch(
            "wakfu_ai.planning.query_search._sequence", side_effect=slow_geometry
        ):
            result = run_search(session, clock=lambda: now[0])
        self.assertEqual(result["expanded"], 0)
        self.assertEqual(result["action"], {"type": "end_turn"})

    def test_context_preparation_still_consumes_the_owner_deadline(self):
        session = fixture([{"spellId": 100, "level": 1}], effects={100: "damage"})
        session.envelope["nativeBudgetMs"] = 1000
        now = [0.0]
        original = session.store.json

        def expensive_read(key):
            now[0] += 0.4
            return original(key)

        session.store.json = expensive_read
        result = run_search(session, clock=lambda: now[0])
        self.assertEqual(result["expanded"], 0)
        self.assertEqual(result["action"], {"type": "end_turn"})

    def _slow_geometry_preparation(self, session, now, delay=0.4):
        from wakfu_ai.planning import query_search

        original_sorted = sorted
        original_adjacencies = query_search.directed_adjacencies
        target_cells = {tuple(cell) for cell in session.cells}
        observed = {"sorted": 0.0, "adjacencies": 0.0}

        def delayed_sorted(values, *args, **kwargs):
            result = original_sorted(values, *args, **kwargs)
            try:
                signature = {tuple(value) for value in result}
            except TypeError:
                signature = set()
            if kwargs.get("key") is not None and signature == target_cells:
                now[0] += delay
                observed["sorted"] += delay
            return result

        def delayed_adjacencies(*args, **kwargs):
            now[0] += delay
            observed["adjacencies"] += delay
            return original_adjacencies(*args, **kwargs)

        return query_search, delayed_sorted, delayed_adjacencies, observed

    def test_slow_target_sort_and_adjacencies_are_excluded_from_work_budget(self):
        from wakfu_ai.planning import query_search

        session = fixture([])
        session.envelope["nativeBudgetMs"] = 5000
        session.envelope["policy"]["limits"].update(budgetMs=250, nodes=4, depth=1)
        now = [0.0]
        (
            module,
            delayed_sorted,
            delayed_adjacencies,
            observed,
        ) = self._slow_geometry_preparation(session, now)
        with patch.object(module, "sorted", delayed_sorted, create=True), patch.object(
            module, "directed_adjacencies", delayed_adjacencies
        ):
            result = run_search(session, clock=lambda: now[0])

        self.assertEqual(observed, {"sorted": 0.4, "adjacencies": 0.4})
        self.assertGreater(result["searchBudgetEvidence"]["contextPreparationMs"], 700)
        self.assertGreater(result["expanded"], 0)
        self.assertNotIn(
            "search_work_budget", result["searchBudgetEvidence"]["stopReasons"]
        )
        self.assertNotIn(
            "decision_wall_budget", result["searchBudgetEvidence"]["stopReasons"]
        )

    def test_slow_geometry_preparation_still_consumes_decision_wall_budget(self):
        from wakfu_ai.planning import query_search

        session = fixture([])
        session.envelope["nativeBudgetMs"] = 2000
        session.envelope["policy"]["searchTimeFraction"] = 0.5
        session.envelope["policy"]["limits"].update(budgetMs=250, nodes=4, depth=1)
        now = [0.0]
        (
            module,
            delayed_sorted,
            delayed_adjacencies,
            observed,
        ) = self._slow_geometry_preparation(session, now)
        with patch.object(module, "sorted", delayed_sorted, create=True), patch.object(
            module, "directed_adjacencies", delayed_adjacencies
        ):
            result = run_search(session, clock=lambda: now[0])

        self.assertEqual(observed, {"sorted": 0.4, "adjacencies": 0.4})
        evidence = result["searchBudgetEvidence"]
        self.assertEqual(evidence["decisionWallBudgetMs"], 750)
        self.assertGreater(evidence["contextPreparationMs"], 700)
        self.assertEqual(result["expanded"], 0)
        self.assertEqual(result["action"], {"type": "end_turn"})
        self.assertIn("decision_wall_budget", evidence["stopReasons"])
        self.assertNotIn("search_work_budget", evidence["stopReasons"])

    def test_invalid_owner_budget_hints_are_rejected(self):
        for value in (True, -1, float("nan"), float("inf"), "500"):
            with self.subTest(value=value):
                session = fixture([])
                session.envelope["nativeBudgetMs"] = value
                with self.assertRaisesRegex(ValueError, "owner budget hint"):
                    next(search(session.envelope, session.store))

    def test_supported_and_unsupported_query_hints_bound_remaining_search(self):
        for rejected in (False, True):
            with self.subTest(rejected=rejected):
                session = fixture(
                    [{"spellId": 100, "level": 1}], effects={100: "damage"}
                )
                session.reject_all = rejected
                native_request = session.request
                now = [0.0]

                def request(query):
                    response = native_request(query)
                    now[0] += 0.1
                    # A generous repertoire hint keeps search open. The first
                    # preview then narrows the owner deadline to exactly the
                    # 500 ms commit reserve, regardless of whether it certifies.
                    response["nativeBudgetMs"] = (
                        10000 if query["operation"] == "repertoire" else 500
                    )
                    return response

                coroutine = search(
                    session.envelope, session.store, clock=lambda: now[0]
                )
                query = next(coroutine)
                while True:
                    try:
                        query = coroutine.send(request(query))
                    except StopIteration as result:
                        decision = result.value
                        break

                self.assertEqual(len(session.preview_actions), 1)
                self.assertEqual(decision["expanded"], 1)
                self.assertEqual(bool(decision["plan"]), not rejected)

    def test_search_finds_move_then_cast_from_native_directed_edge(self):
        session = fixture(
            [{"spellId": 100, "level": 1}],
            cast_requires_move=True,
            effects={100: "damage"},
        )

        result = run_search(session)

        self.assertEqual(result["protocol"], 3)
        self.assertEqual(result["sourceKey"], session.envelope["sourceKey"])
        self.assertEqual(
            result["plan"],
            [
                {"type": "move", "path": [[1, 0, 0]]},
                {
                    "type": "cast",
                    "spellId": 100,
                    "level": 1,
                    "target": [3, 0, 0],
                    "targetId": ENEMY_ID,
                },
            ],
        )
        self.assertEqual(result["action"], result["plan"][0])
        self.assertGreater(result["components"]["damage"], 0)

    def test_search_prefers_effective_heal_and_rejects_friendly_fire(self):
        healing = fixture(
            [{"spellId": 200, "level": 1}], effects={200: "heal"}, edges=[]
        )
        ally = next(
            row for row in healing.envelope["root"]["actors"] if row["id"] == ALLY_ID
        )
        ally["hp"] = 20
        # Keep the complete root state consistent with its public actor snapshot.
        healing.root_state["actors"] = deepcopy(healing.envelope["root"]["actors"])
        result = run_search(healing)
        self.assertEqual(
            result["action"],
            {
                "type": "cast",
                "spellId": 200,
                "level": 1,
                "target": [0, 0, 1],
                "targetId": ALLY_ID,
            },
        )
        self.assertEqual(result["components"]["healing"], 8)

        attack = fixture(
            [{"spellId": 300, "level": 1}, {"spellId": 301, "level": 1}],
            effects={300: "friendly_fire", 301: "safe_damage"},
            edges=[],
        )
        attack.envelope["root"]["actors"][0]["hp"] = 12
        attack.root_state["actors"] = deepcopy(attack.envelope["root"]["actors"])
        safe = run_search(attack)
        self.assertEqual(
            safe["action"],
            {
                "type": "cast",
                "spellId": 301,
                "level": 1,
                "target": [3, 0, 0],
                "targetId": ENEMY_ID,
            },
        )
        self.assertEqual(safe["components"]["healing"], 0)
        self.assertEqual(safe["components"]["damage"], 2)

    def test_unsupported_previews_are_discarded_and_report_dependencies(self):
        session = fixture([{"spellId": 400, "level": 1}], effects={400: "damage"})
        session.reject_all = True

        result = run_search(session)

        self.assertEqual(result["action"], {"type": "end_turn"})
        self.assertGreater(result["expanded"], 1)
        self.assertIn("candidate_native_rule_unknown", result["unknownDependencies"])

    def test_mismatched_response_id_is_fatal(self):
        session = fixture([{"spellId": 500, "level": 1}], effects={500: "damage"})
        session.mismatch_id = True
        with self.assertRaisesRegex(ValueError, "Invalid native query response"):
            run_search(session)

    def test_node_and_depth_budgets_bound_only_search_not_native_graph(self):
        node_limited = fixture([{"spellId": 600, "level": 1}], effects={600: "damage"})
        node_limited.envelope["policy"]["limits"].update(nodes=1)
        result = run_search(node_limited)
        self.assertEqual(result["expanded"], 1)
        self.assertEqual(len(node_limited.preview_actions), 1)

        depth_limited = fixture(
            [{"spellId": 601, "level": 1}],
            cast_requires_move=True,
            effects={601: "damage"},
        )
        depth_limited.envelope["policy"]["limits"].update(depth=1)
        result = run_search(depth_limited)
        self.assertEqual(result["expanded"], 6)
        self.assertEqual(result["action"], {"type": "move", "path": [[1, 0, 0]]})
        self.assertEqual(len(result["plan"]), 1)

    def test_candidate_movement_uses_only_present_directed_edges(self):
        session = fixture([], effects={})
        # The actor is at cell 1, but the graph only exports 0 -> 1.
        state = deepcopy(session.root_state)
        state["actors"][0]["position"] = [1, 0, 0]
        graph = NativeGraph(make_graph(session.cells, session.edges))
        actions = list(candidates(graph, state, {"spells": []}, ACTOR_ID))
        self.assertNotIn({"type": "move", "path": [[0, 0, 0]]}, actions)
        self.assertFalse(any(action["type"] == "move" for action in actions))

        graph = NativeGraph(make_graph(session.cells, [((1, 0, 0), (0, 0, 0))]))
        actions = list(candidates(graph, state, {"spells": []}, ACTOR_ID))
        self.assertEqual(actions, [{"type": "move", "path": [[0, 0, 0]]}])


if __name__ == "__main__":
    unittest.main()
