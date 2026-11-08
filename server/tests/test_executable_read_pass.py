"""Real native executable reads obtain a fresh proof inside suspended replay."""
import sys
import unittest
from contextlib import nullcontext
from dataclasses import replace
from unittest.mock import patch
import test_combat_ordinary_population_read_pass as fixture
from wakfu_server import combat_external_read_pass as external
from wakfu_server import combat_ordinary_events as events
from wakfu_server import combat_global_pv_collections as pv
from wakfu_server.combat_trove_long_map import NativeTroveLongMap


class ExecutableReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.OrdinaryPopulationReadPassTests.setUpClass()

    def exercise(self, enabled, mutate):
        base = fixture.OrdinaryPopulationReadPassTests()
        base.setUp()
        case = base.case
        calls, observations = [], []
        uid = 991
        invocation = replace(case.inv, base_uid=uid, caster_id=7, target_id=-7)
        rows = case.fight.native_owned_group_effects
        rows[uid] = {"invocation": {"target_id": -7}}
        self.assertTrue(external._plain_iteration(case.fight))
        if mutate:
            original_get = rows.get

            def mutating_get(key, default=None):
                observations.append(events._ordinary_phase_facts(case.fight) is None)
                pv.set_global_fighter_status(case.fight, -7, "OUT_OF_PLAY")
                return original_get(key, default)

            rows.get = mutating_get
            self.assertTrue(external._plain_iteration(case.fight))

        def observe(frame, event, arg):
            if event == "call" and frame.f_code is NativeTroveLongMap.__init__.__code__:
                calls.append(1)

        scope = (
            nullcontext()
            if enabled
            else patch.object(external, "external_read_pass", lambda *a: nullcontext())
        )
        previous = sys.getprofile()
        try:
            with scope, events._phase_read_pass(case.events, invocation):
                # The real replay deliberately suspends the outer proof.
                with case.events.replay._callback_read_boundary():
                    self.assertIsNone(events._ordinary_phase_facts(case.fight))
                    sys.setprofile(observe)
                    try:
                        result = (
                            "value",
                            case.events.executable(case.effect, invocation, None),
                        )
                    except ValueError as error:
                        result = ("error", str(error))
                    finally:
                        sys.setprofile(previous)
                self.assertIsNone(case.events.replay._read_pass.get("ordinary_facts"))
        finally:
            sys.setprofile(previous)
        return result, len(calls), observations

    def test_native_consumer_reuses_fresh_reads_and_mutating_getter_revokes(self):
        baseline, baseline_calls, _ = self.exercise(False, False)
        candidate, candidate_calls, _ = self.exercise(True, False)
        self.assertEqual(candidate, baseline)
        self.assertEqual(candidate[0], "value")
        self.assertLess(candidate_calls, baseline_calls)
        old, _, old_observations = self.exercise(False, True)
        new, _, new_observations = self.exercise(True, True)
        self.assertEqual(new, old)
        self.assertEqual(old_observations, [True])
        self.assertEqual(new_observations, [True])
        print(
            {
                "actual_executable_constructors": [baseline_calls, candidate_calls],
                "mutating_getter": new,
            }
        )
