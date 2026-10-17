"""Current area routing preserves native geometry and frozen callback order."""
import unittest
from copy import deepcopy

from wakfu_server.combat_area_event_contracts import (
    AREA_EVENT_PRODUCERS,
    MOVEMENT_AREA_EVENT_ORDER,
    plan_area_movement,
)


class AreaMovementContractTests(unittest.TestCase):
    def fixture(self, *, radius=0):
        from test_combat_effect_area_events import AreaEventTests

        runtime, template, calls = AreaEventTests().fixture(
            entry=(10001, 10008), exit=(10002,)
        )
        runtime.fight.actors[8].physical_radius = radius
        runtime.fight.native_effect_areas.clear()
        for identity, footprint in (
            (31, ((0, 0),)),
            (72, ((0, 0), (1, 0))),
            (9, ((1, 0),)),
        ):
            row = deepcopy(template)
            row.update(uid=identity, native_cells_xy=footprint)
            runtime.fight.native_effect_areas[identity] = row
        return runtime, calls

    def observe(self, runtime, calls, origin, destination):
        runtime.fight.actors[8].position = destination
        result = runtime.movement(8, from_cell=origin, to_cell=destination)
        return (
            result,
            deepcopy(calls),
            deepcopy(runtime.fight.native_effect_areas),
            deepcopy(runtime.fight.native_retained_records),
        )

    def test_real_glyph_callbacks_preserve_point_origin_and_radius_destination(self):
        # Explicit small footprints supply an independent transition oracle;
        # origin uses point containment and destination uses physical radius.
        for radius in (-1, 0, 1, 2):
            for origin in ((-3, 0, 0), (0, 0, 0), (1, 0, 9)):
                for destination in ((-3, 0, 0), (0, 0, 0), (1, 0, 9)):
                    with self.subTest(radius=radius, origin=origin, to=destination):
                        runtime, calls = self.fixture(radius=radius)
                        expected = {10001: [], 10008: [], 10002: []}
                        rows = tuple(runtime.fight.native_effect_areas.values())
                        for row in rows:
                            cells = row["native_cells_xy"]
                            before = origin[:2] in cells
                            after = destination[:2] in cells or any(
                                radius >= 0
                                and max(
                                    abs(x - destination[0]), abs(y - destination[1])
                                )
                                <= radius
                                for x, y in cells
                            )
                            event = (
                                (10008 if before else 10001)
                                if after
                                else (10002 if before else None)
                            )
                            if event is not None:
                                expected[event].append(row["uid"])
                        delivered = []
                        actual_delivery = runtime._deliver_event

                        def record(row, definition, target, event_id):
                            delivered.append((event_id, row["uid"]))
                            return actual_delivery(row, definition, target, event_id)

                        runtime._deliver_event = record
                        result, observed_calls, areas, retained = self.observe(
                            runtime, calls, origin, destination
                        )
                        self.assertEqual(
                            delivered,
                            [
                                (event, uid)
                                for event in (10001, 10008, 10002)
                                for uid in expected[event]
                            ],
                        )
                        self.assertEqual(
                            tuple(map(len, result)),
                            tuple(
                                len(expected[event]) for event in (10001, 10008, 10002)
                            ),
                        )
                        self.assertEqual(set(areas), {31, 72, 9})
                        self.assertEqual(retained, {})
                        self.assertEqual(
                            len(observed_calls),
                            len(expected[10001]) + len(expected[10008]),
                        )

    def test_frozen_groups_preserve_actual_objects_and_entry_inside_exit_order(self):
        runtime, calls = self.fixture()
        definitions = []

        def definition_for(row):
            definitions.append(row["uid"])
            return runtime._definition(row)

        rows = tuple(runtime.fight.native_effect_areas.values())
        plan = plan_area_movement(
            rows,
            definition_for,
            runtime.fight.actors[8],
            from_cell=(0, 0, 0),
            to_cell=(1, 0, 0),
        )
        self.assertEqual(definitions, [31, 72, 9])
        self.assertEqual(tuple(group.event_id for group in plan), (10001, 10008, 10002))
        self.assertIs(plan[0].recipients[0][0], rows[2])
        self.assertIs(plan[1].recipients[0][0], rows[1])
        self.assertIs(plan[2].recipients[0][0], rows[0])
        runtime.fight.native_effect_areas.clear()
        self.assertEqual(plan[2].recipients[0][0]["uid"], 31)

    def test_callbacks_freeze_removed_rows_and_exclude_new_rows(self):
        runtime, calls = self.fixture()
        target = runtime.fight.actors[8]
        target.position = (1, 0, 0)
        original_exit_row = runtime.fight.native_effect_areas[31]

        def activate(row, definition, actor, *, trigger=None):
            calls.append(("activate", row["uid"]))
            runtime.fight.native_effect_areas.pop(31, None)
            extra = deepcopy(row)
            extra["uid"] = 999
            runtime.fight.native_effect_areas[999] = extra
            return True

        def exit_row(row, actor):
            self.assertIs(row, original_exit_row)
            calls.append(("exit", row["uid"]))
            return True

        runtime._activate = activate
        runtime._exit = exit_row
        outcomes = runtime.movement(8, from_cell=(0, 0, 0), to_cell=(1, 0, 0))
        self.assertEqual(outcomes, ((True,), (True,), (True,)))
        self.assertEqual(calls, [("activate", 9), ("activate", 72), ("exit", 31)])

    def test_producer_registry_does_not_turn_subscription_into_producer(self):
        self.assertEqual(MOVEMENT_AREA_EVENT_ORDER, (10001, 10008, 10002))
        self.assertEqual(AREA_EVENT_PRODUCERS["running_source"].event_ids, ())
        with self.assertRaises(TypeError):
            AREA_EVENT_PRODUCERS["invented"] = object()

    def test_missing_target_rejects_without_publication(self):
        runtime, calls = self.fixture()
        before = deepcopy(vars(runtime.fight))
        with self.assertRaisesRegex(ValueError, "Missing native area-event target"):
            runtime.movement(999, from_cell=(0, 0, 0), to_cell=(1, 0, 0))
        self.assertEqual(calls, [])
        self.assertEqual(vars(runtime.fight), before)


if __name__ == "__main__":
    unittest.main()
