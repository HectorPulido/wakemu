"""Committed movement provenance is actor-specific and does not invent a Qe."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from wakfu_server.combat.combat_event_replay import NativeExternalEvent
from wakfu_server.combat.combat_external_movement_recipient import (
    POLICY,
    committed_movement_recipient_scope,
)
from wakfu_server.combat.combat_external_turn_recipient import (
    external_movement_recipient,
    qualified_boundary_actor,
)


class ExternalMovementRecipientTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(id=-7, position=(1, 0, 0))
        fight = SimpleNamespace(
            phase="active",
            current=actor,
            turn_id=8,
            actors={-7: actor},
            walkable={(0, 0, 0), (1, 0, 0)},
            edges={((0, 0, 0), (1, 0, 0))},
        )
        context = dict(
            policy=POLICY,
            actor_id=-7,
            turn_id=8,
            action_id=12,
            from_cell=(0, 0, 0),
            to_cell=(1, 0, 0),
            event_id=1005,
        )
        source = NativeExternalEvent(7, (1005,), 61, movement_boundary_context=context)
        return fight, context, source

    def test_actual_committed_npc_step_rebinds_only_target_five(self):
        fight, context, source = self.fixture()
        source.validate()
        with committed_movement_recipient_scope(fight, context):
            self.assertEqual(
                external_movement_recipient(
                    fight, source, target_code=5, original_target=7
                ),
                -7,
            )
            self.assertIs(
                qualified_boundary_actor(fight, movement_context=context),
                fight.actors[-7],
            )
            for code in range(5):
                self.assertEqual(
                    external_movement_recipient(
                        fight, source, target_code=code, original_target=7
                    ),
                    7,
                )
        self.assertIsNone(source.uid)
        self.assertIsNone(source.target_id)
        self.assertIsNone(source.caster_id)
        self.assertFalse(hasattr(fight, "_wakemu_committed_movement_recipient_scope"))

    def test_forged_copied_stale_wrong_position_and_edge_rejected(self):
        fight, context, source = self.fixture()
        with self.assertRaisesRegex(ValueError, "Unattested"):
            external_movement_recipient(fight, source, target_code=5, original_target=7)
        with committed_movement_recipient_scope(fight, context):
            with self.assertRaisesRegex(ValueError, "Unattested"):
                external_movement_recipient(
                    fight,
                    replace(source, movement_boundary_context=dict(context)),
                    target_code=5,
                    original_target=7,
                )
            fight.turn_id += 1
            with self.assertRaisesRegex(ValueError, "actual participant"):
                qualified_boundary_actor(fight, movement_context=context)
            fight.turn_id -= 1
            fight.actors[-7].position = (0, 0, 0)
            with self.assertRaisesRegex(ValueError, "actual participant"):
                qualified_boundary_actor(fight, movement_context=context)
        fight.actors[-7].position = (1, 0, 0)
        fight.edges = set()
        with self.assertRaisesRegex(ValueError, "terrain edge"):
            with committed_movement_recipient_scope(fight, context):
                pass

    def test_failed_publication_cleans_up_and_bare_events_keep_originals(self):
        fight, context, source = self.fixture()
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with committed_movement_recipient_scope(fight, context):
                raise RuntimeError("abort")
        self.assertFalse(hasattr(fight, "_wakemu_committed_movement_recipient_scope"))
        self.assertIsNone(qualified_boundary_actor(fight))
        self.assertEqual(
            external_movement_recipient(
                fight,
                NativeExternalEvent(7, (1005,), 61),
                target_code=5,
                original_target=7,
            ),
            7,
        )
        with self.assertRaisesRegex(ValueError, "boundary facts"):
            with committed_movement_recipient_scope(fight, dict(context, action_id=0)):
                pass
