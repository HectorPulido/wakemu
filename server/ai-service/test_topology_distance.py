import unittest
from unittest.mock import patch

from topology_distance import measure
from query_search import _metrics, candidates
from test_query_search import actor, make_graph, fixture, run_search
from native_context import NativeGraph


class TopologyDistanceTests(unittest.TestCase):
    def test_shared_reverse_keeps_direction_height_and_current_occupancy(self):
        from topology_distance import directed_adjacencies, distance_field_from_reverse

        start, stair, goal = (0, 0, 0), (-1, 0, 0), (0, 0, 1)
        forward, reverse = directed_adjacencies(
            [(start, stair), (stair, goal)], cells={start, stair, goal}
        )
        self.assertEqual(forward[start], {stair})
        self.assertEqual(
            distance_field_from_reverse(reverse, {goal}, set()),
            {goal: 0, stair: 1, start: 2},
        )
        self.assertEqual(
            distance_field_from_reverse(reverse, {goal}, {stair}), {goal: 0}
        )
        self.assertEqual(
            distance_field_from_reverse(reverse, {start}, set()), {start: 0}
        )

    def test_bidirectional_derivation_rejects_edges_outside_complete_cells(self):
        from topology_distance import directed_adjacencies

        start, unknown = (0, 0, 0), (0, 0, 1)
        with self.assertRaisesRegex(ValueError, "outside complete walkable"):
            directed_adjacencies([(start, unknown)], cells={start})

    def test_frozen_adjacency_is_reused_but_occupancy_and_geometry_stay_fresh(self):
        import topology_distance as topology
        from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet

        topology._immutable_reverse.cache_clear()
        a, b, c = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        cells = ImmutableTerrainSet({a, b, c})
        edges = ImmutableTerrainSet({(a, b), (b, c)})
        actors = [actor(1, 1, a), actor(2, 1, b), actor(3, 0, c)]
        with patch.object(topology, "_reverse", wraps=topology._reverse) as reverse:
            self.assertIsNone(measure(cells, edges, actors)["topologyDistances"]["1"])
            actors[1]["hp"] = 0
            self.assertEqual(measure(cells, edges, actors)["topologyDistances"]["1"], 2)
            self.assertEqual(reverse.call_count, 1)
            changed = ImmutableTerrainSet({(a, c)})
            self.assertEqual(
                measure(cells, changed, actors)["topologyDistances"]["1"], 1
            )
            self.assertEqual(reverse.call_count, 2)
            with self.assertRaisesRegex(ValueError, "outside complete walkable"):
                measure(ImmutableTerrainSet({a}), edges, actors)
        topology._immutable_reverse.cache_clear()

    def test_mutable_edges_are_revalidated_after_in_place_change(self):
        a, b = (0, 0, 0), (0, 0, 1)
        cells, edges = {a, b}, {(a, b)}
        actors = [actor(1, 1, a), actor(2, 0, b)]
        self.assertEqual(measure(cells, edges, actors)["topologyDistances"]["1"], 1)
        edges.clear()
        self.assertIsNone(measure(cells, edges, actors)["topologyDistances"]["1"])

    def test_cached_topology_does_not_bypass_the_native_deadline(self):
        from native_deadline import bounded
        from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet

        a, b = (0, 0, 0), (1, 0, 0)
        cells, edges = ImmutableTerrainSet({a, b}), ImmutableTerrainSet({(a, b)})
        actors = [actor(1, 1, a), actor(2, 0, b)]
        self.assertEqual(measure(cells, edges, actors)["topologyDistances"]["1"], 1)
        now = [0]
        with bounded(1, clock=lambda: now[0]):
            now[0] = 2
            with self.assertRaises(TimeoutError):
                measure(cells, edges, actors)

    def test_support_approach_uses_directed_xyz_wounded_allies_and_unknown_is_not_zero(
        self,
    ):
        origin, stair, goal = (0, 0, 0), (-1, 0, 0), (0, 0, 1)
        actors = [actor(1, 1, origin), actor(2, 1, goal, hp=10), actor(3, 0, (1, 0, 0))]
        cells = {origin, stair, goal, (1, 0, 0)}
        edges = {(origin, stair), (stair, goal), (origin, (1, 0, 0))}
        fact = measure(cells, edges, actors, actor_id=1)["nativeSupportApproach"]
        self.assertEqual(fact, dict(actorId=1, targetIds=[2], distance=2))
        self.assertIsNone(
            measure(cells, None, actors, actor_id=1)["nativeSupportApproach"][
                "distance"
            ]
        )
        self.assertIsNone(
            measure(cells, set(), actors, actor_id=1)["nativeSupportApproach"][
                "distance"
            ]
        )
        actors[1]["hp"] = actors[1]["max_hp"]
        self.assertEqual(
            measure(cells, edges, actors, actor_id=1)["nativeSupportApproach"][
                "targetIds"
            ],
            [],
        )
        actors[1]["hp"] = 0
        self.assertEqual(
            measure(cells, edges, actors, actor_id=1)["nativeSupportApproach"][
                "targetIds"
            ],
            [],
        )

    def test_candidate_order_promotes_stairs_without_removing_dead_end_alternative(
        self,
    ):
        origin, stair, upper, enemy, dead = (
            (0, 0, 0),
            (-1, 0, 0),
            (0, 0, 1),
            (1, 0, 1),
            (1, 0, 0),
        )
        cells = {origin, stair, upper, enemy, dead}
        edges = {(origin, dead), (origin, stair), (stair, upper), (upper, enemy)}
        state = dict(actors=[actor(1, 1, origin, mp=1), actor(2, 0, enemy)])
        actions = list(
            candidates(NativeGraph(make_graph(cells, edges)), state, {"spells": []}, 1)
        )
        self.assertEqual(actions[0], dict(type="move", path=[list(stair)]))
        self.assertIn(dict(type="move", path=[list(dead)]), actions)

    def test_inconsistent_edges_fail_without_inventing_unlisted_cells(self):
        actors = [actor(1, 1, (0, 0, 0)), actor(2, 0, (1, 0, 0))]
        with self.assertRaisesRegex(ValueError, "outside complete walkable"):
            measure({(0, 0, 0)}, {((0, 0, 0), (1, 0, 0))}, actors)

    def test_legacy_snapshot_is_explicitly_distinguished_from_unknown_topology(self):
        actors = [actor(1, 1, (0, 0, 0)), actor(2, 0, (2, 0, 1))]
        legacy = _metrics(dict(actors=actors), 1)
        self.assertEqual(legacy["position"], -0.5)
        self.assertEqual(legacy["position_basis"], "legacy_xy_heuristic")
        unknown = _metrics(dict(actors=actors, topologyDistances=None), 1)
        self.assertEqual(unknown["position"], 0)
        self.assertEqual(unknown["position_basis"], "unknown_topology")

    def test_unreachable_metric_uses_common_reference_when_geometry_changes(self):
        actors = [actor(1, 1, (0, 0, 0)), actor(2, 0, (2, 0, 1))]
        before = dict(actors=actors, topologyDistances={"1": None}, topologyCellCount=4)
        after = dict(actors=actors, topologyDistances={"1": None}, topologyCellCount=3)
        self.assertEqual(
            _metrics(before, 1, unreachable_penalty=5)["position"],
            _metrics(after, 1, unreachable_penalty=5)["position"],
        )

    def test_inactive_actor_does_not_require_a_live_topology_distance(self):
        actors = [actor(1, 1, (0, 0, 0), hp=0), actor(2, 0, (2, 0, 1))]
        result = _metrics(
            dict(actors=actors, topologyDistances={"2": 0}, topologyCellCount=3), 1
        )
        self.assertEqual(result["position_basis"], "inactive_actor")

    def test_self_killing_preview_does_not_gain_position_or_break_search(self):
        session = fixture(
            [dict(spellId=55, level=1)], effects={55: "friendly_fire"}, edges=[]
        )
        session.envelope["root"]["actors"][0]["hp"] = 10
        session.envelope["root"].update(
            measure(session.cells, session.edges, session.envelope["root"]["actors"])
        )
        original = session.request

        def native_response(query):
            reply = original(query)
            if query["operation"] == "preview" and reply.get("supported"):
                state = reply["result"]
                state.update(measure(session.cells, session.edges, state["actors"]))
            return reply

        session.request = native_response
        result = run_search(session)
        self.assertEqual(result["action"], {"type": "end_turn"})
        self.assertEqual(
            result["positionEvidence"]["rootUtility"],
            result["positionEvidence"]["selectedUtility"],
        )
        self.assertEqual(session.envelope["root"]["actors"][0]["hp"], 10)

    def test_vertical_path_can_improve_position_while_xy_distance_increases(self):
        origin, step, top, enemy = (0, 0, 0), (-1, 0, 0), (0, 0, 1), (1, 0, 1)
        cells = {origin, step, top, enemy}
        edges = {(origin, step), (step, top), (top, enemy)}
        actors = [actor(1, 1, origin), actor(2, 0, enemy)]
        root = dict(actors=actors, **measure(cells, edges, actors))
        moved = [dict(actors[0], position=list(step)), actors[1]]
        after = dict(actors=moved, **measure(cells, edges, moved))
        self.assertEqual(root["topologyDistances"]["1"], 3)
        self.assertEqual(after["topologyDistances"]["1"], 2)
        self.assertGreater(
            _metrics(after, 1)["position"], _metrics(root, 1)["position"]
        )

    def test_directed_edges_do_not_invent_reverse_or_other_height_access(self):
        a, b, high = (0, 0, 0), (1, 0, 0), (1, 0, 1)
        actors = [actor(1, 1, a), actor(2, 0, b), actor(3, 0, high)]
        result = measure({a, b, high}, {(a, b)}, actors)
        self.assertEqual(result["topologyDistances"]["1"], 1)
        self.assertIsNone(result["topologyDistances"]["2"])
        self.assertIsNone(result["topologyDistances"]["3"])

    def test_occupied_ally_center_blocks_the_geometric_corridor(self):
        cells = {(x, 0, 0) for x in range(3)}
        edges = {((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2, 0, 0))}
        actors = [
            actor(1, 1, (0, 0, 0)),
            actor(2, 1, (1, 0, 0)),
            actor(3, 0, (2, 0, 0)),
        ]
        self.assertIsNone(measure(cells, edges, actors)["topologyDistances"]["1"])
        actors[1]["hp"] = 0
        self.assertEqual(measure(cells, edges, actors)["topologyDistances"]["1"], 2)

    def test_missing_topology_is_unknown_and_empty_topology_is_unreachable(self):
        actors = [actor(1, 1, (0, 0, 0)), actor(2, 0, (1, 0, 0))]
        cells = {(0, 0, 0), (1, 0, 0)}
        unknown = measure(cells, None, actors)
        self.assertIsNone(unknown["topologyDistances"])
        self.assertEqual(_metrics(dict(actors=actors, **unknown), 1)["position"], 0)
        unreachable = measure(cells, set(), actors)
        self.assertIsNone(unreachable["topologyDistances"]["1"])

    def test_height_alone_has_no_bonus_without_better_directed_distance(self):
        low, high, enemy = (0, 0, 0), (0, 0, 1), (1, 0, 0)
        cells, edges = {low, high, enemy}, {(low, enemy), (high, enemy)}
        a = [actor(1, 1, low), actor(2, 0, enemy)]
        b = [actor(1, 1, high), actor(2, 0, enemy)]
        self.assertEqual(
            _metrics(dict(actors=a, **measure(cells, edges, a)), 1)["position"],
            _metrics(dict(actors=b, **measure(cells, edges, b)), 1)["position"],
        )
