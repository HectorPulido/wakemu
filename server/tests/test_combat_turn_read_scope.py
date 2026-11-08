"""Turn fanout reuses reads only across certified callback-free recipients."""
from copy import deepcopy
from contextlib import contextmanager, nullcontext
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_combat_ordinary_phase_read_pass as fixtures
from wakfu_server import combat_turn_boundary as candidate
from wakfu_server import combat_external_event_removal as removal
from wakfu_server import combat_ordinary_events as ordinary
from wakfu_server.combat_event_replay import NativeEventReplay


@contextmanager
def without_read_reuse(dispatcher, fight, plan, authority):
    # Exercise the same public delivery with its optimization disabled. The
    # legacy per-recipient reads remain the behavioral comparison authority.
    with ordinary._fallback_phase_read_pass(None):
        yield lambda identity: nullcontext()


class TurnReadScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.PhaseReadPassSemanticTests.setUpClass()

    def run_case(self, enabled, scenario="empty"):
        case = fixtures.PhaseReadPassSemanticTests().fixture()
        dispatcher = case.f.dispatcher
        dispatcher.native_retention = case.retention
        dispatcher.replay_event = case.replay
        dispatcher.native_clone_authority = case.events.authority
        original_authority = case.events.authority
        masks = [None] * 7
        if scenario == "callback":
            masks[5] = [1002]
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = masks
        phase, event = ("start", 1001) if scenario == "authority" else ("end", 1002)
        recipients = ((7, 6), (7, 60), (7, 61), (-7, 61))
        observed, iterations, authority_seen = [], [], []

        def activation(invocation, **kwargs):
            observed.append((invocation.reference, invocation.target_id))
            self.assertIsNone(case.replay._read_pass)
            case.fight.native_owned_group_effects[900]["target_id"] = 999999
            return False

        dispatcher.execute_activation = activation
        if scenario == "iterator":

            class Recipients:
                def __iter__(inner):
                    iterations.append("start")
                    self.assertIsNone(case.replay._read_pass)
                    yield recipients[0]
                    self.assertIsNone(case.replay._read_pass)
                    case.fight.native_owned_group_effects[900]["target_id"] = 999999
                    yield from recipients[1:]

            selected_recipients = Recipients()
        else:
            selected_recipients = recipients
        plan = candidate.TurnBoundaryPlan(
            7, case.fight.turn_id, phase, event, False, selected_recipients
        )

        def interest(actual, event_id):
            self.assertIs(actual, dispatcher)
            self.assertIsNone(case.replay._read_pass)
            if scenario == "authority":
                new_authority = replace(original_authority)
                dispatcher.native_clone_authority = new_authority
                case.events.authority = new_authority
                return True
            return False

        original_call = NativeEventReplay.__call__

        def observe(replay, source, **options):
            if source.channel in (4, 40, 41):
                self.assertIsNone(replay._read_pass)
                self.assertIs(options["authority"], original_authority)
                authority_seen.append(source.channel)
            return original_call(replay, source, **options)

        failure = None
        result = None
        with patch.object(
            case.retention, "view", wraps=case.retention.view
        ) as view, patch.object(
            removal, "has_removal_subscription", side_effect=interest
        ), patch.object(
            NativeEventReplay, "__call__", observe
        ):
            try:
                scope = (
                    nullcontext()
                    if enabled
                    else patch.object(candidate, "_turn_read_scope", without_read_reuse)
                )
                with scope:
                    result = candidate.execute_turn_delivery(dispatcher, plan)
            except (ValueError, KeyError) as error:
                failure = type(error).__name__, str(error)
        self.assertIsNone(case.replay._read_pass)
        self.assertEqual((), ordinary._PHASE_READ_SCOPES.get())
        return (
            dict(
                result=result,
                failure=failure,
                observed=observed,
                iterations=iterations,
                authority_seen=authority_seen,
                owned=deepcopy(case.fight.native_owned_group_effects),
                deliveries=deepcopy(
                    getattr(case.fight, "native_turn_event_deliveries", {})
                ),
                packets=tuple(case.f.packets),
            ),
            view.call_count,
        )

    def test_callback_free_recipients_reuse_one_view_with_identical_result(self):
        old, old_views = self.run_case(False)
        new, new_views = self.run_case(True)
        self.assertIsNone(new["failure"])
        self.assertEqual(old, new)
        self.assertGreater(old_views, 1)
        self.assertEqual(1, new_views)

    def test_selected_callback_invalidates_before_next_recipient(self):
        old, _ = self.run_case(False, "callback")
        new, _ = self.run_case(True, "callback")
        self.assertTrue(new["observed"])
        self.assertIsNotNone(new["failure"])
        self.assertEqual(old, new)

    def test_custom_recipient_iterator_is_not_preconsumed_or_given_cached_state(self):
        old, _ = self.run_case(False, "iterator")
        new, _ = self.run_case(True, "iterator")
        self.assertEqual(["start"], new["iterations"])
        self.assertIsNotNone(new["failure"])
        self.assertEqual(old, new)

    def test_exact_dispatcher_custom_getter_is_not_inspected_by_scope(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        dispatcher = object.__new__(EffectDispatcher)
        authority = object()
        dispatcher.native_clone_authority = authority
        plan = candidate.TurnBoundaryPlan(7, 1, "end", 1002, False, ((7, 6),))
        reads = []

        def custom_getter(self, name):
            reads.append(name)
            return object.__getattribute__(self, name)

        with patch.object(EffectDispatcher, "__getattribute__", custom_getter):
            with candidate._turn_read_scope(
                dispatcher, object(), plan, authority
            ) as recipient:
                with recipient(7):
                    pass
        self.assertEqual([], reads)

    def test_replaced_authority_before_removal_keeps_original_argument_without_scope(
        self,
    ):
        old, _ = self.run_case(False, "authority")
        new, _ = self.run_case(True, "authority")
        self.assertTrue(new["authority_seen"])
        self.assertEqual(old, new)


if __name__ == "__main__":
    unittest.main()
