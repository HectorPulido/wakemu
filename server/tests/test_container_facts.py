"""Descriptor pruning follows actual users without revisiting unchanged descriptors."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from wakfu_server.combat_owned_container_facts import OwnedContainerFacts
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow, SOURCE_MAPS
from wakfu_server.combat_retained_collections import RetainedCollections
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_state import Fight


def sources(owner):
    return {name: owner.sources[name] for name in SOURCE_MAPS}


def fixture():
    owner = RetainedCollections()
    row = OwnedStateSourceRow(uid=1, state_uid=100)
    owner.sources["owned_stat_effects"][1] = row
    facts = OwnedContainerFacts({100: {"uid": 100, "level": 1}, 900: {"uid": 900}})
    return owner, row, facts


class ContainerFactsTests(unittest.TestCase):
    def test_unchanged_and_single_parent_mutations_never_iterate_facts(self):
        owner, row, facts = fixture()
        index = owner.source_parents
        self.assertTrue(index.prune_facts(facts, sources(owner)))
        self.assertEqual(dict(facts), {100: {"uid": 100, "level": 1}})
        descriptor_alias = facts[100]
        with patch.object(
            OwnedContainerFacts,
            "__iter__",
            create=True,
            side_effect=AssertionError("Global descriptor iteration"),
        ):
            self.assertTrue(index.prune_facts(facts, sources(owner)))
            descriptor_alias["level"] = 2
            facts[900] = {"uid": 900}
            self.assertTrue(index.prune_facts(facts, sources(owner)))
            self.assertNotIn(900, facts)
            self.assertIs(facts[100], descriptor_alias)
            facts[101] = {"uid": 101}
            row["state_uid"] = 101
            # A separate local reader may drain source dirtiness first.
            self.assertEqual(set(index.parents(sources(owner))), {101})
            self.assertTrue(index.prune_facts(facts, sources(owner)))
            self.assertNotIn(100, facts)
            self.assertIn(101, facts)
            del owner.sources["owned_stat_effects"][1]
            self.assertTrue(index.prune_facts(facts, sources(owner)))
            self.assertFalse(facts)
            self.assertTrue(index.prune_facts(facts, sources(owner)))

    def test_replacement_and_opaque_alias_recovery_require_initial_reconciliation(self):
        owner, row, facts = fixture()
        index = owner.source_parents
        self.assertTrue(index.prune_facts(facts, sources(owner)))
        external = {900: {"uid": 900}}
        self.assertFalse(index.prune_facts(external, sources(owner)))
        self.assertEqual(external, {900: {"uid": 900}})
        replacement = OwnedContainerFacts({100: {"uid": 100}, 900: {"uid": 900}})
        replacement._dirty.clear()  # A new map needs reconciliation independent of its journal.
        self.assertTrue(index.prune_facts(replacement, sources(owner)))
        self.assertEqual(set(replacement), {100})
        opaque = {"state_uid": 200}
        owner.sources["native_owned_group_effects"][2] = opaque
        self.assertFalse(index.prune_facts(replacement, sources(owner)))
        self.assertIs(owner.sources["native_owned_group_effects"][2], opaque)
        replacement[200] = {"uid": 200}
        replacement._dirty.clear()
        del owner.sources["native_owned_group_effects"][2]
        self.assertTrue(index.prune_facts(replacement, sources(owner)))
        self.assertEqual(set(replacement), {100})

    def test_clone_and_codec_restore_independent_journals_and_same_descriptor_alias(
        self,
    ):
        owner, row, facts = fixture()
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
        before.native_owned_state_containers = facts
        before.descriptor_alias = facts[100]
        self.assertTrue(owner.source_parents.prune_facts(facts, sources(owner)))
        for after in (
            deepcopy(before),
            decode_state(json.loads(json.dumps(encode_state(before)))),
        ):
            clone = after.native_retained_records.owner
            current = after.native_owned_state_containers
            self.assertIs(type(current), OwnedContainerFacts)
            self.assertIs(after.descriptor_alias, current[100])
            current[900] = {"uid": 900}
            self.assertTrue(clone.source_parents.prune_facts(current, sources(clone)))
            self.assertNotIn(900, current)
            after.owned_stat_effects[1]["state_uid"] = 101
            self.assertTrue(clone.source_parents.prune_facts(current, sources(clone)))
            self.assertNotIn(100, current)
            self.assertIn(100, facts)
