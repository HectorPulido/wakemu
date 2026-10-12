"""Passive fixtures use native directed reachability and preserve participants."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_passive_witness import (
    directed_witness_candidates,
    passive_fixture_context,
    passive_witness_destination,
)
from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.combat_arena_selection import compact_encounter


class PassiveWitnessGeometryTests(unittest.TestCase):
    def test_valid_supplied_constructor_fixture_needs_no_extra_catalog_read(self):
        context = object()

        def unavailable_geometry():
            self.fail("A successful actual fixture already validated its geometry")

        observed = passive_fixture_context(
            [(-7, -7, -1)],
            (-8, -7, -1),
            lambda cell: context,
            unavailable_geometry,
        )
        self.assertIs(observed, context)

    def test_constructor_failure_outside_geometry_is_not_retried_or_masked(self):
        original = ValueError("Exact native passive constructor proof is missing")

        def fail_constructor(cell):
            raise original

        def unavailable_geometry():
            self.fail("A non-geometry constructor failure must remain unchanged")

        with self.assertRaises(ValueError) as observed:
            passive_fixture_context(
                [(-7, -7, -1)],
                (-8, -7, -1),
                fail_constructor,
                unavailable_geometry,
            )
        self.assertIs(observed.exception, original)

    def test_actual_compact_failure_recovers_through_native_geometry(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "test-fixtures/combat"
            / "map1134-passive-witness.json"
        )
        document = json.loads(path.read_text())
        geometry = prepare_geometry(document["geometry"])
        source = tuple(document["source"])
        attempts = []

        def construct(cell):
            attempts.append(cell)
            selected = compact_encounter(
                geometry,
                cell,
                [source],
                minimum_cells=81,
                minimum_dimensions=(9, 9),
                spread_opponents=False,
            )
            if any(a != b for a, b in selected["participant_positions"]):
                raise ValueError("Compact arena cannot preserve participant positions")
            return selected

        context = passive_fixture_context(
            document["geometry"]["cells"],
            source,
            construct,
            lambda: geometry,
        )
        self.assertEqual(
            attempts,
            [
                tuple(document["original_first_cell"]),
                tuple(document["expected_target"]),
            ],
        )
        self.assertTrue(all(a == b for a, b in context["participant_positions"]))

    def test_actual_map1134_skips_disconnected_first_cell_and_preserves_positions(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "test-fixtures/combat"
            / "map1134-passive-witness.json"
        )
        document = json.loads(path.read_text())
        geometry = prepare_geometry(document["geometry"])
        source = tuple(document["source"])
        old_first = tuple(document["original_first_cell"])
        self.assertNotIn(old_first, set(directed_witness_candidates(geometry, source)))
        target = passive_witness_destination(geometry, source, geometry.cells)
        self.assertEqual(target, tuple(document["expected_target"]))
        selected = compact_encounter(
            geometry,
            target,
            [source],
            minimum_cells=81,
            minimum_dimensions=(9, 9),
            spread_opponents=False,
        )
        self.assertIn(source, selected["cells"])
        self.assertIn(target, selected["cells"])
        self.assertTrue(all(a == b for a, b in selected["participant_positions"]))

    def test_directed_breadth_first_order_excludes_incoming_only_cell_and_source(self):
        source, left, right, farther, incoming = (
            (0, 0, 0),
            (-1, 0, 0),
            (1, 0, 0),
            (2, 0, 0),
            (0, 1, 0),
        )
        geometry = prepare_geometry(
            dict(
                map_id=1,
                cells=[source, left, right, farther, incoming],
                edges=[
                    (source, right),
                    (right, farther),
                    (source, left),
                    (left, source),
                    (incoming, source),
                ],
            )
        )
        self.assertEqual(
            list(directed_witness_candidates(geometry, source)), [left, right, farther]
        )

    def test_one_way_reachability_cannot_relocate_the_monster_to_make_fixture_pass(
        self,
    ):
        source, target = (0, 0, 0), (1, 0, 0)
        geometry = prepare_geometry(
            dict(map_id=1, cells=[source, target], edges=[(source, target)])
        )
        with self.assertRaisesRegex(ValueError, "participant-preserving"):
            passive_witness_destination(geometry, source, geometry.cells)

    def test_disconnected_missing_source_or_foreign_cells_fail_closed(self):
        source, other = (0, 0, 0), (3, 0, 0)
        geometry = prepare_geometry(dict(map_id=1, cells=[source, other], edges=[]))
        with self.assertRaisesRegex(ValueError, "participant-preserving"):
            passive_witness_destination(geometry, source, geometry.cells)
        for cells in ([other], [source, (99, 99, 0)]):
            with self.subTest(cells=cells), self.assertRaises(ValueError):
                passive_witness_destination(geometry, source, cells)


if __name__ == "__main__":
    unittest.main()
