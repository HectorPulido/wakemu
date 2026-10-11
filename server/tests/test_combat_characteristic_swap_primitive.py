"""Installed eZy witness and ordered PA operations, without runtime assumptions."""
import unittest

from wakfu_server.combat_characteristic_swap import (
    swap_characteristics,
    swap_additional_payload,
)


class CharacteristicSwapPrimitiveTests(unittest.TestCase):
    def test_installed_wire_additional_bytes(self):
        # Actual eZy PC21/23 captured40/90 witness: AdditionalDatas field8.
        self.assertEqual(
            swap_additional_payload(21, 23, (40, 90)).hex(), "420a50286015980117a0015a"
        )

    def test_native_swap_and_inverse_order(self):
        values, calls = {21: 40, 23: 90}, []

        def shift(stat, amount, subtract):
            calls.append((stat, amount, subtract))
            values[stat] = max(
                -5000, min(50000, values[stat] + (-amount if subtract else amount))
            )

        captured = swap_characteristics(21, 23, current=values.__getitem__, shift=shift)
        self.assertEqual(values, {21: 90, 23: 40})
        self.assertEqual(
            calls, [(21, 40, True), (21, 90, False), (23, 90, True), (23, 40, False)]
        )
        calls.clear()
        swap_characteristics(
            21,
            23,
            current=values.__getitem__,
            shift=shift,
            captured=captured,
            remove=True,
        )
        self.assertEqual(values, {21: 40, 23: 90})
        self.assertEqual(
            calls, [(21, 90, True), (21, 40, False), (23, 40, True), (23, 90, False)]
        )

    def test_frozen_and_aliasing_still_deliver_all_four_operations(self):
        calls = []
        captured = swap_characteristics(
            21, 21, current=lambda stat: 7, shift=lambda *args: calls.append(args)
        )
        self.assertEqual(captured, (7, 7))
        self.assertEqual(calls, [(21, 7, True), (21, 7, False)] * 2)

    def test_missing_capture_or_malformed_current_fails_before_mutation(self):
        for captured, remove in ((None, True), ((1, None), False)):
            calls = []
            with self.assertRaises(ValueError):
                swap_characteristics(
                    21,
                    23,
                    current=lambda stat: 0,
                    shift=lambda *args: calls.append(args),
                    captured=captured,
                    remove=remove,
                )
            self.assertEqual(calls, [])
