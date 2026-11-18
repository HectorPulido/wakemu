"""Native stage context cleanup follows real receipts and successful bootstrap."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_refresh as refresh
from wakfu_server import rift_transition_delivery as delivery


class OwnedStoryRefreshTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7, account_id=2, instance_id=99, map_id=980, x=0, y=-3, z=0
        )
        self.selected = dict(id="voyage", steps=[dict(id="wave1")])
        self.proof = refresh._proof(self.selected, self.character, "wave1")
        self.db = Mock()

    def test_only_unacknowledged_actual_phase_requests_a_refresh(self):
        with patch.object(
            refresh.controller, "_scope", return_value=(self.selected, {"wave1"})
        ):
            self.db.execute.side_effect = [
                SimpleNamespace(
                    fetchone=lambda: dict(payload=dict(refresh_context=True))
                ),
                SimpleNamespace(fetchone=lambda: None),
            ]
            self.assertEqual(
                refresh.pending(self.db, object(), self.character), self.proof
            )
            self.db.execute.side_effect = [
                SimpleNamespace(
                    fetchone=lambda: dict(payload=dict(refresh_context=True))
                ),
                SimpleNamespace(fetchone=lambda: dict(exists=1)),
            ]
            self.assertIsNone(refresh.pending(self.db, object(), self.character))
            self.db.execute.side_effect = [
                SimpleNamespace(
                    fetchone=lambda: dict(payload=dict(refresh_context=False))
                )
            ]
            self.assertIsNone(refresh.pending(self.db, object(), self.character))

    def test_refresh_queues_after_commit_and_acknowledges_only_the_matching_real_stage(
        self,
    ):
        inside = [False]

        @contextmanager
        def connection():
            inside[0] = True
            try:
                yield self.db
            finally:
                inside[0] = False

        store = SimpleNamespace(connection=connection, now=lambda: 100)
        self.db.execute.side_effect = None
        self.db.execute.return_value.fetchone.return_value = dict(ok=1)

        def queued(*args, **kwargs):
            self.assertFalse(inside[0])
            self.assertEqual(kwargs["context_receipt"], self.proof)

        with patch.object(refresh, "pending", return_value=self.proof), patch.object(
            delivery, "queue_owned_position_refresh", side_effect=queued
        ) as queue:
            self.assertTrue(refresh.notify_pending(store, self.character, "lease"))
            queue.assert_called_once()
        self.db.execute.return_value.fetchone.return_value = dict(
            payload=dict(refresh_context=True)
        )
        with patch.object(
            refresh.controller, "_scope", return_value=(self.selected, {"wave1"})
        ), patch.object(refresh.storage, "record_event") as record:
            refresh.acknowledge(store, self.character, self.proof)
            self.assertTrue(
                record.call_args.args[2].startswith("owned-story-context-refreshed:")
            )
            self.assertFalse(record.call_args.args[2].startswith("owned-story:"))
            with self.assertRaises(ValueError):
                refresh.acknowledge(
                    store, self.character, dict(self.proof, instance_id=88)
                )

    def test_native_end_dialogue_deadline_defers_refresh_but_blocks_next_stage(self):
        receipt = dict(payload=dict(refresh_context=True, created_ms=1000))
        store = SimpleNamespace(now=lambda: datetime.fromtimestamp(3, timezone.utc))
        with patch.object(
            refresh.controller, "_scope", return_value=(self.selected, {"wave1"})
        ), patch(
            "wakfu_server.owned_story_mechanics.sources",
            return_value=dict(context_refresh_delays={"wave1": 3500}),
        ):
            self.db.execute.return_value.fetchone.return_value = receipt
            self.assertIsNone(
                refresh.pending(self.db, store, self.character, due_only=True)
            )
            self.db.execute.side_effect = [
                SimpleNamespace(fetchone=lambda: receipt),
                SimpleNamespace(fetchone=lambda: None),
            ]
            self.assertEqual(
                refresh.pending(self.db, store, self.character), self.proof
            )
            store.now = lambda: datetime.fromtimestamp(5, timezone.utc)
            self.db.execute.side_effect = [
                SimpleNamespace(fetchone=lambda: receipt),
                SimpleNamespace(fetchone=lambda: None),
            ]
            self.assertEqual(
                refresh.pending(self.db, store, self.character, due_only=True),
                self.proof,
            )

    def test_suppressed_presentation_skips_deadline_but_delivered_scene_keeps_it(self):
        receipt = dict(
            payload=dict(
                refresh_context=True,
                created_ms=1000,
                presentation_suppressed=True,
                presentation_delivered=False,
            )
        )
        store = SimpleNamespace(now=lambda: datetime.fromtimestamp(3, timezone.utc))
        with patch.object(
            refresh.controller, "_scope", return_value=(self.selected, {"wave1"})
        ), patch(
            "wakfu_server.owned_story_mechanics.sources",
            return_value=dict(context_refresh_delays={"wave1": 15000}),
        ):
            self.db.execute.side_effect = [
                SimpleNamespace(fetchone=lambda: receipt),
                SimpleNamespace(fetchone=lambda: None),
            ]
            self.assertEqual(
                refresh.pending(self.db, store, self.character, due_only=True),
                self.proof,
            )
            delivered = dict(
                payload=dict(
                    refresh_context=True,
                    created_ms=1000,
                    presentation_suppressed=False,
                    presentation_delivered=True,
                )
            )
            self.db.execute.side_effect = [
                SimpleNamespace(fetchone=lambda: delivered),
            ]
            self.assertIsNone(
                refresh.pending(self.db, store, self.character, due_only=True)
            )

    def test_shared_wakeup_carries_stage_proof_without_replacing_newer_travel(self):
        location = self.character
        delivery.queue_owned_position_refresh(
            2, "story-refresh-test", 7, location, context_receipt=self.proof
        )
        queued = delivery.pending(2, "story-refresh-test", 7)
        self.assertEqual(queued["owned_story_refresh"], self.proof)
        delivery.queue_owned_position_refresh(
            2, "story-refresh-test", 7, dict(location, map_id=527)
        )
        self.assertEqual(delivery.pending(2, "story-refresh-test", 7), queued)
        delivery.acknowledge(2, "story-refresh-test", 7, queued)

    def test_context_only_scope_reads_bounded_location_without_hydrating_inventory(
        self,
    ):
        db = Mock()
        db.execute.side_effect = [
            SimpleNamespace(
                fetchone=lambda: dict(
                    context_route_key="ship", context_policy_version=1, start_map_id=980
                )
            ),
            SimpleNamespace(fetchall=lambda: [dict(character_id=7)]),
            SimpleNamespace(fetchone=lambda: dict(map_id=980, instance_id=99)),
            SimpleNamespace(fetchall=lambda: []),
        ]
        selected = dict(id="ship", map_id=980)
        store = Mock()
        with patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration", return_value={}
        ), patch.object(refresh.controller, "policy", return_value=selected):
            actual, completed = refresh.controller._scope(
                db, store, self.character, check_position=False
            )
        self.assertEqual(actual, selected)
        self.assertEqual(completed, set())
        store.character.assert_not_called()
        self.assertIn(
            "SELECT map_id,instance_id FROM characters",
            db.execute.call_args_list[2].args[0],
        )
