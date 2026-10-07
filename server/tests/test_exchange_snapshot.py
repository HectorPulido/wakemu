import struct
import unittest

from wakfu_server import exchange_snapshot


EXCHANGE = 901
LEFT = 12001
RIGHT = 12002
REVISION = 7


def member(character_id, cash=0, confirmed=None):
    return {
        "character_id": character_id,
        "offered_kamas": cash,
        "confirmed_revision": confirmed,
    }


def unit(uid, character_id, reference=12, quantity=1, **metadata):
    return {
        "uid": uid,
        "character_id": character_id,
        "reference": reference,
        "quantity": quantity,
        **metadata,
    }


def offer(uid, character_id, quantity, **metadata):
    item = unit(uid, character_id, quantity=quantity, **metadata)
    return {
        "uid": uid,
        "character_id": character_id,
        "quantity": quantity,
        "unit": item,
    }


def snapshot(items=(), *, left_cash=0, right_cash=0, confirmed=None):
    return {
        "state": "active",
        "inviter_id": LEFT,
        "invitee_id": RIGHT,
        "items": list(items),
        "members": [
            member(LEFT, left_cash, confirmed),
            member(RIGHT, right_cash, confirmed),
        ],
    }


def item_packets(result):
    return [(opcode, body) for opcode, body in result if opcode in (13084, 13636)]


class ExchangeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.exchange_id = EXCHANGE

    def publish(self, current, previous=None, revision=REVISION):
        return exchange_snapshot.packets(self.exchange_id, revision, current, previous)

    def test_quantity_increase_emits_only_the_added_delta(self):
        previous = snapshot([offer(501, LEFT, 2)])
        current = snapshot([offer(501, LEFT, 5)])
        packets = item_packets(self.publish(current, previous))
        self.assertEqual(1, len(packets))
        opcode, body = packets[0]
        self.assertEqual(13636, opcode)
        exchange_id, actor_id, result, quantity = struct.unpack_from(">qqBh", body)
        uid, reference, current_quantity = struct.unpack_from(">qih", body, 19)
        self.assertEqual(
            (EXCHANGE, LEFT, 0, 3), (exchange_id, actor_id, result, quantity)
        )
        self.assertEqual((501, 12, 5), (uid, reference, current_quantity))

    def test_quantity_decrease_and_full_withdrawal_remove_only_removed_amount(self):
        cases = ((5, 2, 3), (5, 0, 5))
        for before, after, expected_delta in cases:
            with self.subTest(before=before, after=after):
                previous = snapshot([offer(502, LEFT, before)])
                current_items = [] if after == 0 else [offer(502, LEFT, after)]
                current = snapshot(current_items)
                packets = item_packets(self.publish(current, previous))
                self.assertEqual(1, len(packets))
                opcode, body = packets[0]
                self.assertEqual(13084, opcode)
                self.assertEqual(expected_delta, struct.unpack_from(">h", body, 17)[0])
                self.assertEqual(502, struct.unpack_from(">q", body, 19)[0])

    def test_unchanged_offer_emits_no_item_delta(self):
        same = snapshot([offer(503, LEFT, 2)])
        self.assertEqual([], item_packets(self.publish(same, same)))

    def test_metadata_change_removes_old_instance_before_adding_new_instance(self):
        previous = snapshot(
            [offer(504, LEFT, 2, damage_elements=2, resistance_elements=4)]
        )
        current = snapshot(
            [offer(504, LEFT, 2, damage_elements=8, resistance_elements=16)]
        )
        packets = item_packets(self.publish(current, previous))
        self.assertEqual([13084, 13636], [opcode for opcode, _ in packets])
        self.assertEqual(
            [2, 2], [struct.unpack_from(">h", body, 17)[0] for _, body in packets]
        )
        self.assertNotEqual(packets[0][1][19:], packets[1][1][19:])

    def test_foreign_participant_and_mismatched_unit_identity_fail_closed(self):
        invalid = (
            snapshot([offer(505, 99999, 1)]),
            snapshot(
                [
                    {
                        "uid": 505,
                        "character_id": LEFT,
                        "quantity": 1,
                        "unit": unit(506, LEFT, quantity=1),
                    }
                ]
            ),
            snapshot(
                [
                    {
                        "uid": 505,
                        "character_id": LEFT,
                        "quantity": 1,
                        "unit": unit(505, RIGHT, quantity=1),
                    }
                ]
            ),
            snapshot(
                [
                    {
                        "uid": 505,
                        "character_id": LEFT,
                        "quantity": 2,
                        "unit": unit(505, LEFT, quantity=1),
                    }
                ]
            ),
        )
        for current in invalid:
            with self.subTest(current=current), self.assertRaisesRegex(
                ValueError, "hydrated"
            ):
                self.publish(current)

    def test_cash_snapshot_sends_absolute_balance_and_ready_flags_follow_all_content(
        self,
    ):
        previous = snapshot(left_cash=5, right_cash=11, confirmed=None)
        current = snapshot(left_cash=13, right_cash=17, confirmed=REVISION)
        packets = self.publish(current, previous)
        contents = [
            index for index, (opcode, _) in enumerate(packets) if opcode == 13412
        ]
        readiness = [
            index for index, (opcode, _) in enumerate(packets) if opcode == 13486
        ]
        self.assertEqual(2, len(contents))
        self.assertEqual(2, len(readiness))
        self.assertGreater(
            min(readiness),
            max(contents),
            "a later cash update resets readiness sent earlier in this snapshot",
        )
        cash = {
            struct.unpack_from(">q", body, 8)[0]: struct.unpack_from(">q", body, 17)[0]
            for opcode, body in packets
            if opcode == 13412
        }
        self.assertEqual({LEFT: 13, RIGHT: 17}, cash)
        ready = {
            struct.unpack_from(">q", body, 8)[0]: body[16]
            for opcode, body in packets
            if opcode == 13486
        }
        self.assertEqual({LEFT: 1, RIGHT: 1}, ready)


if __name__ == "__main__":
    unittest.main()
