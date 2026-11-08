"""Selected views live only across real certified, callback-free phase reads."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import sys
import unittest
from unittest.mock import patch

from test_combat_ordinary_phase_read_pass import PhaseReadPassSemanticTests
from wakfu_server import combat_retained_query as query
from wakfu_server.combat_ordinary_events import _phase_read_pass
from wakfu_server.combat_event_replay import NativeEventReplay
from wakfu_server.combat_geometry_snapshot import source_snapshot


class ManagerReadPassCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        PhaseReadPassSemanticTests.setUpClass()

    def fixture(self):
        case = PhaseReadPassSemanticTests().fixture()
        case.fight.native_owned_group_effects[900]["native_subscription_masks"] = [
            None
        ] * 7
        return case

    def test_actual_phases_reuse_managers_and_all_callback_boundaries_revoke(self):
        for target in (7, -7):
            outputs = []
            counts = []
            for enabled in (False, True):
                case = self.fixture()
                invocation = replace(
                    case.inv, target_id=target, cell=case.fight.actors[target].position
                )
                calls = []
                code = query.manager_query.__code__

                def profile(frame, event, arg):
                    if event == "call" and frame.f_code is code:
                        calls.append(frame.f_locals["identity"])

                gate = (
                    nullcontext()
                    if enabled
                    else patch.object(
                        query.ReplayQueries,
                        "enable_read_pass_cache",
                        new=lambda self: None,
                    )
                )
                with gate:
                    sys.setprofile(profile)
                    try:
                        result = case.events.phase(
                            case.effect, invocation, uid=800, value=1, channel=3
                        )
                    finally:
                        sys.setprofile(None)
                self.assertIsNone(case.replay._read_pass)
                outputs.append(
                    (result, tuple(case.f.packets), source_snapshot(case.fight))
                )
                counts.append(calls)
            self.assertEqual(outputs[0], outputs[1])
            self.assertGreater(len(counts[0]), len(counts[1]), counts)
            self.assertGreater(len(counts[1]), 0)

        case = self.fixture()
        other = NativeEventReplay(case.f.dispatcher, case.retention)
        with _phase_read_pass(case.events, case.inv):
            first = case.replay._current_view(7)
            holder = case.replay._read_pass["view"]
            self.assertIs(type(holder), query.ReplayQueries)
            self.assertIs(type(holder.queries.routing), query.IndexedRouting)
            self.assertIs(case.replay._current_view(7), first)
            self.assertIn(900, first.by_uid)
            # Another replay's real callback boundary must suspend same-Fight views.
            with other._callback_read_boundary():
                self.assertIsNone(case.replay._read_pass)
                case.retention.remove_group(900)
            self.assertIsNone(case.replay._read_pass["view"])
            after = case.replay._current_view(7)
            self.assertIsNot(after, first)
            self.assertNotIn(900, after.by_uid)
            with _phase_read_pass(case.events, case.inv):
                nested = case.replay._current_view(7)
                self.assertIsNot(nested, after)
            self.assertIsNone(case.replay._read_pass["view"])
            self.assertIsNot(case.replay._current_view(7), after)
        self.assertIsNone(case.replay._read_pass)

        # No opt-in: repeated direct LocalQueries reads are always fresh.
        direct = query.LocalQueries(case.fight)
        self.assertIsNot(direct.for_manager(7), direct.for_manager(7))
        fallback = query.ReplayQueries(case.retention)
        fallback.enable_read_pass_cache()
        before = fallback.for_manager(7)
        self.assertTrue(fallback._manager_views)
        with patch.object(
            case.retention, "view", side_effect=ValueError("opaque failure")
        ):
            with self.assertRaisesRegex(ValueError, "opaque failure"):
                fallback.full_view()
        self.assertTrue(fallback._cache_manager_views)
        self.assertEqual(fallback._manager_views, {})
        self.assertIsNot(fallback.for_manager(7), before)
