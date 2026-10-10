import unittest
from unittest.mock import Mock, patch

from wakfu_server import dungeon_instances
from wakfu_server.maps import dungeon_transition_delivery as delivery


class DungeonTransitionDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.event = {
            "event_id": 4,
            "character_id": 27,
            "session_generation": "lease-a",
            "source_map_id": 527,
            "source_instance_id": 0,
            "source_x": -245,
            "source_y": -90,
            "source_z": 2,
            "destination_map_id": 1086,
            "destination_instance_id": 144115188075855873,
            "destination_x": 4,
            "destination_y": -12,
            "destination_z": 0,
        }
        self.source = {
            "map_id": 527,
            "instance_id": 0,
            "x": -245,
            "y": -90,
            "z": 2,
        }
        self.destination = {
            "map_id": 1086,
            "instance_id": 144115188075855873,
            "x": 4,
            "y": -12,
            "z": 0,
        }
        self.store = object()

    def invoke(self, **overrides):
        values = {
            "worker_generation": "lease-a",
            "current_location": lambda: dict(self.source),
            "in_fight": lambda: False,
            "bootstrap": lambda _event: True,
        }
        values.update(overrides)
        return delivery.deliver_pending_transitions(
            self.store,
            9,
            "lease-a",
            27,
            **values,
        )

    def test_delivery_uses_the_canonical_dynamic_instance_registry(self):
        self.assertIs(delivery.dungeon_instances, dungeon_instances)
        with (
            patch.object(
                dungeon_instances, "pending_transitions", return_value=(self.event,)
            ) as pending,
            patch.object(
                dungeon_instances, "acknowledge_transition", return_value=True
            ) as acknowledge,
        ):
            result = self.invoke()
        self.assertEqual(result["state"], "delivered")
        pending.assert_called_once_with(self.store, 9, "lease-a", 27)
        acknowledge.assert_called_once_with(self.store, 9, "lease-a", 27, 4)

    def test_party_companion_can_walk_before_its_entry_is_delivered(self):
        with (
            patch.object(
                delivery.dungeon_instances,
                "pending_transitions",
                return_value=(self.event,),
            ),
            patch.object(
                delivery.dungeon_instances, "acknowledge_transition", return_value=True
            ) as ack,
        ):
            result = self.invoke(
                current_location=lambda: {
                    **self.source,
                    "x": self.source["x"] + 3,
                    "y": self.source["y"] - 2,
                }
            )
        self.assertEqual(result["state"], "delivered")
        ack.assert_called_once()

    def test_stale_worker_generation_does_not_query_or_send(self):
        with patch.object(delivery.dungeon_instances, "pending_transitions") as pending:
            result = self.invoke(worker_generation="lease-old")
        self.assertEqual(result["state"], "stale_generation")
        pending.assert_not_called()

    def test_combat_defers_without_bootstrap_or_ack(self):
        with (
            patch.object(
                delivery.dungeon_instances,
                "pending_transitions",
                return_value=(self.event,),
            ),
            patch.object(delivery.dungeon_instances, "acknowledge_transition") as ack,
        ):
            bootstrap = Mock(return_value=True)
            result = self.invoke(in_fight=lambda: True, bootstrap=bootstrap)
        self.assertEqual(result["state"], "deferred_combat")
        self.assertEqual(result["pending_event_ids"], (4,))
        bootstrap.assert_not_called()
        ack.assert_not_called()

    def test_unrelated_local_map_defers_without_ack(self):
        unrelated = {**self.destination, "map_id": 527}
        with (
            patch.object(
                delivery.dungeon_instances,
                "pending_transitions",
                return_value=(self.event,),
            ),
            patch.object(delivery.dungeon_instances, "acknowledge_transition") as ack,
        ):
            bootstrap = Mock(return_value=True)
            result = self.invoke(
                current_location=lambda: unrelated, bootstrap=bootstrap
            )
        self.assertEqual(result["state"], "deferred_map_mismatch")
        bootstrap.assert_not_called()
        ack.assert_not_called()

    def test_partial_bootstrap_keeps_event_pending_then_retry_acks(self):
        with (
            patch.object(
                delivery.dungeon_instances,
                "pending_transitions",
                return_value=(self.event,),
            ),
            patch.object(
                delivery.dungeon_instances,
                "acknowledge_transition",
                return_value=True,
            ) as ack,
        ):
            partial = self.invoke(bootstrap=lambda _event: False)
            ack.assert_not_called()
            retried = self.invoke(bootstrap=lambda _event: True)
        self.assertEqual(partial["state"], "bootstrap_incomplete")
        self.assertEqual(partial["pending_event_ids"], (4,))
        self.assertEqual(retried["state"], "delivered")
        ack.assert_called_once_with(self.store, 9, "lease-a", 27, 4)

    def test_generation_change_during_bootstrap_does_not_ack(self):
        with (
            patch.object(
                delivery.dungeon_instances,
                "pending_transitions",
                return_value=(self.event,),
            ),
            patch.object(
                delivery.dungeon_instances,
                "acknowledge_transition",
                side_effect=ValueError("session replaced"),
            ) as ack,
        ):
            result = self.invoke()
        self.assertEqual(result["state"], "session_or_destination_changed")
        self.assertEqual(result["pending_event_ids"], (4,))
        ack.assert_called_once()

    def test_rejects_ambiguous_worker_combat_state(self):
        with patch.object(
            delivery.dungeon_instances,
            "pending_transitions",
            return_value=(self.event,),
        ):
            with self.assertRaisesRegex(ValueError, "combat state must be boolean"):
                self.invoke(in_fight=lambda: None)


if __name__ == "__main__":
    unittest.main()
