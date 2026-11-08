"""Native storage wrappers retain the same prune result without repeated scans."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server import combat_state_managers as managers
from wakfu_server import combat_native_container as containers


def state(uid, caster, target):
    return RunningState(
        uid, 1, 1, caster, target, -1, "target", False, (), 0, True, None
    )


def plain_reference(fight):
    fields = dict(vars(fight))
    for name in (
        "native_effect_areas",
        "native_retired_area_managers",
        "native_retained_records",
        "native_owned_state_containers",
        "owned_stat_effects",
        "native_owned_group_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
    ):
        fields[name] = {uid: dict(row) for uid, row in fields[name].items()}
    fields["actors"] = dict(fight.actors)
    return SimpleNamespace(**fields)


class PruneWrapperCompatibilityTests(unittest.TestCase):
    def test_native_wrappers_match_plain_prune_and_custom_rows_keep_fallback(self):
        owner = RetainedCollections()
        fight = Fight.__new__(Fight)
        fight.actors = owner.actors
        fight.native_retained_records = owner.records
        fight.native_retained_order = owner.order
        for name, rows in (*owner.sources.items(), *owner.area_sources.items()):
            setattr(fight, name, rows)
        actor = Actor(1, 0, (0, 0, 0), 10, 6, 3, 1, 1)
        actor.state_ledger._entries = (state(9001, 108, 1),)
        fight.actors[1] = actor
        for uid in range(101, 112):
            fight.native_retired_area_managers[uid] = OwnedAreaRow(uid=uid)
        for uid, fields in enumerate(
            (
                {"manager_id": 101},
                {"caster_id": 102},
                {"container_kind": "effect_area", "container_id": 103},
            ),
            1,
        ):
            row = {"uid": uid, "manager_id": 1, **fields}
            owner.records.install_owned(uid, row)
            owner.order.append(uid)
        fight.native_retired_area_managers[105]["executing"] = True
        fight.native_retired_area_managers[106]["removing"] = True
        ledger = StateLedger(107)
        ledger._entries = (state(9002, 1, 107),)
        fight.native_retired_area_managers[107]["state_ledger"] = ledger
        fight.native_owned_state_containers = {
            900: {"uid": 900, "target_id": 109, "caster_id": 110}
        }
        child = OwnedStateSourceRow(state_uid=900)
        fight.owned_stat_effects[501] = child

        for phase in range(2):
            expected = plain_reference(fight)
            managers.prune_retired_state_managers(expected)
            with patch.object(
                managers,
                "_retained_manager_users",
                wraps=managers._retained_manager_users,
            ) as indexed:
                with patch.object(
                    containers,
                    "owned_container_users",
                    side_effect=AssertionError("repeated source scan"),
                ):
                    managers.prune_retired_state_managers(fight)
            self.assertEqual(indexed.call_count, 1)
            self.assertEqual(
                set(fight.native_retired_area_managers),
                set(expected.native_retired_area_managers),
            )
            if phase == 0:
                self.assertEqual(
                    set(fight.native_retired_area_managers),
                    {101, 102, 103, 105, 106, 107, 108, 109, 110},
                )
                owner.records.clear()
                owner.order.clear()
                child["state_uid"] = None
                actor.state_ledger._entries = ()
                ledger._entries = ()
                fight.native_retired_area_managers[105]["executing"] = False
                fight.native_retired_area_managers[106]["removing"] = False
        self.assertEqual(fight.native_retired_area_managers, {})

        class CustomRow(dict):
            def get(self, key, default=None):
                raise AssertionError("eligibility read an opaque getter")

        fight.owned_stat_effects[502] = CustomRow(state_uid=900)
        self.assertIsNone(managers._owned_container_state_users(fight))
        # Known wrapper rows in foreign maps do not gain native ownership proof.
        fight.owned_stat_effects = {501: child}
        self.assertIsNone(managers._owned_container_state_users(fight))


if __name__ == "__main__":
    unittest.main()
