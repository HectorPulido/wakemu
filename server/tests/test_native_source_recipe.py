"""Registered actor recipes preserve native nullable area/group authority."""
from copy import deepcopy
from dataclasses import asdict, replace
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
from test_retained_indexed_query import fixture
from wakfu_server.combat_effects import _integer
from wakfu_server.combat_retained_collections import bound_collections
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_query import manager_query, prepare_routing
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server import combat_structural_event_view as event_view
from wakfu_server import combat_selected_manager_recipe as recipes
from wakfu_server import combat_private_target_aura as private_aura


class NativeSourceRecipeTests(unittest.TestCase):
    def test_nullable_native_sources_reuse_fresh_authority_and_custom_fallback(self):
        fight, retention = fixture()

        def payload(uid, caster):
            return b"".join(
                _integer(k, v) for k, v in ((1, uid), (2, uid), (3, 101), (6, caster))
            ).hex()

        del fight.native_owned_group_effects[10]
        fight.native_owned_area_effects[10] = OwnedStateSourceRow(
            caster_id=1,
            target_id=None,
            effect_class=315,
            state_uid=None,
            payload=payload(10, 1),
        )
        fight.native_retained_records.install_owned(
            10, asdict(RetainedEffect(10, None, 315, 101, manager_id=1))
        )
        fight.native_owned_group_effects[20] = OwnedStateSourceRow(
            target_id=None, effect_class=330, state_uid=None, payload=payload(20, 2)
        )
        fight.native_retained_records.install_owned(
            20, asdict(RetainedEffect(20, None, 330, 101, manager_id=2))
        )
        owner = bound_collections(vars(fight))
        proofs = owner._selected_scalar_proofs

        def result(view):
            self.assertIsNotNone(view)
            return view.entries, view.by_uid, view.known

        def query_calls(manager):
            calls = []
            code = event_view.NativeRetainedEventView.__init__.__code__
            prior = sys.getprofile()

            def observe(frame, event, arg):
                if event == "call" and frame.f_code is code:
                    calls.append(True)

            try:
                sys.setprofile(observe)
                view = manager_query(fight, manager)
            finally:
                sys.setprofile(prior)
            return view, len(calls)

        for manager in (1, 2):
            cold, cold_calls = query_calls(manager)
            self.assertEqual(cold_calls, 1)
            self.assertIn(manager, proofs.event_recipes)
            warm, warm_calls = query_calls(manager)
            self.assertEqual(warm_calls, 0)
            self.assertEqual(result(cold), result(warm))
            self.assertIsNot(cold, warm)
            self.assertEqual(warm.entries, retention.view().manager_entries(manager))
            proofs.event_recipes.pop(manager)
            fresh, fresh_calls = query_calls(manager)
            self.assertEqual(fresh_calls, 1)
            self.assertEqual(result(warm), result(fresh))
        area = fight.native_owned_area_effects[10]
        original_payload = area["payload"]
        area["payload"] = "zz"
        self.assertNotIn(1, proofs.event_recipes)
        with self.assertRaises(ValueError):
            manager_query(fight, 1)
        area["payload"] = original_payload
        manager_query(fight, 1)
        fight.actors[1] = deepcopy(fight.actors[1])
        _, count = query_calls(1)
        self.assertEqual(count, 1)
        fight.actors[1].state_ledger = StateLedger(1)
        _, count = query_calls(1)
        self.assertEqual(count, 1)
        for module, name, manager in (
            (private_aura, "validate_private_target_aura", 1),
            (event_view, "registered_or_detached_actor", 2),
        ):
            original = getattr(module, name)
            with patch.object(module, name, wraps=original) as callback:
                cached, count = query_calls(manager)
                self.assertEqual(count, 1)
                self.assertTrue(callback.called)
                self.assertNotIn(manager, proofs.event_recipes)
                self.assertIsNotNone(cached)
            manager_query(fight, manager)
        # Private338 requires its live private-area authority. Nested private
        # metadata is outside primitive scalar certification, never a recipe.
        area.update(
            effect_class=338,
            target_id=1,
            native_manager_source="eYJ.PK.owner_on_caster",
            native_manager_id=1,
            uid=10,
            area_uid=99,
            native_private_area=dict(
                uid=99,
                reference=1,
                level=1,
                anchor_id=1,
                owner_id=1,
                source=private_aura.SOURCE,
                native_area_contract="faN",
                registered=False,
                creation_callbacks_executed=False,
            ),
            payload=original_payload + _integer(7, 1).hex(),
        )
        fight.native_retained_records.install_owned(
            10, asdict(RetainedEffect(10, 1, 338, 101, manager_id=1))
        )
        self.assertIsNone(manager_query(fight, 1))
        self.assertNotIn(1, proofs.event_recipes)
        # The remaining unsupported families are eligibility checks against
        # an already validated group view; they do not forge summon/spatial
        # source bodies or claim that those complete constructors ran.
        view = manager_query(fight, 2)
        routing = prepare_routing(fight)
        managers = SimpleNamespace(by_identity={2: fight.actors[2]})
        proofs.event_recipes.pop(2, None)
        forbidden = SimpleNamespace(
            entries=(replace(view.entries[0], effect_class=307),), known=view.known
        )
        recipes.remember(routing, 2, frozenset(), managers, forbidden)
        self.assertNotIn(2, proofs.event_recipes)
        fight.native_owned_spatial_effects[20] = OwnedStateSourceRow(state_uid=None)
        recipes.remember(routing, 2, frozenset(), managers, view)
        self.assertNotIn(2, proofs.event_recipes)
        del fight.native_owned_spatial_effects[20]
        view = manager_query(fight, 2)
        proofs.event_recipes.pop(2, None)
        routing = prepare_routing(fight)
        # A detached actor is not equivalent to a registered roster binding.
        managers.by_identity[2] = deepcopy(fight.actors[2])
        recipes.remember(routing, 2, frozenset(), managers, view)
        self.assertNotIn(2, proofs.event_recipes)


if __name__ == "__main__":
    unittest.main()
