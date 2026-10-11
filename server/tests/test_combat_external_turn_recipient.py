"""Qualified server turn policy preserves the native null-source contract."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from wakfu_server.combat.combat_event_replay import (
    NativeExternalEvent,
    NativeEventSource,
)
from wakfu_server.combat.combat_external_turn_recipient import (
    external_turn_recipient,
    owned_turn_recipient_scope,
)
from wakfu_server.combat.combat_turn_events import TURN_BOUNDARY_POLICY


class ExternalTurnRecipientTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(id=-7)
        fight = SimpleNamespace(
            phase="active", current=actor, turn_id=9, actors={-7: actor}
        )
        context = dict(
            policy=TURN_BOUNDARY_POLICY,
            actor_id=-7,
            turn_id=9,
            phase="regeneration",
            event_id=1037,
        )
        return (
            fight,
            context,
            NativeExternalEvent(7, (1037,), 61, turn_boundary_context=context),
        )

    def test_actual_publication_rebinds_only_target_five_and_preserves_null_source(
        self,
    ):
        fight, context, source = self.fixture()
        with owned_turn_recipient_scope(fight, context):
            self.assertEqual(
                external_turn_recipient(
                    fight, source, target_code=5, original_target=7
                ),
                -7,
            )
            for code in range(5):
                self.assertEqual(
                    external_turn_recipient(
                        fight, source, target_code=code, original_target=7
                    ),
                    7,
                )
        self.assertIsNone(source.uid)
        self.assertIsNone(source.caster_id)
        self.assertIsNone(source.target_id)
        self.assertFalse(hasattr(fight, "_wakemu_owned_turn_recipient_scope"))

    def test_forged_copied_stale_mismatched_context_rejected(self):
        fight, context, source = self.fixture()
        with self.assertRaisesRegex(ValueError, "Unattested"):
            external_turn_recipient(fight, source, target_code=5, original_target=7)
        with owned_turn_recipient_scope(fight, context):
            with self.assertRaisesRegex(ValueError, "Unattested"):
                external_turn_recipient(
                    fight,
                    replace(source, turn_boundary_context=dict(context)),
                    target_code=5,
                    original_target=7,
                )
            with self.assertRaisesRegex(ValueError, "event mismatch"):
                external_turn_recipient(
                    fight,
                    replace(source, event_ids=(1001,)),
                    target_code=5,
                    original_target=7,
                )
            fight.turn_id += 1
            with self.assertRaisesRegex(ValueError, "active turn"):
                external_turn_recipient(fight, source, target_code=5, original_target=7)

    def test_scope_cleans_up_after_exception_and_unqualified_sources_unchanged(self):
        fight, context, source = self.fixture()
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with owned_turn_recipient_scope(fight, context):
                raise RuntimeError("abort")
        self.assertFalse(hasattr(fight, "_wakemu_owned_turn_recipient_scope"))
        bare = NativeExternalEvent(7, (1037,), 61)
        self.assertEqual(
            external_turn_recipient(fight, bare, target_code=5, original_target=7), 7
        )
        native = NativeEventSource(
            1, 2, 0, 7, -7, (0, 0, 0), (2,), 3, 7, None, False, False, False, True
        )
        self.assertEqual(
            external_turn_recipient(fight, native, target_code=5, original_target=-7),
            -7,
        )
