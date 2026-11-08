"""Native nonempty selection preserves removal order and atomic validation."""
from dataclasses import replace
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_combat_event_replay import NativeEventReplayTests
from wakfu_server.combat_dispel import NativeDispelHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_movement_link import NativeMovementLinkHandler
from wakfu_server.combat_stat_handler import StatExecutionContext


class NativeLocalDispelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        NativeEventReplayTests.setUpClass()

    def fixture(self, link=False):
        case = NativeEventReplayTests()
        case.setUp()
        if link:
            definition = case.retention.view().by_uid[900]
            handler = NativeMovementLinkHandler(
                case.fight,
                case.packets,
                action_id=1,
                allocate_uid=lambda: 901,
                context=lambda *args: StatExecutionContext(
                    True, True, None, True, None
                ),
                authority=SimpleNamespace(property_counts=lambda *args: {}),
            )
            handler(
                dict(effect_class=802, native_effect_flags=[]),
                dict(parameters=[]),
                EffectInvocation(123, 1, 7, -7, (1, 0, 0)),
            )
            case.retention.record(
                replace(
                    definition,
                    uid=901,
                    effect_class=802,
                    generic_effect=123,
                    target_id=-7,
                    manager_id=-7,
                )
            )
        return case, NativeDispelHandler(
            view_provider=case.retention.view, removal_provider=case.retention.removal
        )

    def test_native_nonempty_counter_manager_and_validation_before_mutation(self):
        for link in (False, True):
            results, counts = [], []
            for enabled in (False, True):
                case, handler = self.fixture(link)
                invocation = EffectInvocation(
                    145261, 1, 7, -7 if link else 7, (0, 0, 0)
                )
                calls = []
                code = type(case.retention).view.__code__

                def profile(frame, event, arg):
                    if event == "call" and frame.f_code is code:
                        calls.append(1)

                old = sys.getprofile()
                from contextlib import nullcontext

                gate = (
                    nullcontext()
                    if enabled
                    else patch.object(
                        NativeDispelHandler, "_native_selection", return_value=None
                    )
                )
                try:
                    with gate:
                        sys.setprofile(profile)
                        handler._apply(
                            {"parameters": [123 if link else 308265]}, invocation
                        )
                finally:
                    sys.setprofile(old)
                results.append((tuple(case.packets), source_snapshot(case.fight)))
                counts.append(len(calls))
                self.assertNotIn(900, case.fight.native_owned_group_effects)
                if link:
                    self.assertNotIn(901, case.fight.owned_stat_effects)
                    self.assertEqual(case.fight.native_movement_links, {})
            self.assertEqual(*results)
            self.assertEqual(counts, [1, 0])
        # Bad reciprocal-manager metadata must reject before removing either UID.
        case, handler = self.fixture(True)
        case.fight.native_retained_records[900]["generic_effect"] = 987654
        before = (tuple(case.packets), source_snapshot(case.fight))
        with self.assertRaises(ValueError):
            handler._apply(
                {"parameters": [123]}, EffectInvocation(145261, 1, 7, -7, (0, 0, 0))
            )
        self.assertEqual(before, (tuple(case.packets), source_snapshot(case.fight)))
        self.assertIn(900, case.fight.native_owned_group_effects)
        self.assertIn(901, case.fight.owned_stat_effects)
        # Post-removal liveness may outlast an already-pruned area manager.
        # Absent wire ownership must return False before resolving that manager.
        from wakfu_server.combat_retained_removal_query import NativeRetainedRemovalView

        case, handler = self.fixture()
        carrier = replace(
            case.retention.view().by_uid[900],
            uid=9999,
            effect_class=310,
            target_id=777,
            manager_id=777,
        )
        removal = case.retention.removal(
            NativeRetainedRemovalView(case.fight, (carrier,))
        )
        self.assertIs(removal.families[310][0](9999), False)
        # Fully registered native callbacks must not close back over removal.
        import gc
        import weakref

        case, handler = self.fixture()
        from wakfu_server.combat_retained_removal_query import removal_view

        selected = case.retention.view().by_uid[900]
        view = removal_view(case.retention, (selected,))
        self.assertIsNotNone(view)
        was_enabled = gc.isenabled()
        gc.disable()
        try:

            def registered_lifetime():
                operation = case.retention.removal(view)
                reference = weakref.ref(operation)
                self.assertEqual([entry.uid for entry in operation.plan((900,))], [900])
                return reference

            reference = registered_lifetime()
            self.assertIsNone(reference())
        finally:
            if was_enabled:
                gc.enable()
        # Direct callers retain the legacy dynamically replaceable view contract.
        import struct
        from wakfu_server.combat_retained_effects import (
            NativeRetainedRemoval,
            register_owned_removals,
        )

        case, handler = self.fixture(True)
        link = case.retention.view().by_uid[901]
        old_view = NativeRetainedRemovalView(case.fight, (link,))
        operation = NativeRetainedRemoval(old_view)
        register_owned_removals(
            operation,
            stat_handler=case.retention.stat_handler,
            packets=case.packets,
            action_id=1,
        )
        operation.view = NativeRetainedRemovalView(
            case.fight, (replace(link, manager_id=7),)
        )
        operation.remove((901,))
        self.assertEqual(struct.unpack(">qq", case.packets[-1][1][-16:]), (7, 901))
        # A custom stat-removal method keeps full validation before its callback.
        from contextlib import nullcontext

        for class_override in (False, True):
            case, handler = self.fixture(True)
            order = []
            original_remove = type(case.retention.stat_handler).remove

            def custom_remove(stat, uid):
                order.append("remove")
                return original_remove(stat, uid)

            if class_override:
                gate = patch.object(
                    type(case.retention.stat_handler), "remove", custom_remove
                )
            else:
                case.retention.stat_handler.remove = lambda uid: custom_remove(
                    case.retention.stat_handler, uid
                )
                gate = nullcontext()
            view_code = type(case.retention).view.__code__

            def profile(frame, event, arg):
                if event == "call" and frame.f_code is view_code:
                    order.append("view")

            old_profile = sys.getprofile()
            try:
                with gate:
                    sys.setprofile(profile)
                    handler._apply(
                        {"parameters": [123]},
                        EffectInvocation(145261, 1, 7, -7, (0, 0, 0)),
                    )
            finally:
                sys.setprofile(old_profile)
            self.assertEqual(order, ["view", "remove"])
        # Custom view provider keeps the full path and its observable call order.
        case, handler = self.fixture()
        seen = []
        original = handler.view_provider
        handler.view_provider = lambda: (seen.append("view"), original())[1]
        handler._apply(
            {"parameters": [308265]}, EffectInvocation(145261, 1, 7, 7, (0, 0, 0))
        )
        self.assertEqual(seen, ["view"])
        self.assertNotIn(900, case.fight.native_owned_group_effects)


if __name__ == "__main__":
    unittest.main()
