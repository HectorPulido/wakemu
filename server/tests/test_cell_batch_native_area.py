"""Actual owned area storage remains eligible for native read-only cell batches."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from test_combat_condition_cell_batch import CellBatchOwnedTests
from wakfu_server import combat_condition_cell_batch as batch
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_retained_collections import OwnedMap
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_condition_selection_scope import (
    condition_actor_selection_scope,
)


class NativeAreaCellBatchTests(unittest.TestCase):
    def test_owned_area_binding_shared_reads_mutation_and_custom_fallback(self):
        fixture = CellBatchOwnedTests()
        fixture.setUp()
        fight = fixture.fight
        self.assertIs(type(fight.native_effect_areas), OwnedMap)
        # Empty native Fight (the previous unconditional fallback).
        self.assertIsNotNone(fixture.frame())
        # Reuse the maintained native hour-area snapshot contract and point
        # geometry, away from queried cells (no synthetic Qq target authority).
        from test_combat_ready_area_conditions import ReadyAreaConditionTests

        area_fixture = ReadyAreaConditionTests()
        area_fixture.setUp()
        row = OwnedAreaRow(area_fixture.fight.native_effect_areas[901])
        row.update(
            uid=9001,
            cell=(99, 99, 0),
            native_running_effect_manager=True,
            state_ledger=StateLedger(9001),
        )
        fight.native_effect_areas[9001] = row
        self.assertIs(fight.native_effect_areas[9001], row)
        frame = fixture.frame()
        values, shared = [], []
        cells = ((0, 0, 0), (2, 2, 0), (3, 3, 0))
        baseline = [
            fixture.dispatcher.condition_context(
                replace(fixture.original, cell=cell)
            ).enemy_range_query(0, 99, "target", False, False)
            for cell in cells
        ]
        with frame, condition_actor_selection_scope():
            for cell in cells:
                context = frame.condition(replace(fixture.original, cell=cell))
                values.append(context.enemy_range_query(0, 99, "target", False, False))
                shared.append(frame.range_population)
            self.assertTrue(all(value is shared[0] for value in shared))
            self.assertIsNotNone(shared[0])
            with condition_actor_selection_scope(enabled=False):
                fight.actors[-7].native_fight_properties = frozenset({42})
            fresh = frame.condition(fixture.original)
            self.assertEqual(fresh.enemy_range_query(0, 99, "caster", False, False), 0)
            self.assertIsNot(frame.range_population, shared[0])
        self.assertEqual(values, baseline)
        self.assertIsNone(frame.range_population)
        # Exact owned outer storage is insufficient with an opaque value/read.
        row["opaque"] = object()
        self.assertFalse(batch._native_area_population_inert(fight))
        del row["opaque"]
        # Exact native rows are slotted; per-instance getters cannot be set.
        with self.assertRaises(AttributeError):
            row.get = lambda *args: None

        class CustomRow(OwnedAreaRow):
            def get(self, *args):
                raise AssertionError("opaque row reader must not execute")

        # Raw insertion avoids invoking membership setters on this intentionally
        # malformed custom row; admission must reject it before any reads.
        dict.__setitem__(fight.native_effect_areas, 9001, CustomRow(row))
        try:
            self.assertFalse(batch._native_area_population_inert(fight))
        finally:
            dict.__setitem__(fight.native_effect_areas, 9001, row)
        with patch.object(
            fight.native_effect_areas,
            "values",
            side_effect=AssertionError("opaque reader"),
        ):
            self.assertFalse(batch._native_area_population_inert(fight))

        class CustomMap(dict):
            def items(self):
                raise AssertionError("custom map must not be read")

        owned = fight.native_effect_areas
        try:
            fight.native_effect_areas = CustomMap()
            self.assertFalse(batch._native_area_population_inert(fight))
            other = CellBatchOwnedTests()
            other.setUp()
            fight.native_effect_areas = other.fight.native_effect_areas
            self.assertFalse(batch._native_area_population_inert(fight))
        finally:
            fight.native_effect_areas = owned
        self.assertTrue(batch._native_area_population_inert(fight))
