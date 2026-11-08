"""Differential native manager validation, local invalidation and cold copies."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch
from wakfu_server.combat_retained_query import manager_query
from wakfu_server.combat_retained_collections import bound_collections
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from test_retained_indexed_query import fixture
from test_retained_local_query import payload


class SelectedManagerRecipeTests(unittest.TestCase):
    def test_local_full_authority_replacement_pending_custom_and_cold_copy(self):
        fight, retention = fixture()
        for uid, row in tuple(fight.native_owned_group_effects.items()):
            fight.native_owned_group_effects[uid] = OwnedStateSourceRow(row)
        owner = bound_collections(vars(fight))
        proofs = owner._selected_scalar_proofs

        def snapshot(view):
            return view.entries, view.by_uid, view.known

        def differential(manager):
            cached = manager_query(fight, manager)
            proofs.event_recipes.pop(manager, None)
            fresh = manager_query(fight, manager)
            self.assertEqual(snapshot(cached), snapshot(fresh))
            return fresh

        first = differential(1)
        self.assertIn(1, proofs.event_recipes)
        recipe = proofs.event_recipes[1]
        first.by_uid.clear()
        first.known.clear()
        self.assertEqual(len(manager_query(fight, 1).by_uid), 1)
        self.assertIs(proofs.event_recipes[1], recipe)
        from wakfu_server import combat_structural_event_view as event_view

        native_validator = event_view.validate_retained_entry_identity
        with patch.object(
            event_view, "validate_retained_entry_identity", wraps=native_validator
        ) as calls:
            differential(1)
            self.assertGreater(calls.call_count, 0)
            self.assertNotIn(1, proofs.event_recipes)
        differential(1)
        from wakfu_server.combat_selected_retained_values import SelectedRetainedValues

        native_read = SelectedRetainedValues.read_batch
        calls = []

        def observed_read(instance, *args, **kwargs):
            calls.append(True)
            return native_read(instance, *args, **kwargs)

        with patch.object(SelectedRetainedValues, "read_batch", observed_read):
            differential(1)
            self.assertTrue(calls)
            self.assertNotIn(1, proofs.event_recipes)
        differential(1)
        differential(2)
        unrelated = proofs.event_recipes[2]
        row = fight.native_owned_group_effects[10]
        original = row["payload"]
        row["payload"] = payload(10, 1, 102)
        self.assertNotIn(1, proofs.event_recipes)
        self.assertIs(proofs.event_recipes[2], unrelated)
        with self.assertRaises(ValueError):
            manager_query(fight, 1)
        row["payload"] = original
        differential(1)
        # Nested subscriptions remain live caller authority, not recipe fields.
        row["native_subscription_masks"] = [[1]]
        differential(1)
        row["native_subscription_masks"][0].append(2)
        differential(1)
        parent = RunningState(30, 501, 1, 2, 2, -1, "target", False, (), 0, True, None)
        fight.actors[2].state_ledger._entries = (parent,)
        fight.state_wire_payloads[30] = payload(30, 2, 103)
        retention.record(RetainedEffect(30, 2, 310, 103, manager_id=2))
        row["state_uid"] = 30
        fight.native_retained_records[10]["owner_uid"] = 30
        differential(1)
        fight.actors[2].state_ledger._entries = (replace(parent, level=2),)
        self.assertNotIn(1, proofs.event_recipes)
        differential(1)
        fight.state_wire_payloads[30] = payload(30, 2, 104)
        with self.assertRaises(ValueError):
            manager_query(fight, 1)
        fight.state_wire_payloads[30] = payload(30, 2, 103)
        differential(1)
        old_ledger = fight.actors[2].state_ledger
        fight.actors[2].state_ledger = StateLedger(2)
        self.assertNotIn(1, proofs.event_recipes)
        self.assertIsNone(manager_query(fight, 1))
        fight.actors[2].state_ledger = old_ledger
        differential(1)
        # Exercise ContextVar transitions without forging a registration: the
        # native registration scope below has wire+ledger but no metadata yet.
        from wakfu_server.combat_pending_state import pending_state_registration

        pending = replace(parent, uid=31)
        fight.actors[2].state_ledger._entries += (pending,)
        fight.state_wire_payloads[31] = payload(31, 2, 103)
        with pending_state_registration(fight, pending):
            differential(2)
            self.assertIn(2, proofs.event_recipes)
        self.assertIsNone(manager_query(fight, 2))
        fight.actors[2].state_ledger._entries = (parent,)
        del fight.state_wire_payloads[31]
        differential(1)
        # Same UID source replacement and custom readers never inherit proof.
        fight.native_owned_group_effects[10] = dict(row)
        differential(1)
        self.assertNotIn(1, proofs.event_recipes)
        fight.native_owned_group_effects[10] = OwnedStateSourceRow(row)
        differential(1)
        records = fight.native_retained_records
        calls = []
        records.get = lambda key, default=None: (
            calls.append(key),
            dict.get(records, key, default),
        )[1]
        differential(1)
        self.assertTrue(calls)
        self.assertNotIn(1, proofs.event_recipes)
        del records.get
        differential(1)
        for cloned in (deepcopy(fight), decode_state(encode_state(fight))):
            self.assertEqual(
                bound_collections(vars(cloned))._selected_scalar_proofs.event_recipes,
                {},
            )
            self.assertEqual(
                snapshot(manager_query(cloned, 1)), snapshot(manager_query(fight, 1))
            )
        self.assertLessEqual(len(proofs.event_recipes), 2)
