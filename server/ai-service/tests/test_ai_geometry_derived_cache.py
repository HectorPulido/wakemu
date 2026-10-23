"""Complete immutable terrain reuse remains separate from live tactical facts."""
import unittest

from wakfu_ai.native.native_deadline import bounded
from wakfu_ai.planning import topology_distance as topology


class DerivedGeometryCacheTests(unittest.TestCase):
    def setUp(self):
        topology._immutable_adjacencies.cache_clear()

    def test_exact_xyz_direction_and_complete_terrain_are_reused_by_value(self):
        a, b, upper = (0, 0, 0), (1, 0, 0), (0, 0, 1)
        cells = [a, b, upper]
        edges = [(a, b), (b, upper)]
        forward, reverse = topology.immutable_directed_adjacencies(edges, cells=cells)
        self.assertEqual(dict(forward), {a: {b}, b: {upper}})
        self.assertEqual(dict(reverse), {b: {a}, upper: {b}})
        same = topology.immutable_directed_adjacencies(
            list(reversed(edges)), cells=list(cells)
        )
        self.assertIs(forward, same[0])
        self.assertEqual(topology._immutable_adjacencies.cache_info().hits, 1)
        changed = topology.immutable_directed_adjacencies([(upper, b)], cells=cells)
        self.assertNotEqual(dict(changed[0]), dict(forward))
        with self.assertRaisesRegex(ValueError, "outside complete walkable"):
            topology.immutable_directed_adjacencies(edges, cells=[a, b])

    def test_mutable_inputs_are_resnapshotted_and_cannot_poison_returned_maps(self):
        a, b, c = [0, 0, 0], [1, 0, 0], [2, 0, 0]
        edges, cells = [[a, b]], [a, b, c]
        before = topology.immutable_directed_adjacencies(edges, cells=cells)
        edges[0][1] = c
        after = topology.immutable_directed_adjacencies(edges, cells=cells)
        self.assertEqual(before[0][tuple(a)], {tuple(b)})
        self.assertEqual(after[0][tuple(a)], {tuple(c)})
        with self.assertRaises(TypeError):
            after[0][tuple(a)] = {tuple(b)}
        with self.assertRaises(AttributeError):
            after[0][tuple(a)].add(tuple(b))

    def test_occupancy_movement_death_and_goals_remain_fresh(self):
        a, b, c = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        _, reverse = topology.immutable_directed_adjacencies(
            [(a, b), (b, c)], cells=[a, b, c]
        )
        self.assertEqual(
            topology.distance_field_from_reverse(reverse, {c}, set())[a], 2
        )
        self.assertNotIn(a, topology.distance_field_from_reverse(reverse, {c}, {b}))
        # Vacating/dying on b opens the path without rebuilding terrain.
        self.assertEqual(
            topology.distance_field_from_reverse(reverse, {c}, set())[a], 2
        )
        self.assertEqual(
            topology.distance_field_from_reverse(reverse, {b}, set())[a], 1
        )
        self.assertEqual(
            topology.distance_field_from_reverse(reverse, {a}, set()), {a: 0}
        )
        hazards = {b}
        self.assertEqual(topology.minimum_exposure(reverse, {c}, set(), a, hazards), 1)
        hazards.clear()
        self.assertEqual(topology.minimum_exposure(reverse, {c}, set(), a, hazards), 0)

    def test_hits_and_snapshot_traversal_obey_native_deadline(self):
        a, b = (0, 0, 0), (1, 0, 0)
        topology.immutable_directed_adjacencies([(a, b)], cells=[a, b])
        now = [0]
        with bounded(1, clock=lambda: now[0]):
            now[0] = 2
            with self.assertRaises(TimeoutError):
                topology.immutable_directed_adjacencies([(a, b)], cells=[a, b])
        now[0] = 0

        class Cell(list):
            def __iter__(self):
                now[0] = 2
                return super().__iter__()

        with bounded(1, clock=lambda: now[0]):
            with self.assertRaises(TimeoutError):
                topology.immutable_directed_adjacencies(
                    [], cells=[Cell([0, 0, 0])] * 2048
                )

    def test_cache_is_bounded_and_legacy_mutable_api_remains_independent(self):
        origin = (0, 0, 0)
        for index in range(24):
            end = (index + 1, 0, 0)
            topology.immutable_directed_adjacencies(
                [(origin, end)], cells=[origin, end]
            )
        self.assertEqual(topology._immutable_adjacencies.cache_info().currsize, 16)
        a, b = (0, 0, 0), (1, 0, 0)
        forward, _ = topology.directed_adjacencies([(a, b)], cells=[a, b])
        forward[a].clear()
        cached, _ = topology.immutable_directed_adjacencies([(a, b)], cells=[a, b])
        self.assertEqual(cached[a], {b})


if __name__ == "__main__":
    unittest.main()
