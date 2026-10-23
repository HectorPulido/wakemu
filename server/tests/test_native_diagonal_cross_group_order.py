"""Compare cell enumeration with original anx insertion-order exports."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat_group_cells import ordered_offsets, group_cells


class NativeDiagonalCrossGroupOrderTests(unittest.TestCase):
    def test_native_order_for_long_asymmetric_and_nonpositive_arms(self):
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/native_diagonal_cross_order.json"
            ).read_text()
        )
        for case in fixture["cases"]:
            with self.subTest(description=case["description"]):
                effect = dict(area_class="anx", area_native=case["description"])
                expected = tuple(map(tuple, case["points"]))
                self.assertEqual(ordered_offsets(effect), expected)
                origin = (10, 20, 0)
                # Preserve the original sequence while QI excludes absent heights.
                admitted = expected[::2]
                fight = SimpleNamespace(
                    walkable={(10 + x, 20 + y, 7) for x, y in admitted}
                )
                self.assertEqual(
                    group_cells(fight, effect, origin),
                    tuple((10 + x, 20 + y, 7) for x, y in admitted),
                )
                self.assertEqual(
                    ordered_offsets(
                        effect, origin=origin, reference=origin, direction=5
                    ),
                    expected,
                )
