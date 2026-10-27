"""Qq source-pointer lifetime without restoring spatial membership."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_state_managers import prune_retired_state_managers


class AreaSourcePointerRetentionTests(unittest.TestCase):
    def fight(self, active, retired):
        return SimpleNamespace(
            actors={},
            native_effect_areas=active,
            native_retired_area_managers=retired,
            native_retained_records={},
            native_owned_state_containers={},
        )

    def test_live_child_keeps_removed_source_until_child_disappears(self):
        parent = {"uid": 300, "owner_id": None}
        child = {"uid": 301, "owner_id": 300}
        fight = self.fight({301: child}, {300: parent})
        prune_retired_state_managers(fight)
        self.assertIs(fight.native_retired_area_managers[300], parent)
        self.assertNotIn(300, fight.native_effect_areas)
        del fight.native_effect_areas[301]
        prune_retired_state_managers(fight)
        self.assertEqual(fight.native_retired_area_managers, {})

    def test_owner_pointer_chain_survives_but_unreachable_cycle_is_released(self):
        fight = self.fight(
            {303: {"owner_id": 302}},
            {
                300: {"owner_id": None},
                302: {"owner_id": 300},
                400: {"owner_id": 401},
                401: {"owner_id": 400},
            },
        )
        prune_retired_state_managers(fight)
        self.assertEqual(set(fight.native_retired_area_managers), {300, 302})
        self.assertEqual(set(fight.native_effect_areas), {303})

    def test_retained_runner_source_keeps_its_owner_pointer(self):
        fight = self.fight({}, {300: {"owner_id": None}, 301: {"owner_id": 300}})
        fight.native_retained_records = {10: {"caster_id": 301}}
        prune_retired_state_managers(fight)
        self.assertEqual(set(fight.native_retired_area_managers), {300, 301})
        fight.native_retained_records.clear()
        prune_retired_state_managers(fight)
        self.assertEqual(fight.native_retired_area_managers, {})
