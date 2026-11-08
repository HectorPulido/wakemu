"""Native ownership gateways and replay preserve source identity and parent users."""
from copy import deepcopy
import json
import unittest

from wakfu_server.combat_source_parent_index import OwnedStateSourceRow, SOURCE_MAPS
from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    replace_collection,
)
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_state import Fight


def fight(owner):
    result = object.__new__(Fight)
    result.__dict__.update(
        id=7,
        actors=owner.actors,
        native_retained_tracking=True,
        native_retained_records=owner.records,
        native_retained_order=owner.order,
        **owner.sources,
        **owner.area_sources
    )
    return result


def parents(owner):
    return owner.source_parents.parents(
        {name: owner.sources[name] for name in SOURCE_MAPS}
    )


class SourceParentIntegrationTests(unittest.TestCase):
    def test_map_gateway_alias_replacement_and_deepcopy(self):
        owner = RetainedCollections()
        current = fight(owner)
        row = OwnedStateSourceRow(uid=11, state_uid=91)
        owner.sources["owned_stat_effects"][11] = row
        owner.sources["native_owned_group_effects"][12] = row
        self.assertEqual(set(parents(owner)), {91})
        self.assertEqual(owner.source_parents.counts[91], 2)
        from wakfu_server.combat_retained_gc_boundary import _source_row_known

        self.assertTrue(_source_row_known(row, owner))

        class Opaque:
            def get(self, *args):
                raise AssertionError("Opaque index getter executed")

            def update(self, *args):
                raise AssertionError("Opaque observer callback executed")

        for field in ("maps", "bindings", "dirty"):
            previous = getattr(owner.source_parents, field)
            setattr(owner.source_parents, field, Opaque())
            self.assertFalse(_source_row_known(row, owner))
            setattr(owner.source_parents, field, previous)
        row.extra = lambda: None
        self.assertFalse(_source_row_known(row, owner))
        del row.extra

        row["state_uid"] = 92
        self.assertEqual(set(parents(owner)), {92})
        copied = deepcopy(owner)
        self.assertIs(
            copied.sources["owned_stat_effects"][11],
            copied.sources["native_owned_group_effects"][12],
        )
        copied.sources["owned_stat_effects"][11]["state_uid"] = 93
        self.assertEqual(set(parents(copied)), {93})
        self.assertEqual(set(parents(owner)), {92})
        replace_collection(current, "owned_stat_effects", {})
        self.assertEqual(set(parents(owner)), {92})
        owner.sources["native_owned_group_effects"].clear()
        self.assertEqual(set(parents(owner)), set())
        opaque = {"state_uid": 94}
        owner.sources["native_owned_area_effects"][13] = opaque
        self.assertIs(owner.sources["native_owned_area_effects"][13], opaque)
        self.assertIsNone(parents(owner))
        del owner.sources["native_owned_area_effects"][13]
        self.assertEqual(set(parents(owner)), set())

    def test_replay_restores_source_aliases_and_derived_parent_observers(self):
        owner = RetainedCollections()
        before = fight(owner)
        row = OwnedStateSourceRow(uid=11, state_uid=91, invocation={"level": 1})
        before.owned_stat_effects[11] = row
        before.native_owned_group_effects[12] = row
        before.source_alias = row
        payload = encode_state(before)
        after = decode_state(json.loads(json.dumps(payload)))
        restored = after.native_retained_records.owner
        self.assertIs(type(after.source_alias), OwnedStateSourceRow)
        self.assertIs(after.source_alias, after.owned_stat_effects[11])
        self.assertIs(after.source_alias, after.native_owned_group_effects[12])
        self.assertEqual(set(parents(restored)), {91})
        self.assertEqual(restored.source_parents.counts[91], 2)
        after.source_alias["state_uid"] = 92
        self.assertEqual(set(parents(restored)), {92})
        self.assertEqual(set(parents(owner)), {91})
        self.assertEqual(
            set(after.source_alias._parent_watchers), {restored.source_parents}
        )
