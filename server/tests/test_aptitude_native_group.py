import copy
import unittest
from unittest.mock import patch
from wakfu_server import aptitudes
from wakfu_server.wire import proto_field


class AptitudeNativeGroupTests(unittest.TestCase):
    def character(self, bonus=4, points=1):
        blob = proto_field(24, (1 << 64) - 1) + proto_field(
            34, proto_field(8, bonus) + proto_field(16, points)
        )
        return {"level": 50, "builds": {0: {"aptitudes": blob.hex()}}}

    def test_native_major_range_group_reduces_both_children(self):
        self.assertEqual(
            aptitudes.bonuses(self.character()),
            {"stats": {11: 1, 20: 40}, "percentages": {}, "unsupported": []},
        )
        self.assertEqual(
            [r["effect"] for r in aptitudes.EFFECTS[4]["children"]], [136434, 136435]
        )

    def test_native_safe_groups_support_mixed_and_dynamic_characteristics(self):
        for bonus, expected in [
            (3, {3: 1, 20: 20}),
            (21, {8: 4, 7: 4}),
            (39, {101: 10, 20: 40}),
        ]:
            result = aptitudes.bonuses(self.character(bonus))
            self.assertEqual(result["stats"], expected)
            self.assertEqual(result["unsupported"], [])

    def test_unsupported_child_or_group_never_applies_partial_stats(self):
        for field, value in [
            ("criteria", True),
            ("triggers", True),
            ("target_mask", 1),
            ("runner", "eYg"),
            ("stat_id", -1),
            ("values_by_points", [[]]),
        ]:
            effects = copy.deepcopy(aptitudes.EFFECTS)
            effects[4]["children"][1][field] = value
            with patch.object(aptitudes, "EFFECTS", effects):
                result = aptitudes.bonuses(self.character())
            self.assertEqual(result["stats"], {})
            self.assertEqual(
                result["unsupported"], [{"bonus": 4, "effect": 136433, "runner": "eYg"}]
            )
        effects = copy.deepcopy(aptitudes.EFFECTS)
        effects[4]["values_by_points"][0] = [1]
        with patch.object(aptitudes, "EFFECTS", effects):
            self.assertTrue(aptitudes.bonuses(self.character())["unsupported"])
