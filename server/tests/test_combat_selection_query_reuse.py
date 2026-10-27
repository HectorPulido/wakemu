"""Pure selection snapshots preserve native area validation and callback fences."""
from copy import deepcopy
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from wakfu_server.combat_cell_group import select_cell_group
from wakfu_server.combat_condition_selection_scope import (
    condition_actor_selection_scope,
)
from wakfu_server.combat_effect_area_queries import specific_area_count
from wakfu_server import combat_battleground_border as border


def fixture(size=41):
    cells = tuple((x, y) for y in range(size) for x in range(size))
    return SimpleNamespace(
        native_qi_snapshot=dict(
            x=0, y=0, width=size, height=size, cell_masks=[128] * (size * size)
        ),
        actors={},
        native_effect_areas={
            900: dict(
                uid=900,
                reference=2114,
                cell=(0, 0, 0),
                owner_id=None,
                native_area_contract="faP",
                native_border_source=border.SOURCE,
                native_border_policy=border.POLICY,
                level=0,
                direction=-1,
                native_geometry_reference_source="faP.h.fbg.QI_P",
                native_cells_xy=cells,
            )
        },
    )


def query(fight, cell=(0, 0, 0), reference=2114):
    return specific_area_count(
        fight,
        source_id=7,
        center=cell,
        area_reference=reference,
        minimum=0,
        maximum=100,
    )


def matched_benchmark(cells=120, size=41):
    rows = []
    for reuse in (False, True):
        fight = fixture(size)
        selected, draws = [], []
        points = [(i % size, i // size, 0) for i in range(cells)]

        def predicate(cell):
            selected.append(cell)
            return query(fight, cell, 2114) == 1 and query(fight, cell, 2115) == 0

        started = time.monotonic()
        with patch.object(
            border,
            "verify_battleground_border",
            wraps=border.verify_battleground_border,
        ) as verify:
            result = select_cell_group(
                dict(parameters=[2, 0, 1, 0, 0, 0, 1]),
                points,
                caster_position=(0, 0, 0),
                condition=predicate,
                rng=lambda: draws.append(0.25) or 0.25,
                reuse_condition_actors=reuse,
            )
        rows.append(
            dict(
                reuse=reuse,
                seconds=time.monotonic() - started,
                verifiedBorders=verify.call_count,
                selectedCells=list(result.cells),
                predicateCells=selected,
                rngDraws=draws,
            )
        )
    return rows


class SelectionAreaReuseTests(unittest.TestCase):
    def test_matched_cells_predicate_order_rng_and_border_validation_counts(self):
        baseline, scoped = matched_benchmark(cells=12, size=9)
        for key in ("selectedCells", "predicateCells", "rngDraws"):
            self.assertEqual(baseline[key], scoped[key])
        self.assertEqual(baseline["verifiedBorders"], 24)
        self.assertEqual(scoped["verifiedBorders"], 1)

    def test_arbitrary_nested_callback_invalidates_outer_on_success_or_failure(self):
        for failed in (False, True):
            fight = fixture(3)
            with condition_actor_selection_scope():
                self.assertEqual(query(fight), 1)
                try:
                    with condition_actor_selection_scope(enabled=False):
                        fight.native_effect_areas[900][
                            "native_border_source"
                        ] = "tampered"
                        with self.assertRaisesRegex(ValueError, "provenance"):
                            query(fight)
                        if failed:
                            raise RuntimeError("Callback failed after mutating source")
                except RuntimeError:
                    pass
                with self.assertRaisesRegex(ValueError, "provenance"):
                    query(fight)

    def test_failure_is_not_cached_and_next_selection_reads_changed_source(self):
        fight = fixture(3)
        with condition_actor_selection_scope():
            fight.native_effect_areas[900]["native_cells_xy"] = []
            with self.assertRaisesRegex(ValueError, "shape"):
                query(fight)
            fight.native_effect_areas[900]["native_cells_xy"] = fixture(
                3
            ).native_effect_areas[900]["native_cells_xy"]
            self.assertEqual(query(fight), 1)
        fight.native_effect_areas[900]["native_cells_xy"] = []
        with self.assertRaisesRegex(ValueError, "shape"):
            query(fight)
        with condition_actor_selection_scope(), self.assertRaisesRegex(
            ValueError, "shape"
        ):
            query(fight)

    def test_fight_identity_and_later_population_are_fresh(self):
        one, two = fixture(3), fixture(3)
        two.native_effect_areas[900]["reference"] = 2115
        with condition_actor_selection_scope():
            self.assertEqual(query(one), 1)
            self.assertEqual(query(two), 0)
        del one.native_effect_areas[900]
        self.assertEqual(query(one), 0)


if __name__ == "__main__":
    unittest.main()
