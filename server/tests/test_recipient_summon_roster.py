"""Ordinary event recipients retain local validation beside summon history."""
import unittest
import sys
from test_recipient_projection import EventRecipientProjectionTests
from wakfu_server import combat_summon as module
from wakfu_server.combat_controller_registry import (
    initialize_controller_registry,
    register_native_controller,
)
from wakfu_server.combat_ordinary_events import _phase_read_pass


class SummonRosterRecipientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        EventRecipientProjectionTests.setUpClass()

    def test_filtered_ordinary_projection_retains_registration_and_callback_guards(
        self,
    ):
        fixture = EventRecipientProjectionTests()
        fixture.setUp()
        fight, ordinary, authority = fixture.fight, fixture.ordinary, fixture.authority
        initialize_controller_registry(fight)
        for identity, actor in fight.actors.items():
            register_native_controller(
                fight, identity, team=actor.team, controller_id=identity
            )
        view_calls = []
        view_code = module._EVENT_RECIPIENT_VIEW.__code__

        def observe(frame, event, arg):
            if event == "call" and frame.f_code is view_code:
                view_calls.append(True)

        prior_profile = sys.getprofile()
        sys.setprofile(observe)
        try:
            self.assertTrue(
                module._project_event_recipient(authority, fight, fight.actors[-7])
            )
        finally:
            sys.setprofile(prior_profile)
        self.assertEqual(
            view_calls, [], "Empty summon roster must not copy the ordinary view"
        )
        summon = fixture._register_summon()
        npc = fight.actors[-7]
        # Both live and retained historical registrations use the same strict
        # filtered ordinary roster. Never reconstruct unused spellbook data.
        for retired in (False, True):
            fight.native_summon_registrations[summon.id]["retired"] = retired
            self.assertTrue(module._project_event_recipient(authority, fight, npc))
            ordinary.monsters[-7]["native_spellbook"] = object()
            with self.assertRaises(ValueError):
                module._EVENT_RECIPIENT_CALL(
                    authority, fight, npc, _include_summon_counts=False
                )
            self.assertIsNone(module.verify_event_recipient(authority, fight, npc))
            ordinary.monsters[-7].pop("native_spellbook")
        case = fixture.case.case
        with _phase_read_pass(case.events, case.inv):
            module.verify_event_recipient(authority, fight, npc)
            with case.events.replay._callback_read_boundary():
                fight.native_summon_registrations[summon.id]["actor_id"] = -999
            with self.assertRaisesRegex(ValueError, "Stale summon roster"):
                module.verify_event_recipient(authority, fight, npc)
            with case.events.replay._callback_read_boundary():
                fight.native_summon_registrations[summon.id]["actor_id"] = summon.id
            module.verify_event_recipient(authority, fight, npc)
        # Replaced native methods stay on the complete custom fallback path.
        calls = []
        original = authority._ordinary_view

        def custom_view(preview, **kwargs):
            calls.append("custom")
            return original(preview, **kwargs)

        authority._ordinary_view = custom_view
        self.assertFalse(module._project_event_recipient(authority, fight, npc))
        module.verify_event_recipient(authority, fight, npc)
        self.assertTrue(calls)


if __name__ == "__main__":
    unittest.main()
