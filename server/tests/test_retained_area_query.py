"""Selected Qq reads use actual state-manager and published prototype authority."""
import unittest

from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_effects import _integer
from wakfu_server.combat_retained_area_query import (
    selected_area_manager,
    selected_area_row,
)
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_query import manager_query
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_state_managers import state_manager, registered_area_pv
from test_retained_indexed_query import fixture


def area_payload(generic=103):
    return b"".join(
        _integer(key, value)
        for key, value in ((1, 30), (2, 30), (3, generic), (6, 1), (7, 901))
    ).hex()


def install_area(fight, retention, *, with_carrier=True):
    # Same genuine GLYPH/Qf contract as StateManagerTests; select a published
    # prototype whose native property12 actually authorizes the state manager.
    definitions = native_effect_areas()
    choices = [
        (int(key), definition)
        for key, definition in definitions.items()
        if definition.get("type") == "GLYPH"
        and 12 in definition.get("native_area_properties", ())
    ]
    if not choices:
        raise AssertionError("Published GLYPH with native Qf property12 required")
    reference, definition = min(choices, key=lambda pair: pair[0])
    row = OwnedAreaRow(
        uid=901,
        reference=reference,
        cell=(2, 3, 4),
        owner_id=1,
        native_area_contract="faY",
        native_running_effect_manager=True,
        native_qq_bhi=False,
        native_qq_guard_source="Qq.constructor",
        child_effect_uids={},
        state_ledger=StateLedger(901),
    )
    fight.native_effect_areas[901] = row
    if with_carrier:
        row["state_ledger"]._entries = (
            RunningState(30, 501, 1, 1, 901, -1, "target", False, (), 0, True, None),
        )
        fight.state_wire_payloads[30] = area_payload()
        retention.record(RetainedEffect(30, 901, 310, 103, manager_id=901))
    # These assertions execute the production providers; no provider is patched.
    if state_manager(fight, 901).state_ledger is not row["state_ledger"]:
        raise AssertionError("Area ledger did not resolve through native manager")
    if not registered_area_pv(fight, 901).native_running_effect_manager:
        raise AssertionError("Published area does not own a native Qf")
    return row


class RetainedAreaQueryTests(unittest.TestCase):
    def test_area_carrier_and_cross_manager_dependency_match_complete_view(self):
        fight, retention = fixture()
        row = install_area(fight, retention)
        fight.native_owned_group_effects[10]["state_uid"] = 30
        fight.native_retained_records[10]["owner_uid"] = 30
        full = retention.view()
        self.assertIs(
            selected_area_manager(fight, 901).state_ledger, row["state_ledger"]
        )
        self.assertEqual(manager_query(fight, 901).entries, full.manager_entries(901))
        self.assertEqual(manager_query(fight, 1).entries, full.manager_entries(1))
        # Unrelated wire is not authority for either selected manager.
        fight.native_owned_group_effects[20]["payload"] = "zz"
        self.assertEqual(
            [entry.uid for entry in manager_query(fight, 901).entries], [30]
        )
        self.assertEqual([entry.uid for entry in manager_query(fight, 1).entries], [10])
        with self.assertRaises(ValueError):
            retention.view()
        # A dependency mutation is observed, including through the area lookup.
        fight.state_wire_payloads[30] = area_payload(104)
        with self.assertRaises(ValueError):
            manager_query(fight, 1)

    def test_foreign_opaque_and_null_qf_rows_decline_without_fabricated_authority(self):
        fight, retention = fixture()
        row = install_area(fight, retention, with_carrier=False)
        self.assertIsNotNone(manager_query(fight, 901))
        row["opaque"] = object()
        self.assertIsNone(selected_area_row(fight, 901))
        self.assertIsNone(manager_query(fight, 901))
        del row["opaque"]
        row["state_ledger"] = StateLedger(902)
        with self.assertRaisesRegex(ValueError, "state manager"):
            selected_area_manager(fight, 901)
        row["state_ledger"] = StateLedger(901)
        original = row
        foreign = dict(row)
        fight.native_effect_areas[901] = foreign
        self.assertIs(fight.native_effect_areas[901], foreign)
        self.assertIsNone(selected_area_row(fight, 901))
        fight.native_effect_areas[901] = original
        row["native_running_effect_manager"] = False
        del row["state_ledger"]
        self.assertIsNone(state_manager(fight, 901))
        self.assertIsNone(selected_area_manager(fight, 901))
        self.assertIsNone(manager_query(fight, 901))

    def test_selected_uid_type_rejects_custom_equality_without_calling_it(self):
        fight, retention = fixture()
        row = install_area(fight, retention, with_carrier=False)

        class OpaqueIdentity:
            def __eq__(self, other):
                raise AssertionError("Native guard invoked custom UID equality")

        # Direct dictionary mutation models a foreign write to an owned row.
        dict.__setitem__(row, "uid", OpaqueIdentity())
        self.assertIsNone(selected_area_row(fight, 901))


if __name__ == "__main__":
    unittest.main()
