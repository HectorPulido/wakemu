"""Native area target forms and PV ownership contracts, without catalogs."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_area_predicates import (
    is_area_type,
    is_specific_area,
    is_own_deposit,
)


def fight(*rows):
    return SimpleNamespace(native_effect_areas={r["uid"]: r for r in rows})


def area(uid=101, owner=1, area_type=12, reference=823):
    return dict(
        uid=uid,
        owner_id=owner,
        native_type_id=area_type,
        reference=reference,
        native_area_contract="faZ",
        cell=(2, 3, 0),
        native_cells_xy=((2, 3), (3, 3)),
    )


class NativeAreaPredicateTests(unittest.TestCase):
    def test_null_target_scans_manager_without_cell_or_owner_filter(self):
        state = fight(area(owner=99))
        self.assertTrue(is_area_type(state, area_type=12, target_kind="null"))
        self.assertTrue(is_specific_area(state, reference=823, target_kind="null"))
        self.assertFalse(is_area_type(state, area_type=10, target_kind="null"))
        self.assertFalse(is_specific_area(state, reference=101, target_kind="null"))

    def test_area_target_reads_selected_prototype_without_geometry(self):
        row = area()
        row.pop("native_cells_xy")
        state = fight(row, area(uid=102, reference=900))
        self.assertTrue(
            is_specific_area(state, reference=823, target_kind="area", target_id=101)
        )
        self.assertFalse(
            is_specific_area(state, reference=900, target_kind="area", target_id=101)
        )
        self.assertFalse(
            is_area_type(state, area_type=12, target_kind="area", target_id=None)
        )

    def test_cell_target_uses_footprint_while_fighter_target_is_not_cell(self):
        state = fight(area())
        self.assertTrue(
            is_area_type(state, area_type=12, target_kind="cell", cell=(3, 3, 99))
        )
        self.assertFalse(
            is_specific_area(state, reference=823, target_kind="cell", cell=(4, 3, 0))
        )
        self.assertFalse(
            is_area_type(
                state, area_type=12, target_kind="actor", target_id=1, cell=(2, 3, 0)
            )
        )

    def test_own_deposit_compares_canonical_pv_not_controller_or_team(self):
        state = fight(area(owner=2))
        # Two native objects resolve to one PV. No team/controller fields exist.
        owners = {1: 7, 2: 7, 3: 8, None: None}
        query = owners.__getitem__
        self.assertTrue(
            is_own_deposit(
                state,
                source_id=1,
                target_kind="area",
                target_id=101,
                pv_owner_query=query,
            )
        )
        self.assertFalse(
            is_own_deposit(
                state,
                source_id=3,
                target_kind="area",
                target_id=101,
                pv_owner_query=query,
            )
        )
        self.assertFalse(
            is_own_deposit(
                state, source_id=None, target_kind="null", pv_owner_query=query
            )
        )

    def test_optional_boolean_selects_only_cell_center_xy(self):
        state = fight(area())
        kwargs = dict(
            source_id=1, pv_owner_query=lambda value: value, exclude_center=True
        )
        self.assertTrue(
            is_own_deposit(state, target_kind="cell", cell=(2, 3, 999), **kwargs)
        )
        self.assertFalse(
            is_own_deposit(state, target_kind="cell", cell=(3, 3, 0), **kwargs)
        )
        self.assertTrue(is_own_deposit(state, target_kind="null", **kwargs))
        self.assertTrue(
            is_own_deposit(state, target_kind="area", target_id=101, **kwargs)
        )

    def test_deposit_type_is_native_id_twelve_not_ordinal_ten(self):
        self.assertFalse(
            is_own_deposit(
                fight(area(area_type=10)),
                source_id=1,
                target_kind="null",
                pv_owner_query=lambda value: value,
            )
        )

    def test_explicit_null_pv_owners_compare_equal_without_synthetic_ids(self):
        self.assertTrue(
            is_own_deposit(
                fight(area(owner=None)),
                source_id=1,
                target_kind="null",
                pv_owner_query=lambda value: None,
            )
        )

    def test_unsupported_actor_and_null_caster_do_not_read_area_manager(self):
        state = SimpleNamespace(native_effect_areas="unavailable")
        self.assertFalse(is_area_type(state, area_type=12, target_kind="actor"))
        self.assertFalse(
            is_own_deposit(
                state, source_id=None, target_kind="null", pv_owner_query=None
            )
        )

    def test_missing_authority_never_becomes_false_or_success(self):
        state = fight(area())
        for kwargs in (
            dict(area_type=12, target_kind="unknown"),
            dict(area_type=12, target_kind="area", target_id=999),
            dict(area_type=12, target_kind="cell"),
            dict(area_type=True, target_kind="null"),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                is_area_type(state, **kwargs)
        with self.assertRaises(ValueError):
            is_own_deposit(state, source_id=1, target_kind="null", pv_owner_query=None)
        row = area()
        row.pop("native_type_id")
        with self.assertRaises(ValueError):
            is_area_type(fight(row), area_type=12, target_kind="null")


if __name__ == "__main__":
    unittest.main()
