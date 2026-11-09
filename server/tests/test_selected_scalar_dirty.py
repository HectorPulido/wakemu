"""Scalar-only proof dirtiness; full retained authority is not cached."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from wakfu_server import combat_retained_query as query
from wakfu_server.combat_retained_collections import bound_collections
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from test_retained_indexed_query import fixture


class SelectedScalarDirtyTests(unittest.TestCase):
    def test_local_mutation_parent_wire_custom_and_cold_clone_codec(self):
        fight, _ = fixture()
        for uid, row in tuple(fight.native_owned_group_effects.items()):
            fight.native_owned_group_effects[uid] = OwnedStateSourceRow(row)
        owner = bound_collections(vars(fight))
        routing = query.prepare_routing(fight)
        self.assertIsNotNone(routing)

        # Exercise scalar proof independently; full routing still runs in manager_query.
        def check(manager):
            return query._selected_scalars(
                fight, routing, routing.by_manager.get(manager, ()), manager
            )

        self.assertTrue(check(1))
        self.assertTrue(check(2))
        with patch.object(
            query, "_row_scalar_proof", wraps=query._row_scalar_proof
        ) as calls:
            self.assertTrue(check(1))
            self.assertTrue(check(2))
            self.assertEqual(calls.call_count, 0)
        proof2 = owner._selected_scalar_proofs.managers[2]
        row = fight.native_owned_group_effects[10]
        original = row["payload"]
        row["payload"] = original + "00"
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        self.assertIs(owner._selected_scalar_proofs.managers[2], proof2)
        self.assertTrue(check(1))
        row["payload"] = object()
        self.assertFalse(check(1))
        row["payload"] = original
        self.assertTrue(check(1))
        record = fight.native_retained_records[10]
        record["owner_uid"] = 20
        self.assertTrue(check(1))
        fight.state_wire_payloads[20] = object()
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        self.assertFalse(check(1))
        del fight.state_wire_payloads[20]
        self.assertTrue(check(1))
        record["owner_uid"] = None
        self.assertTrue(check(1))
        proof1 = owner._selected_scalar_proofs.managers[1]
        fight.native_retained_records[20]["generic_effect"] = 102
        self.assertIs(owner._selected_scalar_proofs.managers[1], proof1)
        fight.native_retained_records[20]["generic_effect"] = 101
        record.values = lambda: dict.values(record)
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        self.assertFalse(check(1))
        del record.values
        self.assertTrue(check(1))
        row.get = lambda key, default=None: dict.get(row, key, default)
        self.assertFalse(check(1))
        del row.get
        self.assertTrue(check(1))
        fight.native_owned_group_effects[10] = dict(row)
        self.assertTrue(check(1))
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        fight.native_owned_group_effects[10] = OwnedStateSourceRow(row)
        self.assertTrue(check(1))
        from wakfu_server.combat_retained_collections import RetainedCollections

        record = fight.native_retained_records[10]
        foreign = RetainedCollections()
        record.owner = foreign
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        self.assertTrue(check(1))
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        record.owner = owner
        self.assertTrue(check(1))
        record.uid = 999
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        record.uid = 10
        self.assertTrue(check(1))
        row = fight.native_owned_group_effects[10]
        watchers = row._parent_watchers
        del row._parent_watchers
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        self.assertTrue(check(1))
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        row._parent_watchers = watchers
        self.assertTrue(check(1))
        row._invalidate_scalar = lambda: None
        row["payload"] = object()
        self.assertNotIn(1, owner._selected_scalar_proofs.managers)
        self.assertFalse(check(1))
        row["payload"] = original
        del row._invalidate_scalar
        self.assertTrue(check(1))
        from wakfu_server.combat_retained_collections import OwnedMap

        calls = []
        records = fight.native_retained_records

        def instance_get(uid, default=None):
            calls.append(uid)
            return dict.get(records, uid, default)

        records.get = instance_get
        try:
            self.assertTrue(check(1))
            self.assertTrue(calls)
            self.assertEqual(owner._selected_scalar_proofs.managers, {})
        finally:
            del records.get
        self.assertTrue(check(1))
        calls.clear()

        def class_get(mapping, uid, default=None):
            calls.append(uid)
            return dict.get(mapping, uid, default)

        with patch.object(OwnedMap, "get", class_get):
            self.assertTrue(check(1))
            self.assertTrue(calls)
            self.assertEqual(owner._selected_scalar_proofs.managers, {})
        self.assertTrue(check(1))
        # Full query remains live: changing actual payload must still be noticed.
        row = fight.native_owned_group_effects[10]
        row["payload"] = "zz"
        self.assertTrue(check(1))
        with self.assertRaises(ValueError):
            query.manager_query(fight, 1)
        row["payload"] = original
        self.assertTrue(check(1))
        for cloned in (deepcopy(fight), decode_state(encode_state(fight))):
            cloned_owner = bound_collections(vars(cloned))
            self.assertEqual(cloned_owner._selected_scalar_proofs.managers, {})
            self.assertEqual(cloned_owner._selected_scalar_proofs.dependents, {})
        from wakfu_server.wakia_bridge.wakfu_ai.context.native_context import (
            _instance_fields,
        )

        self.assertNotIn("_selected_scalar_proofs", _instance_fields(owner))
        self.assertLessEqual(len(owner._selected_scalar_proofs.managers), 2)


if __name__ == "__main__":
    unittest.main()
