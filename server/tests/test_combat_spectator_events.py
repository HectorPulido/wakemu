import unittest
import struct

from wakfu_server.combat.combat_spectator_events import (
    is_normal_finish_packet,
    public_combat_events,
    terminal_batch,
)


class SpectatorEventFilterTests(unittest.TestCase):
    def test_only_shared_combat_events_are_forwarded_and_deduplicated(self):
        shared = (13482, b"turn")
        owner_a = (
            (12847, b"private-owner-bootstrap"),
            shared,
            (12755, b"private-fight-reward"),
            (13509, b"attack"),
            (13873, b"private-account-wallet"),
        )
        owner_b = (
            (12847, b"different-owner-bootstrap"),
            shared,
            (12755, b"other-private-fight-reward"),
            (13509, b"attack"),
            (13021, b"private-kamas"),
        )

        self.assertEqual(
            public_combat_events((owner_a, owner_b)),
            (shared, (13509, b"attack")),
        )

    def test_private_rewards_currency_inventory_and_malformed_packets_never_forward(
        self,
    ):
        self.assertEqual(
            public_combat_events(
                (
                    (
                        (12755, b"fight report"),
                        (12753, b"account currency"),
                        (13021, b"character currency"),
                        (13873, b"wallet"),
                        (12691, b"inventory"),
                        (12847, b"owner bootstrap"),
                        (13482, "not bytes"),
                        (13482,),
                    ),
                )
            ),
            (),
        )

    def test_event_order_is_preserved_across_batches(self):
        batches = (
            ((13624, b"move"), (12873, b"stats")),
            ((13560, b"effect"), (12238, b"end")),
        )
        self.assertEqual(
            public_combat_events(batches),
            tuple(packet for batch in batches for packet in batch),
        )

    def test_duplicate_recipient_copy_is_deduped_per_sequence_only(self):
        repeated = (13482, b"same-turn-frame")
        sequence_n = public_combat_events(((repeated,), (repeated,)))
        sequence_n_plus_one = public_combat_events(((repeated,), (repeated,)))
        self.assertEqual(sequence_n, (repeated,))
        self.assertEqual(sequence_n + sequence_n_plus_one, (repeated, repeated))

    def test_intentional_duplicate_inside_one_owner_batch_is_preserved(self):
        repeated = (13560, b"effect")
        self.assertEqual(
            public_combat_events(((repeated, repeated), (repeated,))),
            (repeated, repeated),
        )

    @staticmethod
    def finish(fight_id=7, action_id=1):
        body = struct.pack(">iiiB", fight_id, action_id, -1, 0)
        body += b"\x01" + struct.pack(">q", 100)
        body += b"\x01" + struct.pack(">q", -200)
        body += b"\x00"
        return 12238, body

    def test_terminal_batch_keeps_one_native_finish_and_excludes_marker_removal(self):
        first = self.finish(action_id=4)
        duplicate = self.finish(action_id=5)
        marker_removal = (12238, struct.pack(">iiiB", 7, 1, -1, 1))
        animation = (13509, b"melee")
        self.assertTrue(is_normal_finish_packet(first, 7))
        self.assertFalse(is_normal_finish_packet(marker_removal, 7))
        self.assertEqual(
            terminal_batch(
                (animation, marker_removal, first, duplicate),
                fight_id=7,
                fallback_packet=lambda: self.finish(action_id=6),
            ),
            (animation, first),
        )

    def test_terminal_batch_builds_fallback_when_owner_batches_lost_result(self):
        fallback = self.finish(action_id=9)
        self.assertEqual(
            terminal_batch(
                ((13509, b"attack"),), fight_id=7, fallback_packet=lambda: fallback
            ),
            ((13509, b"attack"), fallback),
        )


if __name__ == "__main__":
    unittest.main()
