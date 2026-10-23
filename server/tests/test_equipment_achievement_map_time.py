"""Original EQUIP achievement/map/day predicates use owned and live authority."""
import ast
import struct
from unittest import TestCase
from unittest.mock import patch

from wakfu_server import (
    equipment_conditions as conditions,
    equipment_context,
    equipment,
    world_clock,
)
from wakfu_server.combat_local_criteria import parse_local_criterion
from wakfu_server.wire import proto_field


class EquipmentAchievementMapTimeTests(TestCase):
    def context(self, **changes):
        context = dict(
            actor_kind="player",
            level=100,
            native_map_id=527,
            world_time_ms=1800000,
            completed_achievements=(),
        )
        context.update(changes)
        return context

    def check(self, expression, context):
        return conditions.evaluate(
            expression,
            item=dict(uid=1, reference=8089),
            selected=[],
            owned={},
            criterion_context=context,
        )

    def test_all_seven_original_achievement_templates_use_exact_owned_completion(self):
        rows = [
            row["EQUIP"]
            for row in conditions.catalog().values()
            if "IsAchievementComplete(" in row.get("EQUIP", "")
        ]
        self.assertEqual(len(rows), 7)
        for expression in rows:
            call = next(
                node
                for node in ast.walk(parse_local_criterion(expression))
                if isinstance(node, ast.Call)
            )
            identity = call.args[0].value
            self.assertFalse(self.check(expression, self.context()))
            self.assertTrue(
                self.check(expression, self.context(completed_achievements=(identity,)))
            )
            self.assertFalse(
                self.check(
                    expression, self.context(completed_achievements=(identity + 1,))
                )
            )
        for values in ((True,), (-1,), [1509], None):
            with self.assertRaises(ValueError):
                self.check(
                    "IsAchievementComplete(1509)",
                    self.context(completed_achievements=values),
                )

    def test_all_six_map_templates_use_native_map_definition_and_original_day_cycle(
        self,
    ):
        rows = [
            row["EQUIP"]
            for row in conditions.catalog().values()
            if "GetInstanceId(" in row.get("EQUIP", "")
        ]
        self.assertEqual(len(rows), 6)
        for expression in rows:
            if "IsDay" in expression:
                self.assertTrue(self.check(expression, self.context(native_map_id=506)))
                self.assertFalse(
                    self.check(expression, self.context(native_map_id=527))
                )
                self.assertTrue(
                    self.check(
                        expression, self.context(native_map_id=527, world_time_ms=0)
                    )
                )
            else:
                self.assertTrue(self.check(expression, self.context(native_map_id=527)))
                self.assertFalse(
                    self.check(expression, self.context(native_map_id=800))
                )
        for expression in (
            "GetInstanceId() == 0",
            "IsDay()",
            "IsAchievementComplete(1509)",
        ):
            with self.assertRaises(ValueError):
                self.check(expression, dict(actor_kind="player", level=100))

    def test_game_clock_offset_matches_actual_23354_publication_and_boundaries(self):
        with patch.dict("os.environ", {"WAKFU_CLOCK_OFFSET_SECONDS": "-300"}), patch(
            "wakfu_server.world_clock.time.time_ns", return_value=2100000 * 1000000
        ):
            self.assertEqual(world_clock.current_time_ms(), 1800000)
            self.assertEqual(
                world_clock.current_time_ms(),
                struct.unpack(
                    ">q",
                    world_clock.packet(offset_ms=world_clock.configured_offset_ms()),
                )[0],
            )
        for timestamp, expected in (
            (0, False),
            (1799999, False),
            (1800000, True),
            (5399999, True),
            (5400000, False),
            (7200000, False),
        ):
            self.assertEqual(
                self.check("IsDay()", self.context(world_time_ms=timestamp)), expected
            )

    def test_existing_light_reconciles_across_day_boundary_without_reloading_or_consuming(
        self,
    ):
        actor = dict(
            id=1,
            level=100,
            map_id=527,
            instance_id=506,
            inventory_items=[dict(uid=10, character_id=1, quantity=1, reference=8089)],
            equipment_criterion_context=self.context(
                native_map_id=506, world_time_ms=0
            ),
        )
        sheet = proto_field(10, proto_field(8, 10) + proto_field(16, 17))
        with patch("wakfu_server.world_clock.current_time_ms", return_value=0):
            self.assertEqual(
                equipment.resolve_sheet(actor, sheet)["entries"],
                [dict(uid=10, slot=17)],
            )
        with patch("wakfu_server.world_clock.current_time_ms", return_value=1800000):
            context = equipment_context.for_character(actor)
            self.assertEqual(context["native_map_id"], 527)
            self.assertEqual(context["world_time_ms"], 1800000)
            self.assertEqual(equipment.resolve_sheet(actor, sheet)["entries"], [])
            with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
                equipment.validate_sheet(actor, sheet)
        self.assertEqual(actor["inventory_items"][0]["quantity"], 1)
        self.assertEqual(actor["equipment_criterion_context"]["world_time_ms"], 0)
