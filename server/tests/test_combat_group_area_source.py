"""Directional group PV routing; native constructor integration is separate."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_group_cells import group_cells
from wakfu_server.combat_effect_area_targets import NativeAreaTarget


class GroupAreaSourceTests(unittest.TestCase):
    def fixture(self):
        return SimpleNamespace(
            actors={},
            walkable={(0, 0, 5), (0, -1, 8), (1, 0, 9)},
            native_effect_areas={},
            native_retired_area_managers={},
        ), dict(area_class="anz", area_native="Directed rectangle-1x2")

    def test_registered_area_uses_its_actual_pv_position_and_facing(self):
        fight, effect = self.fixture()
        area = NativeAreaTarget(42, (0, 0, 5), 0, 7, direction=7)
        before = deepcopy(fight.__dict__)
        with patch(
            "wakfu_server.combat_effect_area_targets.retained_area_source_target",
            return_value=area,
        ) as resolve:
            self.assertEqual(
                group_cells(fight, effect, (0, 0, 99), caster_id=42),
                ((0, 0, 5), (0, -1, 8)),
            )
        resolve.assert_called_once_with(fight, 42)
        self.assertEqual(fight.__dict__, before)
        self.assertNotIn(42, fight.actors)

    def test_fighter_keeps_original_orientation_without_area_resolution(self):
        fight, effect = self.fixture()
        fight.actors[7] = SimpleNamespace(position=(0, 0, 5), direction=1)
        with patch(
            "wakfu_server.combat_effect_area_targets.retained_area_source_target"
        ) as resolve:
            self.assertEqual(
                group_cells(fight, effect, (0, 0, 99), caster_id=7),
                ((0, 0, 5), (1, 0, 9)),
            )
        resolve.assert_not_called()

    def test_unknown_caster_still_rejects_without_mutation_or_invented_facing(self):
        fight, effect = self.fixture()
        before = deepcopy(fight.__dict__)
        with self.assertRaisesRegex(ValueError, "requires caster snapshot"):
            group_cells(fight, effect, (0, 0, 5), caster_id=99)
        self.assertEqual(fight.__dict__, before)

    def test_registered_area_validation_failure_is_not_replaced_by_fighter_default(
        self,
    ):
        fight, effect = self.fixture()
        before = deepcopy(fight.__dict__)
        with patch(
            "wakfu_server.combat_effect_area_targets.retained_area_source_target",
            side_effect=ValueError("Incomplete registered area PV authority"),
        ):
            with self.assertRaisesRegex(
                ValueError, "Incomplete registered area PV authority"
            ):
                group_cells(fight, effect, (0, 0, 5), caster_id=42)
        self.assertEqual(fight.__dict__, before)
