"""Immediate native removal ownership and legacy evaluation ordering."""
import gc
import sys
import weakref
from types import SimpleNamespace
import unittest
from test_combat_event_replay import NativeEventReplayTests
from wakfu_server.combat_retained_effects import NativeRetainedRemoval
from wakfu_server.combat_retained_runtime import remove_now


class NativeRemovalScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        NativeEventReplayTests.setUpClass()

    def test_native_handle_release_and_captured_provider_uid_evaluation(self):
        case = NativeEventReplayTests()
        case.setUp()
        view = case.retention.view()
        references = []
        init_code = NativeRetainedRemoval.__init__.__code__

        def profile(frame, event, arg):
            if event == "return" and frame.f_code is init_code:
                references.append(weakref.ref(frame.f_locals["self"]))

        old_profile = sys.getprofile()
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            sys.setprofile(profile)
            result = remove_now(case.retention, view, (900,))
            sys.setprofile(old_profile)
            self.assertEqual([entry.uid for entry in result], [900])
            self.assertNotIn(900, case.fight.native_owned_group_effects)
            self.assertEqual(len(references), 1)
            self.assertIsNone(references[0]())
        finally:
            sys.setprofile(old_profile)
            if was_enabled:
                gc.enable()
        events = []

        class CustomRemoval:
            def remove(self, uids):
                self_test.assertIs(type(uids), tuple)
                events.append("remove")
                return uids

        self_test = self
        marker = object()

        def provider(value):
            self.assertIs(value, marker)
            events.append("provider")
            return CustomRemoval()

        def forbidden(value):
            self.fail(
                "replacement provider must not override already evaluated callable"
            )

        retention = SimpleNamespace(removal=provider)

        def changing_view():
            events.append("view")
            retention.removal = forbidden
            return marker

        def uids():
            events.append("iterate")
            yield 11
            yield 12

        captured = retention.removal
        value = changing_view()
        self.assertEqual(
            remove_now(
                retention, value, uids(), _provider=captured, _snapshot_uids=True
            ),
            (11, 12),
        )
        self.assertEqual(events, ["view", "provider", "iterate", "remove"])
        # A supplied None is distinct from an omitted callable: preserve TypeError.
        retention.removal = provider
        with self.assertRaises(TypeError):
            remove_now(retention, marker, (), _provider=None)
        self.assertEqual(events, ["view", "provider", "iterate", "remove"])


if __name__ == "__main__":
    unittest.main()
