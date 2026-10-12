"""Selected Qq identity predicates do not require a fighter state manager."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_area_predicates import is_own_area


class SelectedAreaSnapshotTests(unittest.TestCase):
    def row(self):
        return dict(
            uid=101,
            owner_id=7,
            native_type_id=19,
            reference=823,
            native_area_contract="faZ",
            cell=(2, 3, 0),
            native_cells_xy=((2, 3), (3, 3)),
        )

    def query(self, fight, owner=7):
        return is_own_area(
            fight,
            source_id=owner,
            target_kind="area",
            target_id=101,
            pv_owner_query=lambda identity: identity,
        )

    def test_active_selected_owner_query_needs_no_fighter_state_manager(self):
        fight = SimpleNamespace(native_effect_areas={101: self.row()})
        self.assertTrue(self.query(fight))
        self.assertFalse(self.query(fight, owner=8))

    def test_active_selected_uid_mismatch_remains_rejected(self):
        row = self.row()
        row["uid"] = 102
        with self.assertRaises(ValueError):
            self.query(SimpleNamespace(native_effect_areas={101: row}))

    def test_actual_fighter_collision_remains_rejected(self):
        fight = SimpleNamespace(
            native_effect_areas={101: self.row()}, actors={101: object()}
        )
        with self.assertRaisesRegex(ValueError, "identity collision"):
            self.query(fight)


if __name__ == "__main__":
    unittest.main()
