import unittest
from wakfu_server.combat_resistance_stack import (
    capped_request,
    refill,
    requested_from_payload,
)
from wakfu_server.combat_stat_effects import owned_effect_payload

TIME = bytes.fromhex("08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01")


def row(uid, actual, requested):
    return {
        "actual": actual,
        "payload": owned_effect_payload(
            uid=uid,
            base_uid=None,
            generic_effect=348444,
            caster_id=7,
            target_id=-7,
            value=actual,
            stat_id=27,
            requested=requested,
            timing_payload=TIME,
            execution_status=0,
        ).hex(),
    }


class ResistanceStackTests(unittest.TestCase):
    def test_native_probe_150_plus100_and_removal(self):
        first = row(901, 150, 150)
        second = row(902, 50, 100)
        self.assertEqual(capped_request(100, [(901, first)]), 50)
        current, updates = refill(-50, -1000, 1000, False, [(902, second)])
        self.assertEqual(current, -100)
        self.assertEqual(updates[0][1], 100)
        self.assertEqual(requested_from_payload(updates[0][2]), 100)

    def test_insertion_order_and_prepercent_request_are_preserved(self):
        current, updates = refill(
            -150, -1000, 1000, False, [(902, row(902, 10, 50)), (901, row(901, 0, 100))]
        )
        self.assertEqual(current, -200)
        self.assertEqual([(u, v) for u, v, _ in updates], [(902, 50), (901, 10)])

    def test_native_allocation_is_not_resource_clamped_delta(self):
        current, updates = refill(-50, -50, 1000, False, [(902, row(902, 50, 100))])
        self.assertEqual(current, -50)
        self.assertEqual(updates[0][1], 100)
        current, updates = refill(-50, -1000, 1000, True, [(902, row(902, 50, 100))])
        self.assertEqual(current, -50)
        self.assertEqual(updates[0][1], 100)

    def test_cap_uses_same_action_values_not_characteristic_value(self):
        self.assertEqual(capped_request(100, []), 100)
        self.assertEqual(capped_request(100, [(901, row(901, 250, 250))]), 0)
