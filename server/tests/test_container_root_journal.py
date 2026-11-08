"""Captured descriptor root aliases have a journal independent of orphan pruning."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_owned_container_facts import OwnedContainerFacts
from wakfu_server.combat_owned_container_row import OwnedContainerRow
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow, SOURCE_MAPS
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_state import Fight
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_native_container import capture_owned_state_container


class ContainerRootJournalTests(unittest.TestCase):
    def test_original_alias_mutations_and_pruning_have_independent_journals(self):
        row = OwnedContainerRow(uid=100, caster_id=7, target_id=8, level=1)
        facts = OwnedContainerFacts({100: row})
        self.assertIs(facts[100], row)
        facts._roots_dirty.clear()
        row["level"] = 2
        self.assertFalse(facts._roots_dirty)
        row["caster_id"] = 9
        self.assertEqual(facts._roots_dirty, {100})
        facts._roots_dirty.clear()
        row.update(target_id=10)
        self.assertEqual(facts._roots_dirty, {100})
        owner = RetainedCollections()
        source = OwnedStateSourceRow(uid=1, state_uid=100)
        owner.sources["owned_stat_effects"][1] = source
        maps = {name: owner.sources[name] for name in SOURCE_MAPS}
        index = owner.source_parents
        self.assertTrue(index.prune_facts(facts, maps))
        self.assertEqual(facts._roots_dirty, {100})
        self.assertEqual(index.root_changed_parents, {100})
        self.assertFalse(index.changed_parents)
        index.root_changed_parents.clear()
        source["state_uid"] = 101
        self.assertTrue(index.prune_facts(facts, maps))
        self.assertEqual(index.root_changed_parents, {100, 101})
        self.assertEqual(facts._roots_dirty, {100})
        self.assertFalse(row._root_maps)
        facts._roots_dirty.clear()
        row["uid"] = 102
        self.assertFalse(facts._roots_dirty)
        external = {"uid": 100, "caster_id": 7, "target_id": 8}
        facts[100] = external
        self.assertIs(facts[100], external)
        self.assertEqual(facts._root_opaque, {100})
        facts[100] = row
        self.assertFalse(facts._root_opaque)
        facts.clear()
        self.assertFalse(row._root_maps)
        self.assertFalse(facts._root_bindings)

    def test_codec_and_clone_rebuild_only_current_descriptor_alias_observers(self):
        owner = RetainedCollections()
        before = object.__new__(Fight)
        before.__dict__.update(
            id=7,
            actors=owner.actors,
            native_retained_tracking=True,
            native_retained_records=owner.records,
            native_retained_order=owner.order,
            **owner.sources,
            **owner.area_sources
        )
        row = OwnedContainerRow(uid=100, caster_id=7, target_id=8)
        facts = before.native_owned_state_containers = OwnedContainerFacts({100: row})
        before.alias = row
        for after in (
            deepcopy(before),
            decode_state(json.loads(json.dumps(encode_state(before)))),
        ):
            current = after.native_owned_state_containers
            self.assertIs(type(after.alias), OwnedContainerRow)
            self.assertIs(current[100], after.alias)
            self.assertIs(current._root_bindings[100], after.alias)
            self.assertTrue(
                all(watcher() is current for watcher, uid in after.alias._root_maps)
            )
            current._roots_dirty.clear()
            facts._roots_dirty.clear()
            after.alias["target_id"] = 9
            self.assertEqual(current._roots_dirty, {100})
            self.assertFalse(facts._roots_dirty)
            self.assertEqual(row["target_id"], 8)

    def test_native_capture_refreshes_descriptor_and_detaches_historical_alias(self):
        state = RunningState(100, 3442, 1, 7, 8, -1, "target", False, (), 0, True, None)
        fight = SimpleNamespace(native_owned_state_containers=OwnedContainerFacts())
        with patch(
            "wakfu_server.combat_native_container.resolve_state_container",
            return_value=state,
        ) as resolve, patch(
            "wakfu_server.combat_native_container.owned_container_users",
            return_value=(1,),
        ):
            capture_owned_state_container(fight, 100)
            old = fight.native_owned_state_containers[100]
            self.assertIs(type(old), OwnedContainerRow)
            resolve.return_value = replace(state, level=2)
            capture_owned_state_container(fight, 100)
        current = fight.native_owned_state_containers[100]
        self.assertIsNot(old, current)
        self.assertEqual(old["level"], 1)
        self.assertEqual(current["level"], 2)
        self.assertFalse(old._root_maps)
        fight.native_owned_state_containers._roots_dirty.clear()
        old["caster_id"] = 999
        self.assertFalse(fight.native_owned_state_containers._roots_dirty)
