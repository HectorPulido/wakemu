"""A native wrapper with an observable method override keeps legacy reads."""
import unittest
from wakfu_server.combat_state import Fight
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server import combat_state_managers as managers


class PruneWrapperCallbackTests(unittest.TestCase):
    def test_shadowed_get_abstains_without_invoking_custom_callback(self):
        owner = RetainedCollections()
        fight = Fight.__new__(Fight)
        fight.actors = owner.actors
        fight.native_retained_records = owner.records
        fight.native_retained_order = owner.order
        for name, rows in (*owner.sources.items(), *owner.area_sources.items()):
            setattr(fight, name, rows)
        calls = []
        row = OwnedStateSourceRow(state_uid=900)
        row.get = lambda key, default=None: calls.append(key) or 900
        fight.owned_stat_effects[1] = row
        self.assertIsNone(managers._owned_container_state_users(fight))
        record = owner.records.install_owned(1, {"uid": 1, "manager_id": 101})
        record.get = lambda key, default=None: calls.append(key) or 101
        self.assertIsNone(
            managers._retained_manager_users(owner.records, _native_owned=True)
        )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
