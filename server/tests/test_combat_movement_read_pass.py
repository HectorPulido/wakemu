"""Isolated differential tests for public voluntary movement delivery."""
from contextlib import nullcontext
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_combat_ordinary_phase_read_pass as phase_fixture
from wakfu_server import combat_external_read_pass as external
from wakfu_server import combat_ordinary_events as ordinary
from wakfu_server import combat_voluntary_movement_events as movement


class MovementReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        phase_fixture.PhaseReadPassSemanticTests.setUpClass()

    def fixture(self):
        case = phase_fixture.PhaseReadPassSemanticTests().fixture()
        case.dispatcher = case.f.dispatcher
        case.dispatcher.native_retention = case.retention
        case.dispatcher.replay_event = case.replay
        case.dispatcher.native_clone_authority = case.events.authority
        return case

    def deliver(self, case):
        destination = case.fight.actors[7].position
        origin = next(
            cell
            for cell in sorted(case.fight.walkable)
            if cell[2] == destination[2]
            and abs(cell[0] - destination[0]) + abs(cell[1] - destination[1]) == 1
        )
        return movement.deliver_voluntary_movement(
            case.dispatcher,
            actor_id=7,
            from_cell=origin,
            to_cell=destination,
            action_id=12,
        )

    def run_case(self, *, enabled, mutation=None):
        case = self.fixture()
        masks = [None] * 7
        if mutation is not None:
            masks[5] = [1005]
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = masks
        observed = []
        custom_calls = []

        def activation(invocation, **kwargs):
            observed.append(
                (invocation.reference, invocation.caster_id, invocation.target_id)
            )
            self.assertIsNone(case.replay._read_pass)
            if mutation == "ownership":
                case.fight.native_owned_group_effects[900]["target_id"] = 999999
            elif mutation == "replace_replay":

                def replacement(source, **options):
                    self.assertIsNone(case.replay._read_pass)
                    custom_calls.append((source.manager_actor_id, source.channel))
                    return ()

                case.dispatcher.replay_event = replacement
            return False

        case.dispatcher.execute_activation = activation
        scope = (
            nullcontext()
            if enabled
            else patch.object(
                external, "external_read_pass", side_effect=lambda *args: nullcontext()
            )
        )
        failure = None
        result = None
        with patch.object(case.retention, "view", wraps=case.retention.view) as view:
            try:
                with scope:
                    result = self.deliver(case)
            except (ValueError, KeyError) as error:
                failure = type(error).__name__, str(error)
        self.assertIsNone(case.replay._read_pass)
        self.assertEqual(ordinary._PHASE_READ_SCOPES.get(), ())
        return (
            dict(
                result=result,
                failure=failure,
                observed=observed,
                custom_calls=custom_calls,
                packets=tuple(case.f.packets),
                owned=deepcopy(case.fight.native_owned_group_effects),
            ),
            view.call_count,
        )

    def test_empty_fanout_reuses_one_view_with_identical_result(self):
        baseline, baseline_views = self.run_case(enabled=False)
        candidate, candidate_views = self.run_case(enabled=True)
        self.assertIsNone(baseline["failure"], baseline["failure"])
        self.assertIsNone(candidate["failure"], candidate["failure"])
        self.assertEqual(candidate, baseline)
        self.assertGreater(baseline_views, 1)
        self.assertEqual(candidate_views, 1)

    def test_clone_mutation_revalidates_before_next_recipient(self):
        baseline, _ = self.run_case(enabled=False, mutation="ownership")
        candidate, _ = self.run_case(enabled=True, mutation="ownership")
        self.assertTrue(candidate["observed"])
        self.assertIsNotNone(candidate["failure"])
        self.assertEqual(candidate, baseline)

    def test_callback_replaces_replay_without_leaking_native_scope(self):
        baseline, _ = self.run_case(enabled=False, mutation="replace_replay")
        candidate, _ = self.run_case(enabled=True, mutation="replace_replay")
        self.assertTrue(candidate["observed"])
        self.assertTrue(candidate["custom_calls"])
        self.assertEqual(candidate, baseline)

    def test_opaque_nonfighter_boundary_revokes_population_before_mutation(self):
        case = self.fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        source = case.f.source()
        # Exercise the shared helper's opaque-PV fallback: an unknown area
        # cannot receive the fighter-only pure-recipient exemption. No fake
        # area authority is installed and this is not an area-admission test.
        with movement._movement_read_scope(case.dispatcher, case.fight, ()) as boundary:
            case.replay(source, authority=case.events.authority)
            self.assertIsNotNone(case.replay._read_pass["view"])
            with boundary(901):
                self.assertIsNone(case.replay._read_pass)
                case.fight.native_owned_group_effects[900]["target_id"] = 999999
            self.assertIsNone(case.replay._read_pass["view"])
            with self.assertRaises((ValueError, KeyError)):
                case.replay(source, authority=case.events.authority)
        self.assertIsNone(case.replay._read_pass)


if __name__ == "__main__":
    unittest.main()
