"""A retained range query shares one validated Qf snapshot, then discards it."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_retained_runtime import (
    _native_retained_condition_population,
    native_retained_condition_effects,
    native_retained_condition_reader,
)
from wakfu_server.combat_range_conditions import registered_state_carriers
import test_combat_retained_cell_groups as cell_groups


class RetainedQuerySnapshotTests(unittest.TestCase):
    def fight(self):
        fight, _ = cell_groups.RetainedCellGroupTests().fixture()
        # A second valid manager exercises one query reading the complete
        # population across multiple actor candidates.
        fight.actors[8] = SimpleNamespace(
            id=8, state_ledger=SimpleNamespace(entries=())
        )
        return fight

    def test_one_query_builds_complete_population_once_and_matches_public_reads(self):
        fight = self.fight()
        expected = native_retained_condition_effects(fight, 7)
        self.assertEqual(expected, ((350552, 949, 901),))

        with patch(
            "wakfu_server.combat_retained_runtime._native_retained_condition_population",
            wraps=_native_retained_condition_population,
        ) as build:
            read = native_retained_condition_reader(fight)
            self.assertEqual(
                registered_state_carriers(fight, fight.actors[7], retained_reader=read),
                (),
            )
            self.assertEqual(
                registered_state_carriers(fight, fight.actors[8], retained_reader=read),
                (),
            )
            self.assertEqual(read(7), expected)
            self.assertEqual(read(8), ())
            self.assertEqual(build.call_count, 1)

        # The public helper remains fresh per call and semantically identical.
        self.assertEqual(native_retained_condition_effects(fight, 7), expected)
        self.assertEqual(native_retained_condition_effects(fight, 8), ())

    def test_new_query_revalidates_after_mutation_and_rejects_invalid_full_graph(self):
        fight = self.fight()
        read = native_retained_condition_reader(fight)
        expected = ((350552, 949, 901),)
        self.assertEqual(read(7), expected)

        # The current query owns an immutable local projection. A later query
        # must validate changed live ownership instead of reusing that view.
        fight.native_retained_records[901]["manager_id"] = 999
        self.assertEqual(read(7), expected)
        next_query = native_retained_condition_reader(fight)
        with self.assertRaises(ValueError):
            next_query(7)

    def test_pending_state_graph_mismatch_fails_closed_on_first_read(self):
        fight = self.fight()
        fight.native_retained_records.clear()

        with self.assertRaisesRegex(ValueError, "Incomplete native retained"):
            native_retained_condition_reader(fight)(7)


if __name__ == "__main__":
    unittest.main()
