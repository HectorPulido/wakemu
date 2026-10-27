"""Static topology reuse retains exact values and never caches dynamic actors."""
from concurrent.futures import ThreadPoolExecutor
import gc
from types import SimpleNamespace
import unittest
import weakref
from unittest.mock import patch

from wakfu_ai.bridge.jondo_geometry import (
    GeometryProjectionCache,
    geometry_projection,
    body_extra_cells,
)
from wakfu_ai.bridge.jondo_snapshot import _reachable


class GeometryProjectionTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        self.walkable = {self.c, self.a, self.b}
        self.edges = ((self.b, self.c), (self.a, self.b))
        self.cache = GeometryProjectionCache()

    def project(self, *, revision="catalog-a"):
        return self.cache.get(self.walkable, self.edges, catalog_revision=revision)

    def test_same_exact_topology_reuses_dense_ordered_directed_projection(self):
        projection = self.project()
        self.assertIs(self.project(), projection)
        self.assertEqual(projection.cells, (self.a, self.b, self.c))
        self.assertEqual(dict(projection.indices), {self.a: 0, self.b: 1, self.c: 2})
        self.assertEqual(projection.encoded_edges, ((1, 2), (0, 1)))
        self.assertEqual(
            dict(projection.adjacency), {self.b: (self.c,), self.a: (self.b,)}
        )
        for value in (projection.indices, projection.adjacency):
            with self.assertRaises(TypeError):
                value[self.a] = ()

    def test_in_place_walkable_and_edge_mutation_never_reuses_stale_projection(self):
        original = self.project()
        self.walkable.add((3, 0, 0))
        extended = self.project()
        self.assertIsNot(extended, original)
        self.assertEqual(len(extended.cells), 4)
        self.edges += ((self.c, (3, 0, 0)),)
        changed_edge = self.project()
        self.assertIsNot(changed_edge, extended)
        self.assertEqual(changed_edge.encoded_edges[-1], (2, 3))
        self.assertEqual(original.cells, (self.a, self.b, self.c))
        self.assertEqual(original.encoded_edges, ((1, 2), (0, 1)))

    def test_catalog_scope_edge_direction_and_edge_order_are_part_of_the_key(self):
        original = self.project()
        self.assertIsNot(self.project(revision="catalog-b"), original)
        self.edges = tuple(reversed(self.edges))
        self.assertIsNot(self.project(), original)
        self.edges = ((self.b, self.a), (self.c, self.b))
        reversed_directions = self.project()
        self.assertEqual(reversed_directions.encoded_edges, ((1, 0), (2, 1)))

    def test_equal_new_objects_are_validated_before_reuse_and_numeric_type_aliases_rejected(
        self,
    ):
        original = self.project()
        copied_cells = {tuple(list(cell)) for cell in self.walkable}
        copied_edges = tuple(
            tuple(tuple(list(cell)) for cell in edge) for edge in self.edges
        )
        self.assertIs(
            self.cache.get(copied_cells, copied_edges, catalog_revision="catalog-a"),
            original,
        )
        for zero in (False, 0.0):
            invalid_cells = {(zero, 0, 0), self.b, self.c}
            with self.assertRaises(ValueError):
                self.cache.get(invalid_cells, self.edges, catalog_revision="catalog-a")
            invalid_edges = ((self.b, self.c), ((zero, 0, 0), self.b))
            with self.assertRaises(ValueError):
                self.cache.get(
                    self.walkable, invalid_edges, catalog_revision="catalog-a"
                )

    def test_dynamic_portals_and_actor_occupancy_do_not_modify_or_enter_the_static_cache(
        self,
    ):
        projection = self.project()
        actor = SimpleNamespace(id=-7, position=self.a, hp=100, mp=2)
        obstacle = SimpleNamespace(id=7, position=self.b, hp=100)
        fight = SimpleNamespace(
            walkable=self.walkable,
            edges=self.edges,
            actors={actor.id: actor, obstacle.id: obstacle},
        )
        reached, _ = _reachable(fight, actor, geometry=projection)
        self.assertEqual(reached, {self.a: 0})
        reached, dynamic = _reachable(
            fight, actor, [(self.a, self.c)], geometry=projection
        )
        self.assertEqual(reached[self.c], 1)
        self.assertEqual(dynamic[self.a], [self.b, self.c])
        self.assertEqual(projection.adjacency[self.a], (self.b,))
        obstacle.hp = 0
        reached, static = _reachable(fight, actor, geometry=projection)
        self.assertEqual(reached, {self.a: 0, self.b: 1, self.c: 2})
        self.assertIs(static, projection.adjacency)
        self.assertIs(self.project(), projection)

    def test_fresh_equal_graph_refreshes_strict_tuple_validation_proof(self):
        original = self.project()
        cells = {tuple(list(cell)) for cell in self.walkable}
        edges = tuple(tuple(tuple(list(cell)) for cell in edge) for edge in self.edges)
        from wakfu_ai.bridge import jondo_geometry

        with patch.object(
            jondo_geometry, "_integer_cell", wraps=jondo_geometry._integer_cell
        ) as checked:
            self.assertIs(
                self.cache.get(cells, edges, catalog_revision="catalog-a"), original
            )
            self.assertGreater(checked.call_count, 0)
            checked.reset_mock()
            self.assertIs(
                self.cache.get(cells, edges, catalog_revision="catalog-a"), original
            )
            self.assertEqual(checked.call_count, 0)
        with self.assertRaises(ValueError):
            self.cache.get(
                {(False, 0, 0), self.b, self.c}, edges, catalog_revision="catalog-a"
            )

    def test_xy_body_lookup_preserves_all_floors_dense_order_and_geometry_invalidation(
        self,
    ):
        from wakfu_server.combat_obstacle_condition import footprint

        walkable = {(x, y, z) for x in range(4) for y in range(4) for z in (0, 1)}
        cache = GeometryProjectionCache()
        projection = cache.get(walkable, (), catalog_revision="body-a")
        for position, radius in (((1, 1, 0), 1), ((1, 1, 1), 0), ((0, 0, 0), 1)):
            body = frozenset(footprint(position, radius))
            legacy = [
                index
                for cell, index in projection.indices.items()
                if cell[:2] in body and cell != position
            ]
            actual = body_extra_cells(projection, position, body)
            self.assertEqual(actual, legacy)
            self.assertEqual(actual, sorted(actual))
        body = frozenset(footprint((1, 1, 0), 1))
        old = body_extra_cells(projection, (1, 1, 0), body)
        self.assertEqual(len(old), 17)  # 3x3, BOTH floors, except exact sourceXYZ.
        self.assertIn(projection.indices[1, 1, 1], old)
        with self.assertRaises(TypeError):
            projection.xy_indices[1, 1] = ()
        walkable.add((1, 1, 2))
        changed = cache.get(walkable, (), catalog_revision="body-a")
        self.assertIsNot(changed, projection)
        self.assertEqual(len(body_extra_cells(changed, (1, 1, 0), body)), 18)
        self.assertEqual(body_extra_cells(projection, (1, 1, 0), body), old)
        self.assertIsNot(cache.get(walkable, (), catalog_revision="body-b"), changed)

    def test_entry_and_topology_unit_bounds_evict_and_do_not_retain_oversized_entries(
        self,
    ):
        cache = GeometryProjectionCache(max_entries=2, max_units=20)
        first = cache.get(self.walkable, self.edges, catalog_revision="a")
        cache.get(self.walkable, self.edges, catalog_revision="b")
        cache.get(self.walkable, self.edges, catalog_revision="c")
        self.assertEqual(cache.size, dict(entries=2, units=14))
        self.assertIsNot(
            cache.get(self.walkable, self.edges, catalog_revision="a"), first
        )
        large = GeometryProjectionCache(max_entries=2, max_units=2)
        left = large.get(self.walkable, self.edges, catalog_revision="a")
        right = large.get(self.walkable, self.edges, catalog_revision="a")
        self.assertIsNot(left, right)
        self.assertEqual(large.size, dict(entries=0, units=0))

    def test_concurrent_owners_do_not_duplicate_cache_accounting_or_retain_fight_objects(
        self,
    ):
        with ThreadPoolExecutor(max_workers=4) as workers:
            values = list(workers.map(lambda _: self.project(), range(16)))
        self.assertTrue(all(value is values[0] for value in values))
        self.assertEqual(self.cache.size, dict(entries=1, units=7))

        class Fight:
            pass

        fight = Fight()
        fight.walkable, fight.edges = self.walkable, self.edges
        fight.actors = {"private-state": object()}
        reference = weakref.ref(fight)
        geometry_projection(fight, catalog_revision="weak-reference-test")
        del fight
        gc.collect()
        self.assertIsNone(reference())


if __name__ == "__main__":
    unittest.main()
