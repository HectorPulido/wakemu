"""Navigation facts distinguish allied obstruction from impassable terrain."""
import unittest

from wakfu_ai.planning import topology_distance as topology
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet


def actor(identity, team, position, *, summon=False):
    return dict(
        id=identity,
        team=team,
        position=position,
        hp=20,
        max_hp=20,
        registeredSummon=summon,
    )


class AllyRelaxedTopologyTests(unittest.TestCase):
    def tearDown(self):
        topology._immutable_measure.cache_clear()
        topology._immutable_reverse.cache_clear()

    def test_ally_corridor_stays_strictly_blocked_but_has_navigation_progress(self):
        a, b, c, d = ((0, 0, 0), (1, 0, 0), (2, 0, 1), (3, 0, 1))
        cells, edges = {a, b, c, d}, {(a, b), (b, c), (c, d)}
        actors = [actor(1, 1, a), actor(2, 1, c), actor(3, 0, d)]
        before = topology.measure(cells, edges, iter(actors), actor_id=1)
        self.assertIsNone(before["topologyDistances"]["1"])
        self.assertEqual(before["allyRelaxedTopologyDistances"]["1"], 3)
        actors[0]["position"] = b
        after = topology.measure(cells, edges, actors, actor_id=1)
        self.assertIsNone(after["topologyDistances"]["1"])
        self.assertEqual(after["allyRelaxedTopologyDistances"]["1"], 2)

    def test_true_disconnection_and_unknown_edges_remain_unknown(self):
        a, b, c = (0, 0, 0), (1, 0, 0), (0, 0, 1)
        actors = [actor(1, 1, a), actor(2, 1, b), actor(3, 0, c)]
        facts = topology.measure({a, b, c}, {(a, b)}, actors, actor_id=1)
        self.assertIsNone(facts["topologyDistances"]["1"])
        self.assertIsNone(facts["allyRelaxedTopologyDistances"]["1"])
        self.assertIsNone(
            topology.measure({a, b, c}, None, actors)["allyRelaxedTopologyDistances"]
        )

    def test_hostile_summon_remains_a_blocker_for_primary_navigation(self):
        a, b, c, d = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0))
        actors = [
            actor(1, 1, a),
            actor(2, 1, b),
            actor(3, 0, c, summon=True),
            actor(4, 0, d),
        ]
        facts = topology.measure({a, b, c, d}, {(a, b), (b, c), (c, d)}, actors)
        self.assertIsNone(facts["topologyDistances"]["1"])
        self.assertEqual(facts["allyRelaxedTopologyDistances"]["1"], 2)
        self.assertIsNone(facts["allyRelaxedPrimaryTopologyDistances"]["1"])
        # Shared occupancy must not turn a hostile summon into a relaxed ally.
        actors[1]["position"] = c
        facts = topology.measure({a, b, c, d}, {(a, b), (b, c), (c, d)}, actors)
        self.assertIsNone(facts["allyRelaxedPrimaryTopologyDistances"]["1"])
        actors[2]["hp"] = 0
        facts = topology.measure({a, b, c, d}, {(a, b), (b, c), (c, d)}, actors)
        self.assertEqual(facts["allyRelaxedTopologyDistances"]["1"], 3)

    def test_relaxed_fields_are_private_cached_copies_and_occupancy_is_fresh(self):
        a, b, c, d = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0))
        cells = ImmutableTerrainSet({a, b, c, d})
        edges = ImmutableTerrainSet({(a, b), (b, c), (c, d), (a, c)})
        actors = [
            actor(1, 1, a),
            actor(2, 1, b),
            actor(3, 0, c, summon=True),
            actor(4, 0, d),
        ]
        first = topology.measure(cells, edges, actors)
        first["allyRelaxedTopologyDistances"]["1"] = 999
        first["allyRelaxedPrimaryTopologyDistances"]["1"] = 999
        second = topology.measure(cells, edges, actors)
        self.assertEqual(second["allyRelaxedTopologyDistances"]["1"], 1)
        self.assertIsNone(second["allyRelaxedPrimaryTopologyDistances"]["1"])
        actors[2]["registeredSummon"] = False
        third = topology.measure(cells, edges, actors)
        self.assertNotIn("allyRelaxedPrimaryTopologyDistances", third)
        self.assertEqual(third["allyRelaxedTopologyDistances"]["1"], 1)


if __name__ == "__main__":
    unittest.main()
