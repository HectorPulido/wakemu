from copy import copy
from dataclasses import asdict
import unittest
from unittest.mock import patch

from wakfu_server import combat_structural_qf_scope as scope
from wakfu_server import combat_state_managers as managers
from wakfu_server.combat_owned_container_row import OwnedContainerRow
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_effects import _integer
import test_combat_event_replay as fixture


class ShadowContainerUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.NativeEventReplayTests.setUpClass()

    def setUp(self):
        self.case = fixture.NativeEventReplayTests()
        self.case.setUp()

    def install_valid_state_and_retired_area(self):
        fight = self.case.fight
        owner = managers._native_prune_owner(fight)
        self.assertIsNotNone(owner)
        state = RunningState(800, 61, 1, -7, -7, 1, "target", False, (), 0, True, None)
        fight.actors[-7].state_ledger._entries = (state,)
        fight.state_wire_payloads[800] = _integer(3, 123).hex()
        owner.records.install_owned(
            800,
            asdict(RetainedEffect(800, -7, 310, 123, manager_id=-7)),
        )
        owner.order.append(800)
        child_uid = next(iter(fight.native_owned_group_effects))
        fight.native_owned_group_effects[child_uid]["state_uid"] = 800
        fight.native_retained_records[child_uid]["owner_uid"] = 800
        fight.native_owned_state_containers[800] = OwnedContainerRow(asdict(state))
        fight.native_retired_area_managers[999] = OwnedAreaRow(
            {"uid": 999, "executing": True, "removing": False}
        )
        return owner, state

    @staticmethod
    def make_full_check_shadow(fight):
        shadow = copy(fight)
        shadow.native_retained_records = dict(fight.native_retained_records)
        shadow.native_retained_order = list(fight.native_retained_order)
        shadow.native_owned_state_containers = dict(fight.native_owned_state_containers)
        for name in ("native_effect_areas", "native_retired_area_managers"):
            setattr(
                shadow,
                name,
                {uid: dict(row) for uid, row in getattr(fight, name, {}).items()},
            )
        return shadow

    def test_full_check_uses_attested_source_index_and_preserves_rejection(self):
        fight = self.case.fight
        owner, state = self.install_valid_state_and_retired_area()
        before = (
            dict(fight.native_retained_records),
            tuple(fight.native_retained_order),
            dict(fight.native_owned_state_containers),
            dict(fight.native_retired_area_managers),
            tuple(fight.actors[-7].state_ledger.entries),
        )
        indexed = []
        original = managers._owned_container_state_users

        def observe(shadow):
            value = original(shadow)
            indexed.append((shadow is fight, value))
            return value

        with patch.object(
            managers, "_owned_container_state_users", side_effect=observe
        ):
            scope._full_check(self.case.retention, fight)
        self.assertGreaterEqual(len(indexed), 1)
        self.assertTrue(all(not is_live for is_live, _ in indexed))
        self.assertTrue(all(800 in users for _, users in indexed))
        self.assertEqual(
            (
                dict(fight.native_retained_records),
                tuple(fight.native_retained_order),
                dict(fight.native_owned_state_containers),
                dict(fight.native_retired_area_managers),
                tuple(fight.actors[-7].state_ledger.entries),
            ),
            before,
        )

        source_row = next(iter(fight.native_owned_group_effects.values()))
        original_users = original(fight)
        original_state_uid = source_row.get("state_uid")
        source_row["state_uid"] = 424242
        self.assertTrue(owner.source_parents.dirty)
        shadow = self.make_full_check_shadow(fight)
        with managers.qualified_prune_shadow(shadow, owner):
            self.assertEqual(
                managers._owned_container_state_users(shadow),
                (original_users - {original_state_uid}) | {424242},
            )
        self.assertFalse(owner.source_parents.dirty)
        source_row["state_uid"] = original_state_uid
        original(fight)

        uid = next(iter(fight.native_retained_records))
        prior = fight.native_retained_records[uid]["generic_effect"]
        fight.native_retained_records[uid]["generic_effect"] = True
        try:
            with self.assertRaisesRegex(ValueError, "generic definition"):
                scope._full_check(self.case.retention, fight)
        finally:
            fight.native_retained_records[uid]["generic_effect"] = prior

    def test_custom_source_or_fact_reader_keeps_legacy_fallback(self):
        fight = self.case.fight
        owner, _ = self.install_valid_state_and_retired_area()
        shadow = self.make_full_check_shadow(fight)
        source_row = next(iter(fight.native_owned_group_effects.values()))
        source_row.get = lambda key, default=None: dict.get(source_row, key, default)
        try:
            with managers.qualified_prune_shadow(shadow, owner):
                self.assertIsNone(managers._owned_container_state_users(shadow))
        finally:
            del source_row.get

        shadow = self.make_full_check_shadow(fight)
        shadow.native_owned_state_containers = dict(fight.native_owned_state_containers)
        fact = OwnedContainerRow({"uid": 700, "target_id": 7, "caster_id": 7})
        fact.get = lambda key, default=None: dict.get(fact, key, default)
        shadow.native_owned_state_containers[700] = fact
        with managers.qualified_prune_shadow(shadow, owner):
            self.assertFalse(managers._shadow_prune_callbacks_known(shadow))
            self.assertIsNone(managers._owned_container_state_users(shadow))


if __name__ == "__main__":
    unittest.main()
