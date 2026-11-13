"""Native LOS cell selector must use the exact exported eYk definition."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from wakfu_server.combat_cell_group import native_cell_criterion_presence


class RiiLosCellGroupTests(TestCase):
    def test_exact_native_selector_and_mismatches(self):
        effect = {
            "effect_class": 349,
            "area_class": "anu",
            "parameters": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        }
        invocation = SimpleNamespace(reference=367418)
        with patch(
            "wakfu_server.combat_cell_group.native_cell_group_metadata", return_value={}
        ):
            self.assertTrue(native_cell_criterion_presence(effect, invocation))
            for changed in (
                dict(effect, effect_class=315),
                dict(effect, area_class="anA"),
                dict(effect, parameters=[2.0] + effect["parameters"][1:]),
            ):
                with self.assertRaises(ValueError):
                    native_cell_criterion_presence(changed, invocation)
            with self.assertRaises(ValueError):
                native_cell_criterion_presence(
                    effect, SimpleNamespace(reference=367419)
                )
