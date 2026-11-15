"""Settled quest packets stay scoped until their owner's world return."""

from types import SimpleNamespace
import unittest

from wakfu_server import combat_progression_delivery


class CombatProgressionDeliveryTests(unittest.TestCase):
    def test_defer_and_after_return_preserve_original_packets_and_scope(self):
        fight = SimpleNamespace(id=611)
        packets = ((13832, b"objective"), (13371, b"tracking"))

        combat_progression_delivery.defer(fight, 260, 7, 328, packets)
        delivered = combat_progression_delivery.after_return(fight, 260, 7, 328)

        self.assertIs(delivered, packets)
        self.assertEqual(packets, delivered)
        self.assertEqual(
            (), combat_progression_delivery.after_return(fight, 261, 7, 329)
        )

    def test_defer_snapshots_mutable_packet_collections(self):
        fight = SimpleNamespace(id=611)
        packets = [(13832, b"objective")]

        combat_progression_delivery.defer(fight, 260, 7, 328, packets)
        packets.append((13371, b"later mutation"))

        self.assertEqual(
            ((13832, b"objective"),),
            combat_progression_delivery.after_return(fight, 260, 7, 328),
        )

    def test_after_return_rejects_mismatched_owner_or_session_generation(self):
        fight = SimpleNamespace(id=611)
        combat_progression_delivery.defer(fight, 260, 7, 328, ((13832, b"x"),))

        self.assertEqual(
            (), combat_progression_delivery.after_return(fight, 261, 7, 328)
        )
        self.assertEqual(
            (), combat_progression_delivery.after_return(fight, 260, 8, 328)
        )
        for generation, character_id in ((7, 329),):
            with self.subTest(
                generation=generation,
                character_id=character_id,
            ):
                with self.assertRaisesRegex(ValueError, "Foreign"):
                    combat_progression_delivery.after_return(
                        fight, 260, generation, character_id
                    )

    def test_conflicting_deferred_packets_fail_closed(self):
        fight = SimpleNamespace(id=611)
        combat_progression_delivery.defer(fight, 260, 7, 328, ((13832, b"x"),))

        with self.assertRaisesRegex(ValueError, "Conflicting"):
            combat_progression_delivery.defer(
                fight, 260, 7, 328, ((13832, b"different"),)
            )


if __name__ == "__main__":
    unittest.main()
