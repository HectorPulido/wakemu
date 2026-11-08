"""Factory lifecycle backlinks preserve exact public authority methods."""
from copy import deepcopy
import gc
from types import SimpleNamespace, MethodType
import unittest
import weakref

from wakfu_server.combat_event_replay import NativeCloneAuthority
from wakfu_server.combat_cost_payment_events import NativeCostPaymentEvents
from wakfu_server.combat_breeze_payment_events import NativeBreezePaymentEvents
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_ordinary_events import (
    OrdinaryHealingEvents,
    OrdinaryDamageEvents,
    OrdinaryResourceLossEvents,
    OrdinaryArmorEvents,
    OrdinaryDisplacementEvents,
    bind_factory_event_authority,
)


class Preview:
    pass


class NativeEventAuthorityLifetimeTests(unittest.TestCase):
    def events(self, cls=OrdinaryHealingEvents):
        return cls(
            adapter=SimpleNamespace(
                actor_authority=OrdinaryActorAuthority.__new__(OrdinaryActorAuthority)
            ),
            preview=Preview(),
            plan=None,
            replay=None,
            retention=None,
        )

    def test_factory_methods_identity_copy_release_and_standalone_contract(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            for cls in (
                OrdinaryHealingEvents,
                OrdinaryDamageEvents,
                OrdinaryResourceLossEvents,
                OrdinaryArmorEvents,
                OrdinaryDisplacementEvents,
                NativeCostPaymentEvents,
                NativeBreezePaymentEvents,
            ):
                with self.subTest(kind=cls.__name__):
                    events = self.events(cls)
                    authority = events.authority
                    bind_factory_event_authority(events)
                    self.assertIs(events.authority, authority)
                    self.assertIs(type(authority), NativeCloneAuthority)
                    self.assertIs(type(authority.executable), MethodType)
                    self.assertIs(authority.executable.__self__, events)
                    self.assertIs(
                        authority.executable.__func__, OrdinaryHealingEvents.executable
                    )
                    self.assertIs(authority.condition_context.__self__, events)
                    self.assertIs(
                        authority.condition_context.__func__,
                        OrdinaryHealingEvents.conditions,
                    )
                    copied = deepcopy(events)
                    self.assertIs(copied.authority.executable.__self__, copied)
                    self.assertIs(copied.authority.condition_context.__self__, copied)
                    copied_ref = weakref.ref(copied)
                    del copied
                    self.assertIsNone(copied_ref())
                    independent = deepcopy(authority)
                    self.assertIs(
                        independent.executable.__self__.authority, independent
                    )
                    events_ref, preview_ref = weakref.ref(events), weakref.ref(
                        events.preview
                    )
                    del independent, events, authority
                    self.assertIsNone(events_ref())
                    self.assertIsNone(preview_ref())

            standalone = self.events()
            authority = standalone.authority
            reference = weakref.ref(standalone)
            del standalone
            self.assertIs(authority.executable.__self__, reference())
            self.assertIsNotNone(reference())

            # A replacement/custom callback is neither wrapped nor certified.
            events = self.events()
            callback = lambda *args: False
            events.authority = NativeCloneAuthority(callback, callback)
            bind_factory_event_authority(events)
            self.assertIs(events.authority.executable, callback)
            self.assertFalse(events.authority.executable())
        finally:
            if enabled:
                gc.enable()


if __name__ == "__main__":
    unittest.main()
