"""Focused pending-state recipe invalidation tests for the isolated candidate."""
import unittest
from unittest.mock import patch

from test_retained_indexed_query import fixture
from test_retained_local_query import payload
from wakfu_server.combat_pending_state import pending_state_registration
from wakfu_server.combat_retained_collections import bound_collections
from wakfu_server.combat_retained_query import manager_query, prepare_routing
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server import combat_selected_manager_recipe as recipe_module


class SelectedPendingLocalTests(unittest.TestCase):
    def native_fixture(self):
        fight, _retention = fixture()
        for uid, row in tuple(fight.native_owned_group_effects.items()):
            fight.native_owned_group_effects[uid] = OwnedStateSourceRow(row)
        return fight, bound_collections(vars(fight))._selected_scalar_proofs

    @staticmethod
    def state(uid, target):
        return RunningState(
            uid, 501, 1, target, target, -1, "target", False, (), 0, True, None
        )

    @staticmethod
    def add_pending_ledger_state(fight, state):
        actor = fight.actors[state.target_id]
        actor.state_ledger._entries = actor.state_ledger.entries + (state,)
        fight.state_wire_payloads[state.uid] = payload(state.uid, state.target_id, 103)

    def test_unrelated_pending_state_reuses_recipe_and_matches_fresh_view(self):
        fight, proofs = self.native_fixture()
        first = self.state(30, 2)
        self.add_pending_ledger_state(fight, first)
        with pending_state_registration(fight, first):
            original = manager_query(fight, 1)
            recipe = proofs.event_recipes[1]
            self.assertNotIn(30, recipe[2])

            second = self.state(31, 2)
            self.add_pending_ledger_state(fight, second)
            with pending_state_registration(fight, second):
                with patch.object(
                    recipe_module, "reuse", wraps=recipe_module.reuse
                ) as reuse:
                    reused = manager_query(fight, 1)
                self.assertTrue(reuse.called)
                self.assertIs(proofs.event_recipes[1], recipe)
                self.assertEqual(
                    (reused.entries, reused.by_uid, reused.known),
                    (original.entries, original.by_uid, original.known),
                )

                # Force the constructor path with the same live source and
                # pending scopes; compare all public view products exactly.
                with patch.object(recipe_module, "reuse", return_value=None):
                    fresh = manager_query(fight, 1)
                self.assertEqual(
                    (reused.entries, reused.by_uid, reused.known),
                    (fresh.entries, fresh.by_uid, fresh.known),
                )

    def test_pending_parent_uid_is_a_recipe_dependency(self):
        fight, proofs = self.native_fixture()
        parent = self.state(30, 2)
        self.add_pending_ledger_state(fight, parent)
        fight.native_owned_group_effects[10]["state_uid"] = 30
        fight.native_retained_records[10]["owner_uid"] = 30
        with pending_state_registration(fight, parent):
            self.assertEqual(manager_query(fight, 1).entries[0].uid, 10)
            recipe = proofs.event_recipes[1]
            self.assertIn(30, recipe[2])
            self.assertEqual(recipe[1], frozenset({30}))
            routing = prepare_routing(fight)
        # The parent is no longer pending. Its source is now missing, so the
        # previously accepted recipe must be evicted rather than reused.
        self.assertIsNone(recipe_module.reuse(routing, 1, frozenset()))
        self.assertNotIn(1, proofs.event_recipes)

    def test_selected_manager_ledger_only_pending_uid_is_a_dependency(self):
        fight, proofs = self.native_fixture()
        pending = self.state(32, 1)
        self.add_pending_ledger_state(fight, pending)
        with pending_state_registration(fight, pending):
            view = manager_query(fight, 1)
            self.assertEqual(tuple(entry.uid for entry in view.entries), (10,))
            recipe = proofs.event_recipes[1]
            self.assertIn(32, recipe[2])
            self.assertIn(32, recipe[1])
            routing = prepare_routing(fight)
        self.assertIsNone(recipe_module.reuse(routing, 1, frozenset()))
        self.assertNotIn(1, proofs.event_recipes)


if __name__ == "__main__":
    unittest.main()
