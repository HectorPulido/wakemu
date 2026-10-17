"""Offline planner contracts over explicit registered native cell footprints.

These cases qualify the planner/delivery boundary only. Native definition
loading, geometry construction, glyph/trap guards and packet delivery remain
covered by the separate affected interaction milestone.
"""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_area_event_contracts import (
    deliver_area_movement,
    plan_area_movement,
)


class AreaMovementPlanTests(unittest.TestCase):
    def rows(self):
        return [
            dict(uid=31, native_cells_xy=((0, 0),)),
            dict(uid=72, native_cells_xy=((0, 0), (1, 0))),
            dict(uid=9, native_cells_xy=((1, 0),)),
        ]

    def plan(
        self,
        rows,
        *,
        origin=(0, 0, 0),
        destination=(1, 0, 0),
        radius=0,
        definition_for=None
    ):
        return plan_area_movement(
            rows,
            (lambda row: {"source_uid": row["uid"]})
            if definition_for is None
            else definition_for,
            SimpleNamespace(physical_radius=radius),
            from_cell=origin,
            to_cell=destination,
        )

    def test_registered_transitions_preserve_native_group_and_source_order(self):
        rows = self.rows()
        rows.append(dict(uid=10, native_cells_xy=((1, 0),)))
        plan = self.plan(rows)
        self.assertEqual(tuple(group.event_id for group in plan), (10001, 10008, 10002))
        self.assertEqual(
            [[row["uid"] for row, _ in group.recipients] for group in plan],
            [[9, 10], [72], [31]],
        )
        self.assertEqual(
            [
                definition["source_uid"]
                for group in plan
                for _, definition in group.recipients
            ],
            [9, 10, 72, 31],
        )

    def test_destination_radius_and_origin_point_have_distinct_authority(self):
        rows = [dict(uid=1, native_cells_xy=((1, 0),))]
        # Origin's expanded footprint touches this cell, but origin is a point.
        plan = self.plan(rows, origin=(0, 0, 3), destination=(0, 0, -2), radius=1)
        self.assertEqual([len(group.recipients) for group in plan], [1, 0, 0])
        # A negative native radius has no expansion; center containment remains.
        center = self.plan(rows, origin=(4, 4, 0), destination=(1, 0, 0), radius=-1)
        outside = self.plan(rows, origin=(4, 4, 0), destination=(0, 0, 0), radius=-1)
        self.assertEqual([len(group.recipients) for group in center], [1, 0, 0])
        self.assertEqual([len(group.recipients) for group in outside], [0, 0, 0])

    def test_plan_retains_original_rows_across_removal_and_new_registration(self):
        rows = self.rows()
        originals = tuple(rows)
        plan = self.plan(rows)
        rows.clear()
        rows.append(dict(uid=999, native_cells_xy=((1, 0),)))
        calls = []

        def deliver(row, definition, target, event_id):
            calls.append((event_id, row["uid"]))
            row["visited"] = True
            return [(event_id, row["uid"])]

        result = deliver_area_movement(plan, SimpleNamespace(), deliver)
        self.assertEqual(calls, [(10001, 9), (10008, 72), (10002, 31)])
        self.assertEqual(result, (((10001, 9),), ((10008, 72),), ((10002, 31),)))
        self.assertTrue(all(row["visited"] for row in originals))
        self.assertNotIn("visited", rows[0])

    def test_definition_validation_preserves_input_order_before_callback_delivery(self):
        visited = []

        def definition(row):
            visited.append(row["uid"])
            if row["uid"] == 72:
                raise ValueError("unqualified native definition")
            return row

        with self.assertRaisesRegex(ValueError, "unqualified native definition"):
            self.plan(self.rows(), definition_for=definition)
        self.assertEqual(visited, [31, 72])

    def test_empty_delivery_and_invalid_native_radius_do_not_invent_events(self):
        plan = self.plan([])
        self.assertEqual(
            deliver_area_movement(
                plan,
                SimpleNamespace(),
                lambda *arguments: self.fail("Empty group callback"),
            ),
            ((), (), ()),
        )
        for radius in (True, None, -129, 128):
            with self.subTest(radius=radius):
                with self.assertRaisesRegex(ValueError, "signed-byte radius"):
                    self.plan(self.rows(), radius=radius)
