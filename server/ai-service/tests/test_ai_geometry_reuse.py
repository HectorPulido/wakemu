"""Geometry reuse keeps current occupancy and complete directed XYZ semantics."""
import random
import unittest

from wakfu_ai.planning import topology_distance as topology
from wakfu_ai.planning.movement_routes import hazard_route_alternatives
from wakfu_ai.native.native_deadline import bounded
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet


class GeometryReuseTests(unittest.TestCase):
    def setUp(self):
        topology._immutable_measure.cache_clear()

    def test_cached_facts_match_fresh_geometry_across_state_transitions(self):
        rng = random.Random(7331)
        cells = ImmutableTerrainSet(
            (x, y, z) for x in range(5) for y in range(3) for z in range(2)
        )
        points = sorted(cells)
        edges = ImmutableTerrainSet(
            (a, b) for a in points for b in points if a != b and rng.random() < 0.065
        )
        actors = [
            dict(
                id=i,
                team=i % 2,
                position=points[i * 4],
                hp=20,
                max_hp=20,
                registeredSummon=i == 4,
            )
            for i in range(6)
        ]
        for _ in range(100):
            chosen = rng.choice(actors)
            chosen.update(
                hp=rng.choice([0, 1, 10, 20]),
                position=rng.choice(points),
                registeredSummon=rng.choice([True, False]),
            )
            actor_id = rng.choice([None, 0, 1, 4])
            expected = topology._measure(cells, edges, actors, actor_id=actor_id)
            self.assertEqual(
                topology.measure(cells, edges, actors, actor_id=actor_id), expected
            )

    def test_hp_only_change_reuses_bfs_but_wounding_death_and_move_invalidate(self):
        a, b, c = (0, 0, 0), (0, 0, 1), (1, 0, 1)
        cells = ImmutableTerrainSet([a, b, c])
        edges = ImmutableTerrainSet([(a, b), (b, c)])
        actors = [
            dict(id=1, team=1, position=a, hp=10, max_hp=20),
            dict(id=2, team=0, position=c, hp=10, max_hp=20),
        ]
        topology.measure(cells, edges, actors)
        actors[1]["hp"] = 9
        topology.measure(cells, edges, actors)
        self.assertEqual(topology._immutable_measure.cache_info().hits, 1)
        for update in [dict(team=1, hp=20), dict(position=b), dict(hp=0)]:
            actors[1].update(update)
            self.assertEqual(
                topology.measure(cells, edges, actors),
                topology._measure(cells, edges, actors),
            )
        self.assertEqual(topology._immutable_measure.cache_info().misses, 4)
        edges = ImmutableTerrainSet([(c, a)])
        self.assertEqual(
            topology.measure(cells, edges, actors),
            topology._measure(cells, edges, actors),
        )

    def test_public_mutation_and_expired_deadline_cannot_poison_reused_facts(self):
        a, b = (0, 0, 0), (0, 0, 1)
        cells, edges = ImmutableTerrainSet([a, b]), ImmutableTerrainSet([(a, b)])
        actors = [
            dict(id=1, team=1, position=a, hp=10, max_hp=20),
            dict(id=2, team=1, position=b, hp=10, max_hp=20),
        ]
        first = topology.measure(cells, edges, actors, actor_id=1)
        first["topologyDistances"]["1"] = 999
        first["nativeSupportApproach"]["targetIds"].clear()
        second = topology.measure(cells, edges, actors, actor_id=1)
        self.assertEqual(second["topologyDistances"]["1"], 0)
        self.assertEqual(second["nativeSupportApproach"]["targetIds"], [2])
        now = [0]
        with bounded(1, clock=lambda: now[0]):
            now[0] = 2
            with self.assertRaises(TimeoutError):
                topology.measure(cells, edges, actors, actor_id=1)

    def test_missing_support_source_does_not_require_unused_hp_maximum(self):
        a, b = (0, 0, 0), (1, 0, 0)
        cells, edges = ImmutableTerrainSet([a, b]), ImmutableTerrainSet([(a, b)])
        actors = [
            dict(id=1, team=1, position=a, hp=10),
            dict(id=2, team=0, position=b, hp=10),
        ]
        for actor_id in (None, 999):
            self.assertEqual(
                topology.measure(cells, edges, actors, actor_id=actor_id),
                topology._measure(cells, edges, actors, actor_id=actor_id),
            )

    def test_hazard_routes_keep_directed_height_and_occupied_cells(self):
        a, b, c, d, goal = ((0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1), (2, 0, 0))
        adjacency = {a: {b, c}, b: {goal}, c: {d}, d: {goal}, goal: {a}}
        routes = hazard_route_alternatives(adjacency, a, set(), 5, {b})
        self.assertIn((b, goal), routes)
        self.assertIn((c, d, goal), routes)
        blocked = hazard_route_alternatives(adjacency, a, {c}, 5, {b})
        self.assertNotIn((c, d, goal), blocked)
        self.assertEqual(hazard_route_alternatives(adjacency, goal, {a}, 5, {b}), ())


if __name__ == "__main__":
    unittest.main()
