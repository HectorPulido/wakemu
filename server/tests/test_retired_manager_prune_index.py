"""A prune pass retains every current native source and rereads later changes."""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_state_managers import prune_retired_state_managers


def state(uid, caster, target):
    return RunningState(
        uid, 1, 1, caster, target, -1, "target", False, (), 0, True, None
    )


class RetiredManagerPruneIndexTests(unittest.TestCase):
    def test_current_references_leases_ledgers_and_children_survive_then_release(self):
        ledger = StateLedger(1)
        ledger._entries = (state(9001, 108, 1),)
        retained_ledger = StateLedger(107)
        retained_ledger._entries = (state(9002, 1, 107),)
        fight = SimpleNamespace(
            actors={1: SimpleNamespace(id=1, state_ledger=ledger)},
            native_effect_areas={},
            native_retired_area_managers={uid: {} for uid in range(101, 112)},
            native_retained_records={
                1: {"manager_id": 101},
                2: {"caster_id": 102},
                3: {"container_kind": "effect_area", "container_id": 103},
                4: {"container_kind": "spell", "container_id": 104},
            },
            native_owned_state_containers={
                900: {"uid": 900, "target_id": 109, "caster_id": 110}
            },
            owned_stat_effects={501: {"state_uid": 900}},
            native_owned_group_effects={},
        )
        fight.native_retired_area_managers[105]["executing"] = True
        fight.native_retired_area_managers[106]["removing"] = True
        fight.native_retired_area_managers[107]["state_ledger"] = retained_ledger
        prune_retired_state_managers(fight)
        self.assertEqual(
            set(fight.native_retired_area_managers),
            {101, 102, 103, 105, 106, 107, 108, 109, 110},
        )
        # These changes happen after the first complete pass, like native callbacks.
        fight.native_retained_records[1]["manager_id"] = None
        fight.native_retained_records[2]["caster_id"] = None
        fight.native_retained_records[3]["container_kind"] = "spell"
        fight.native_retired_area_managers[105]["executing"] = False
        fight.native_retired_area_managers[106]["removing"] = False
        retained_ledger._entries = ()
        ledger._entries = ()
        fight.owned_stat_effects.clear()
        prune_retired_state_managers(fight)
        self.assertEqual(fight.native_retired_area_managers, {})

    def test_non_native_values_and_custom_records_keep_original_equality_reads(self):
        class Record(dict):
            def get(self, key, default=None):
                if key != "manager_id":
                    raise AssertionError(
                        "Matching manager must retain short-circuit reads"
                    )
                return 12

        for record, identity, survives in (
            ({"manager_id": True}, 1, True),
            ({"manager_id": []}, 12, False),
            (Record(), 12, True),
        ):
            with self.subTest(identity=identity, record_type=type(record).__name__):
                fight = SimpleNamespace(
                    actors={},
                    native_effect_areas={},
                    native_retired_area_managers={
                        identity: {},
                        999: {"executing": True},
                    },
                    native_retained_records={1: record},
                    native_owned_state_containers={},
                )
                prune_retired_state_managers(fight)
                self.assertEqual(
                    identity in fight.native_retired_area_managers, survives
                )
                self.assertIn(999, fight.native_retired_area_managers)


if __name__ == "__main__":
    unittest.main()
