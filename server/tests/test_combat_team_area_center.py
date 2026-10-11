"""Selected Qq centers must not become the parent's raw placement cell."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_team_area_center import team_area_center


class TeamAreaCenterTests(unittest.TestCase):
    def setUp(self):
        self.fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, position=(1, 2, 0))}
        )
        self.invocation = SimpleNamespace(
            caster_id=7, target_id=39, cell=(8, 9, 0), native_target_cell_argument=False
        )

    def test_registered_area_pv_precedes_parent_placement_cell(self):
        with patch(
            "wakfu_server.combat_team_area_center.registered_area_pv",
            return_value=SimpleNamespace(id=39, position=(3, 4, 0)),
        ) as lookup:
            self.assertEqual(
                team_area_center(self.fight, self.invocation, "target"), (3, 4, 0)
            )
            lookup.assert_called_once_with(self.fight, 39)
        self.assertEqual(
            team_area_center(self.fight, self.invocation, "caster"), (1, 2, 0)
        )

    def test_unknown_nonnull_pv_does_not_fall_back_to_cell(self):
        with patch(
            "wakfu_server.combat_team_area_center.registered_area_pv", return_value=None
        ):
            with self.assertRaisesRegex(
                ValueError, "Missing native team-area selected PV"
            ):
                team_area_center(self.fight, self.invocation, "target")

    def test_null_and_explicit_cell_arguments_preserve_native_cell_route(self):
        self.invocation.target_id = None
        self.assertEqual(
            team_area_center(self.fight, self.invocation, "target"), (8, 9, 0)
        )
        self.invocation.target_id = 39
        self.invocation.native_target_cell_argument = True
        with patch("wakfu_server.combat_team_area_center.registered_area_pv") as lookup:
            self.assertEqual(
                team_area_center(self.fight, self.invocation, "target"), (8, 9, 0)
            )
            lookup.assert_not_called()
