"""Memoization must preserve directed native topology and caller isolation."""
import unittest
from unittest.mock import patch

from wakfu_server.combat import combat_geometry as geometry
from wakfu_server.combat import combat_arena_selection as arena


def topology(cells, edges):
    return {"map_id": 777, "cells": list(cells), "edges": list(edges)}


def bidirectional(edges):
    return [(a, b) for a, b in edges for a, b in ((a, b), (b, a))]


class EncounterComponentCacheTests(unittest.TestCase):
    def setUp(self):
        with geometry._encounter_components_lock:
            geometry._encounter_components.clear()

    def test_same_snapshot_and_origin_traverse_only_once(self):
        a, b = (0, 0, 0), (1, 0, 2)
        prepared = geometry.prepare_geometry(topology([a, b], bidirectional([(a, b)])))
        with patch.object(geometry, "reachable", wraps=geometry.reachable) as walk:
            for _ in range(245):
                self.assertEqual(
                    geometry.encounter_component(prepared, a), ({a, b}, set())
                )
            self.assertEqual(walk.call_count, 4)

    def test_same_map_id_distinct_snapshot_and_origins_are_isolated(self):
        a, b, c = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        first = geometry.prepare_geometry(topology([a, b, c], bidirectional([(a, b)])))
        second = geometry.prepare_geometry(topology([a, b, c], bidirectional([(b, c)])))
        self.assertEqual(geometry.encounter_component(first, a)[0], {a, b})
        self.assertEqual(geometry.encounter_component(second, a)[0], {a})
        self.assertEqual(geometry.encounter_component(first, c)[0], {c})

    def test_directed_one_way_branch_is_excluded(self):
        a, b, c = (0, 0, 0), (1, 0, 3), (2, 0, 3)
        prepared = geometry.prepare_geometry(
            topology([a, b, c], bidirectional([(a, b)]) + [(b, c)])
        )
        self.assertEqual(geometry.encounter_component(prepared, a)[0], {a, b})
        self.assertEqual(geometry.encounter_component(prepared, c)[0], {c})

    def test_ambiguous_column_removal_rechecks_connectivity(self):
        a, low, high, far = (0, 0, 0), (1, 0, 0), (1, 0, 5), (2, 0, 0)
        prepared = geometry.prepare_geometry(
            topology(
                [a, low, high, far], bidirectional([(a, low), (a, high), (low, far)])
            )
        )
        for _ in range(2):
            self.assertEqual(geometry.encounter_component(prepared, a), ({a}, {(1, 0)}))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            geometry.encounter_component(prepared, low)

    def test_mutable_callers_are_resnapshotted_and_not_cached(self):
        a, b = (0, 0, 0), (1, 0, 0)
        data = topology([a, b], bidirectional([(a, b)]))
        self.assertEqual(geometry.encounter_component(data, a)[0], {a, b})
        data["edges"].clear()
        self.assertEqual(geometry.encounter_component(data, a)[0], {a})
        self.assertFalse(geometry._encounter_components)

    def test_results_cannot_mutate_cached_sets(self):
        a = (0, 0, 0)
        prepared = geometry.prepare_geometry(topology([a], []))
        cells, ambiguous = geometry.encounter_component(prepared, a)
        cells.clear()
        ambiguous.add((999, 999))
        self.assertEqual(geometry.encounter_component(prepared, a), ({a}, set()))

    def test_cache_is_bounded_lru_and_retains_geometry_identity(self):
        cells = [(n, 0, 0) for n in range(34)]
        prepared = geometry.prepare_geometry(topology(cells, []))
        for origin in cells[:32]:
            geometry.encounter_component(prepared, origin)
        geometry.encounter_component(prepared, cells[0])
        geometry.encounter_component(prepared, cells[32])
        self.assertEqual(len(geometry._encounter_components), 32)
        self.assertIn((id(prepared), cells[0]), geometry._encounter_components)
        self.assertNotIn((id(prepared), cells[1]), geometry._encounter_components)
        self.assertTrue(
            all(
                value[0] is prepared
                for value in geometry._encounter_components.values()
            )
        )

    def test_selected_encounters_match_uncached_algorithm_across_policies(self):
        cells = {(x, y, (x // 3)) for x in range(9) for y in range(8)}
        edges = [
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        ]
        prepared = geometry.prepare_geometry(topology(cells, edges))
        origin, opponents = (1, 1, 0), [(7, 6, 2), (8, 5, 2)]

        def uncached(data, source, **unused):
            selected, ambiguous = geometry._compute_encounter_component(
                geometry.prepare_geometry(data), source
            )
            return set(selected), set(ambiguous)

        for budget in (None, 25, 49):
            for spread in (False, True):
                options = {"cell_budget": budget, "spread_opponents": spread}
                with patch.object(
                    arena, "encounter_component", side_effect=uncached
                ), patch.object(arena, "_COMPACT_ENCOUNTER_LIMIT", 0):
                    expected = arena.compact_encounter(
                        prepared, origin, opponents, **options
                    )
                self.assertEqual(
                    arena.compact_encounter(prepared, origin, opponents, **options),
                    expected,
                )
                self.assertEqual(
                    arena.compact_encounter(prepared, origin, opponents, **options),
                    expected,
                )


class CompleteEncounterCacheTests(unittest.TestCase):
    def setUp(self):
        arena._compact_encounters.clear()
        cells = {(x, y, 0) for x in range(9) for y in range(8)}
        edges = [
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        ]
        self.data = topology(cells, edges)
        self.prepared = geometry.prepare_geometry(self.data)
        self.origin = (1, 1, 0)
        self.members = [(7, 6, 0), (8, 5, 0)]

    def call(self, **options):
        return arena.compact_encounter(
            self.prepared, self.origin, self.members, **options
        )

    def test_245_identical_calls_compute_complete_selection_once(self):
        with patch.object(
            arena, "_select_compact_encounter", wraps=arena._select_compact_encounter
        ) as select:
            expected = self.call()
            for _ in range(244):
                self.assertEqual(self.call(), expected)
            self.assertEqual(select.call_count, 1)

    def test_every_selection_option_and_ordered_member_is_in_key(self):
        variants = [
            {},
            {"cell_budget": 2500},
            {"cell_budget": 49},
            {"minimum_cells": 26},
            {"minimum_dimensions": (6, 5)},
            {"minimum_dimensions": (5, 6)},
            {"spread_opponents": True},
        ]
        with patch.object(
            arena, "_select_compact_encounter", wraps=arena._select_compact_encounter
        ) as select:
            for options in variants:
                first = self.call(**options)
                self.assertEqual(self.call(**options), first)
            self.members.reverse()
            self.call()
            self.origin = (2, 1, 0)
            self.call()
            self.prepared = geometry.prepare_geometry(self.data)
            self.call()
            self.assertEqual(select.call_count, len(variants) + 3)
        self.assertEqual(len(arena._compact_encounters), len(variants) + 3)

    def test_all_mutable_output_layers_are_independent(self):
        expected = self.call()
        changed = self.call()
        changed["cells"].clear()
        changed["edges"].clear()
        changed["placement"][0].clear()
        changed["placement"][1].clear()
        changed["placement"][9] = []
        changed["participant_positions"].clear()
        changed["blocked_ambiguous"].add((999, 999))
        changed["map_id"] = -1
        self.assertEqual(self.call(), expected)

    def test_validation_is_not_bypassed_by_populated_cache(self):
        self.call()
        for invalid in (
            {"minimum_cells": True},
            {"spread_opponents": 1},
            {"minimum_dimensions": (True, 5)},
            {"cell_budget": True},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.call(**invalid)
        with self.assertRaises(ValueError):
            arena.compact_encounter(self.prepared, self.origin, [])

    def test_mutable_topology_change_bypasses_full_cache(self):
        first = arena.compact_encounter(self.data, self.origin, self.members)
        self.data["edges"] = []
        with self.assertRaises(ValueError):
            arena.compact_encounter(self.data, self.origin, self.members)
        self.assertTrue(first["edges"])
        self.assertFalse(arena._compact_encounters)

    def test_directed_topology_cached_result_matches_fresh_selection(self):
        # One-way boundary excludes the right component from the player's SCC.
        self.data["edges"] = [
            (a, b) for a, b in self.data["edges"] if not (a[0] == 5 and b[0] == 4)
        ]
        self.prepared = geometry.prepare_geometry(self.data)
        actual = self.call(cell_budget=40)
        fresh = arena.compact_encounter(
            self.data, self.origin, self.members, cell_budget=40
        )
        self.assertEqual(actual, fresh)
        self.assertTrue(all(cell[0] <= 4 for cell in actual["cells"]))
        self.assertEqual(self.call(cell_budget=40), fresh)

    def test_lru_bound_retains_strong_geometry_reference(self):
        for n in range(33):
            self.call(minimum_cells=25 + n)
        self.assertEqual(len(arena._compact_encounters), 32)
        self.assertTrue(
            all(
                value[0] is self.prepared
                for value in arena._compact_encounters.values()
            )
        )
        self.assertNotIn(25, [key[5] for key in arena._compact_encounters])


if __name__ == "__main__":
    unittest.main()
