"""Execute actual World delivery with superseded committed wakeups and fences."""

from types import SimpleNamespace
from contextlib import nullcontext
import time
import unittest
from unittest.mock import Mock, patch

from test_dungeon_recovery_callers import caller
from wakfu_server import rift_transition_delivery
from wakfu_server.position_buffer import PositionBaselineChanged


class RiftTransitionRecoveryCallerTests(unittest.TestCase):
    def setUp(self):
        self.account_id = 17001
        self.generation = "rift-recovery-caller"
        self.actor_id = 17002
        self.member = dict(
            account_id=self.account_id,
            generation=self.generation,
            id=self.actor_id,
            selected_character_id=self.actor_id,
        )
        self.old = dict(
            id=self.actor_id, map_id=527, instance_id=0, x=1, y=2, z=0, direction=3
        )
        self.first = dict(map_id=1280, instance_id=19001, x=5, y=6, z=0)
        self.latest = dict(map_id=527, instance_id=0, x=8, y=9, z=0)
        self.addCleanup(
            rift_transition_delivery.supersede_recovered_sessions,
            (
                SimpleNamespace(
                    account_id=self.account_id,
                    generation=self.generation,
                    character_id=self.actor_id,
                ),
            ),
        )

    def delivery(self):
        namespace = dict(
            INITIAL_character=self.old,
            INITIAL_position=dict(x=1, y=2, z=0),
            INITIAL_movement_state=None,
            loaded=True,
            account_id=self.account_id,
            generation=self.generation,
            fight=None,
            combat_session=None,
            consume_rift_entry_combat_retirement=Mock(),
            STORE=Mock(current_character_session=Mock(return_value=True)),
            prepare_world_respawn_delivery=Mock(return_value=True),
            cancel_crafting=Mock(),
            WORLD=Mock(),
            POSITIONS=Mock(),
            Movement=Mock(),
            owned_native_bootstrap=Mock(return_value=((13256, b"scene"),)),
            send=Mock(),
            connection=object(),
            service="world",
            join_world=Mock(),
            mark_static_sync_pending=Mock(),
            record=Mock(),
        )
        namespace[
            "POSITIONS"
        ].account_barrier.side_effect = lambda *args, **kwargs: nullcontext()
        return caller("deliver_rift_transition", namespace), namespace

    def test_newer_committed_wakeup_retries_without_disconnecting_or_consuming_it(self):
        deliver, ns = self.delivery()
        rift_transition_delivery.queue((self.member,), self.first)

        def superseding_character(*args):
            # Another valid party worker committed its newer transition after
            # pending() returned the earlier wakeup. No lease replacement.
            rift_transition_delivery.queue((self.member,), self.latest)
            return dict(self.old, **self.latest)

        ns["STORE"].character.side_effect = superseding_character
        self.assertFalse(deliver())
        ns["WORLD"].leave.assert_not_called()
        ns["POSITIONS"].attach.assert_not_called()
        ns["send"].assert_not_called()
        self.assertEqual(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            ),
            self.latest,
        )
        ns["STORE"].character.side_effect = None
        ns["STORE"].character.return_value = dict(self.old, **self.latest)
        self.assertTrue(deliver())
        self.assertIsNone(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            )
        )
        ns["join_world"].assert_called_once_with(
            self.generation, ns["connection"], dict(self.old, **self.latest)
        )

    def test_changed_position_fence_preserves_world_until_fresh_delivery(self):
        deliver, ns = self.delivery()
        rift_transition_delivery.queue((self.member,), self.first)
        ns["STORE"].character.return_value = dict(self.old, **self.first)
        ns["POSITIONS"].attach.side_effect = PositionBaselineChanged(
            "newer durable move"
        )
        self.assertFalse(deliver())
        ns["WORLD"].leave.assert_not_called()
        ns["cancel_crafting"].assert_not_called()
        ns["send"].assert_not_called()
        self.assertEqual(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            ),
            self.first,
        )
        ns["POSITIONS"].attach.side_effect = None
        self.assertTrue(deliver())
        ns["WORLD"].leave.assert_called_once_with(self.actor_id, self.generation)

    def test_replaced_session_still_cannot_hydrate_or_acknowledge(self):
        deliver, ns = self.delivery()
        rift_transition_delivery.queue((self.member,), self.first)
        ns["STORE"].current_character_session.return_value = False
        with self.assertRaisesRegex(ValueError, "replaced session"):
            deliver()
        ns["STORE"].character.assert_not_called()
        ns["WORLD"].leave.assert_not_called()
        ns["POSITIONS"].attach.assert_not_called()
        ns["send"].assert_not_called()
        self.assertEqual(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            ),
            self.first,
        )

    def test_new_wakeup_during_publication_is_not_acknowledged_as_old_destination(self):
        deliver, ns = self.delivery()
        rift_transition_delivery.queue((self.member,), self.first)
        ns["STORE"].character.return_value = dict(self.old, **self.first)
        ns["send"].side_effect = lambda *args: rift_transition_delivery.queue(
            (self.member,), self.latest
        )
        self.assertTrue(deliver())
        self.assertEqual(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            ),
            self.latest,
        )

    def test_respawn_attach_failure_does_not_publish_occupation_or_world(self):
        deliver, ns = self.delivery()
        metadata = dict(position_released=False, occupation_published=False)
        destination = dict(self.first, world_respawn=metadata)
        rift_transition_delivery.queue((self.member,), destination)
        ns["STORE"].character.return_value = dict(self.old, **self.first)
        ns["POSITIONS"].attach.side_effect = PositionBaselineChanged(
            "newer durable move"
        )
        ns.update(
            INITIAL_world_respawn_retry_at=0.0,
            character=self.old,
            time=time,
            DatabaseError=type("DatabaseError", (Exception,), {}),
            PoolTimeout=type("PoolTimeout", (Exception,), {}),
            send_batch=Mock(),
        )
        ns["prepare_world_respawn_delivery"] = caller(
            "prepare_world_respawn_delivery", ns
        )
        from wakfu_server import world_respawn

        with patch.object(
            world_respawn, "publication", return_value=((12436, b"health"),)
        ), patch.object(world_respawn, "release_position") as release:
            self.assertFalse(deliver())
        release.assert_called_once()
        ns["send_batch"].assert_not_called()
        ns["WORLD"].leave.assert_not_called()
        self.assertTrue(metadata["position_released"])
        self.assertFalse(metadata["occupation_published"])


if __name__ == "__main__":
    unittest.main()
