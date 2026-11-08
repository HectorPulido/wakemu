"""Instance read extensions invalidate both native root journals without callbacks."""
from types import SimpleNamespace
import unittest
from wakfu_server.combat_owned_container_facts import OwnedContainerFacts
from wakfu_server.combat_owned_container_row import OwnedContainerRow
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow, SOURCE_MAPS
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_native_container import owned_container_users
from wakfu_server.combat_retained_gc_boundary import (
    _container_row_known,
    _container_facts_known,
)


class ContainerReadOverrideTests(unittest.TestCase):
    def test_source_and_descriptor_alias_get_extensions_invalidate_and_recover(self):
        owner = RetainedCollections()
        source = OwnedStateSourceRow(uid=1, state_uid=100)
        owner.sources["owned_stat_effects"][1] = source
        maps = {name: owner.sources[name] for name in SOURCE_MAPS}
        index = owner.source_parents
        self.assertEqual(set(index.parents(maps)), {100})
        calls = []

        def custom_get(key, default=None):
            calls.append(key)
            return 200 if key == "state_uid" else default

        source.get = custom_get
        self.assertTrue(index.dirty)
        self.assertIsNone(index.parents(maps))
        self.assertEqual(calls, [])
        # The actual legacy consumer still runs the user's read extension.
        self.assertTrue(owned_container_users(SimpleNamespace(**maps), 200))
        self.assertEqual(calls, ["state_uid"])
        del source.get
        self.assertTrue(index.dirty)
        self.assertEqual(set(index.parents(maps)), {100})
        descriptor = OwnedContainerRow(uid=100, target_id=7, caster_id=8)
        facts = OwnedContainerFacts({100: descriptor})
        self.assertTrue(
            _container_facts_known(
                facts, SimpleNamespace(native_owned_state_containers=facts)
            )
        )
        self.assertTrue(_container_row_known(descriptor, facts))
        facts._roots_dirty.clear()
        descriptor.get = custom_get
        self.assertEqual(facts._roots_dirty, {100})
        self.assertFalse(_container_row_known(descriptor, facts))
        self.assertEqual(calls, ["state_uid"])
        facts._roots_dirty.clear()
        del descriptor.get
        self.assertEqual(facts._roots_dirty, {100})
        self.assertTrue(_container_row_known(descriptor, facts))
        self.assertEqual(calls, ["state_uid"])
