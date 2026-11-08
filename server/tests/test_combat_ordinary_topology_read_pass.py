"""Candidate topology reuse preserves native probing and dynamic life state."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_combat_ordinary_population_read_pass as population_fixture
from wakfu_server import combat_global_pv_collections as pv
from wakfu_server import combat_ordinary_events as events
from wakfu_server.combat_trove_long_map import NativeTroveLongMap


class OrdinaryTopologyReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        population_fixture.OrdinaryPopulationReadPassTests.setUpClass()

    def setUp(self):
        self.base = population_fixture.OrdinaryPopulationReadPassTests()
        self.base.setUp()
        self.case = self.base.case
        self.fight = self.case.fight

    def facts(self):
        return pv._ordinary_fighter_topology(self.fight, pv._collections(self.fight))

    def test_order_membership_and_life_stay_correct_across_callback_and_rebinding(self):
        state = pv._collections(self.fight)
        expected = NativeTroveLongMap(state["fighters"]).order()
        with events._phase_read_pass(self.case.events, self.case.inv):
            first = self.facts()
            self.assertEqual(first, (expected, frozenset(expected)))
            for _ in range(20):
                self.assertIs(self.facts(), first)
                self.assertEqual(pv.ordinary_fighter_order(self.fight, state), expected)
                self.assertTrue(pv.global_fighter_guards(self.fight, 7)["baF"])
                self.assertFalse(
                    pv._ordinary_fighter_contains(self.fight, state, 999999)
                )
            self.fight.actors[7].hp = 1
            pv.set_global_fighter_status(self.fight, 7, "OFF_PLAY")
            self.assertTrue(pv.global_fighter_guards(self.fight, 7)["baG"])
            self.assertIs(self.facts(), first)  # Only topology was reused.
            with self.case.events.replay._callback_read_boundary():
                pv.set_global_fighter_status(self.fight, 7, "IN_PLAY")
                state["fighters"] = deepcopy(state["fighters"])
            second = self.facts()
            self.assertIsNot(second, first)
            self.assertTrue(pv.global_fighter_guards(self.fight, 7)["baF"])
            self.fight.native_global_pv_collections = deepcopy(state)
            self.assertIsNot(self.facts(), second)
        self.assertIsNone(self.facts())

    def test_unreachable_present_key_keeps_original_probing_failure(self):
        state = pv._collections(self.fight)
        topology = state["fighters"]
        original_slot = topology["keys"].index(7)
        free_slot = topology["states"].index(0)
        topology["keys"][free_slot] = 7
        topology["states"][free_slot] = 1
        topology["keys"][original_slot] = 0
        topology["states"][original_slot] = 0
        native = NativeTroveLongMap(topology)
        self.assertIn(7, native.order())
        self.assertFalse(native.contains(7))
        with events._phase_read_pass(self.case.events, self.case.inv):
            self.assertIsNone(self.facts())
            self.assertEqual(
                pv.ordinary_fighter_order(self.fight, state), native.order()
            )
            with self.assertRaisesRegex(ValueError, "fdy registration"):
                pv.global_fighter_guards(self.fight, 7)

    def test_no_free_slots_and_custom_provider_keep_uncached_contract(self):
        state = pv._collections(self.fight)
        topology = state["fighters"]
        capacity = len(topology["keys"])
        topology.update(
            keys=list(range(1, capacity + 1)),
            states=[1] * capacity,
            size=capacity,
            free=0,
        )
        expected = NativeTroveLongMap(topology).order()
        with events._phase_read_pass(self.case.events, self.case.inv):
            self.assertIsNone(self.facts())
            self.assertEqual(pv.ordinary_fighter_order(self.fight, state), expected)
        self.setUp()
        original = NativeTroveLongMap.order
        with events._phase_read_pass(self.case.events, self.case.inv):
            self.assertIsNotNone(self.facts())
            with patch.object(
                NativeTroveLongMap, "order", lambda instance: original(instance)
            ):
                self.assertIsNone(self.facts())
            with events._fallback_phase_read_pass(self.case.events):
                self.assertIsNone(self.facts())

    def test_custom_collection_does_not_add_getters_and_suspends_opaque_lookup(self):
        case = self

        class Collection(dict):
            get_calls = 0
            item_calls = 0

            def get(self, *args):
                self.get_calls += 1
                return super().get(*args)

            def __getitem__(self, key):
                self.item_calls += 1
                case.assertIsNone(events._ordinary_phase_facts(case.fight))
                return super().__getitem__(key)

        state = pv._collections(self.fight)
        custom = Collection(state)
        expected = NativeTroveLongMap(state["fighters"]).order()
        with events._phase_read_pass(self.case.events, self.case.inv):
            before = self.facts()
            self.assertIsNone(pv._ordinary_fighter_topology(self.fight, custom))
            self.assertEqual((custom.get_calls, custom.item_calls), (0, 0))
            self.assertEqual(pv.ordinary_fighter_order(self.fight, custom), expected)
            self.assertEqual((custom.get_calls, custom.item_calls), (0, 1))
            self.assertIsNot(self.facts(), before)

    def test_provider_override_mutation_then_restore_cannot_revive_old_proof(self):
        state = pv._collections(self.fight)
        baseline = NativeTroveLongMap(deepcopy(state["fighters"]))
        baseline.remove(7)
        expected = baseline.contains(7)
        original = NativeTroveLongMap.contains
        calls = []

        def overridden(native, identity):
            self.assertIsNone(events._ordinary_phase_facts(self.fight))
            calls.append(identity)
            native.remove(7)
            return original(native, identity)

        with events._phase_read_pass(self.case.events, self.case.inv):
            before = self.facts()
            with patch.object(NativeTroveLongMap, "contains", overridden):
                self.assertEqual(
                    pv._ordinary_fighter_contains(self.fight, state, 7), expected
                )
            self.assertEqual(calls, [7])
            self.assertEqual(
                pv._ordinary_fighter_contains(self.fight, state, 7), expected
            )
            self.assertIsNot(self.facts(), before)
            self.assertEqual(state["fighters"], baseline.state)
            with self.assertRaisesRegex(ValueError, "fdy registration"):
                pv.global_fighter_guards(self.fight, 7)

    def test_collection_override_is_suspended_before_reentrant_restoration(self):
        original = pv._collections
        calls = []

        def overridden(fight):
            calls.append(fight)
            self.assertIsNone(events._ordinary_phase_facts(fight))
            pv._collections = original
            self.assertIsNone(self.facts())
            NativeTroveLongMap(original(fight)["fighters"]).remove(7)
            return original(fight)

        with events._phase_read_pass(self.case.events, self.case.inv):
            before = self.facts()
            with patch.object(pv, "_collections", overridden):
                with self.assertRaisesRegex(ValueError, "fdy registration"):
                    pv.global_fighter_guards(self.fight, 7)
            self.assertEqual(calls, [self.fight])
            self.assertIsNot(self.facts(), before)
            self.assertNotIn(7, self.facts()[1])

    def test_custom_collection_getter_frequency_matches_original_consumer(self):
        case = self

        class Collection(dict):
            calls = 0

            def get(self, *args):
                self.calls += 1
                case.assertIsNone(events._ordinary_phase_facts(case.fight))
                return super().get(*args)

        custom = Collection(pv._collections(self.fight))
        self.fight.native_global_pv_collections = custom
        pv._collections(self.fight)
        expected = custom.calls
        custom.calls = 0
        with events._phase_read_pass(self.case.events, self.case.inv):
            self.assertTrue(pv.global_fighter_guards(self.fight, 7)["baF"])
        self.assertEqual(custom.calls, expected)

    def test_corrupt_topology_after_callback_is_not_hidden_by_prior_facts(self):
        with events._phase_read_pass(self.case.events, self.case.inv):
            self.assertIsNotNone(self.facts())
            with self.case.events.replay._callback_read_boundary():
                pv._collections(self.fight)["fighters"]["states"][0] = 9
            with self.assertRaisesRegex(ValueError, "Trove topology"):
                pv.global_fighter_guards(self.fight, 7)


if __name__ == "__main__":
    unittest.main()
