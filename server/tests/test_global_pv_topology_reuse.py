import sys
import unittest
from copy import deepcopy
from unittest.mock import patch
import test_combat_ordinary_population_read_pass as fixture
from wakfu_server import combat_global_pv_collections as pv
from wakfu_server import combat_ordinary_events as events
from wakfu_server.combat_native_actor_lookup import native_actor_population
from wakfu_server.combat_trove_long_map import NativeTroveLongMap


class GlobalPVReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.OrdinaryPopulationReadPassTests.setUpClass()

    def test_actual_population_reuses_only_existing_proof_and_keeps_live_iterator(self):
        base = fixture.OrdinaryPopulationReadPassTests()
        base.setUp()
        case, fight = base.case, base.case.fight
        state = pv._collections(fight)
        calls = []

        def observe(frame, event, arg):
            if event == "call" and frame.f_code is NativeTroveLongMap.__init__.__code__:
                if frame.f_locals.get("state") is state["fighters"]:
                    calls.append(1)

        def population():
            previous = sys.getprofile()
            try:
                sys.setprofile(observe)
                return tuple(a.id for a in native_actor_population(fight))
            finally:
                sys.setprofile(previous)

        expected = population()
        self.assertEqual(len(calls), 1)
        calls.clear()
        with events._phase_read_pass(case.events, case.inv):
            self.assertEqual(population(), expected)  # No proof: original constructor.
            self.assertEqual(len(calls), 1)
            proof = pv._ordinary_fighter_topology(fight, state)
            calls.clear()
            for _ in range(4):
                self.assertEqual(population(), expected)
            self.assertEqual(len(calls), 0)
            pending = pv.global_pv_iterator(fight, caster_id=None)
            with case.events.replay._callback_read_boundary():
                pv.set_global_fighter_status(fight, expected[0], "OUT_OF_PLAY")
            self.assertEqual(tuple(pending), expected[1:])
            calls.clear()
            self.assertEqual(population(), expected[1:])
            self.assertEqual(len(calls), 1)  # Callback invalidated the proof.
            replacement = pv._ordinary_fighter_topology(fight, state)
            self.assertIsNot(replacement, proof)
            with case.events.replay._callback_read_boundary():
                state["fighters"] = deepcopy(state["fighters"])
                pv.set_global_fighter_status(fight, expected[0], "OFF_PLAY")
            self.assertEqual(population(), expected)
            original = NativeTroveLongMap.order
            with patch.object(
                NativeTroveLongMap, "order", lambda value: original(value)
            ):
                self.assertEqual(population(), expected)
                self.assertIsNone(pv._ordinary_fighter_topology(fight, state))
        print(
            "fighter constructor calls: cold=1, warmed actual population x4=0; packet population/order/live status preserved"
        )
