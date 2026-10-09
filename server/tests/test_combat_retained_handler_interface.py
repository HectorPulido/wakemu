from types import SimpleNamespace
import unittest
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_area_remove import NativeAreaRemovalHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation


class RetainedHandlerInterfaceTests(unittest.TestCase):
    def test_wrapped_native_runner_keeps_prepare_and_cleanup_owner(self):
        retention = object.__new__(NativeRetainedRuntime)
        for family in (843, 911):
            handler = NativeAreaRemovalHandler(
                SimpleNamespace(),
                [],
                action_id=1,
                allocate_uid=lambda: 55,
                context=lambda *args: None,
                container=lambda *args: None,
                rng=lambda: 0.5,
            )
            registered = retention.wrap(handler)
            self.assertIs(registered.prepare.__self__, handler)
            self.assertIs(registered.cancel_prepared.__self__, handler)
            invocation = EffectInvocation(300001, 1, 7, None, (0, 0, 0))
            prepared = registered.prepare(dict(effect_class=family), {}, invocation)
            self.assertEqual(prepared.native_running_uid, 55)
            self.assertIn(55, handler.prepared)
            registered.cancel_prepared(prepared)
            self.assertNotIn(55, handler.prepared)

    def test_plain_callable_keeps_its_original_narrow_interface(self):
        registered = object.__new__(NativeRetainedRuntime).wrap(lambda *args: False)
        self.assertFalse(hasattr(registered, "prepare"))
        self.assertFalse(hasattr(registered, "cancel_prepared"))
