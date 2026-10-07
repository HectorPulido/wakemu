import unittest
import struct

from wakfu_server.characters.ecology_feedback import describe, information


class EcologyFeedbackTests(unittest.TestCase):
    def test_native_information_subtype_four_uses_utf8_signed_short_length(self):
        text = "Ecosistema: á"
        opcode, body = information(text)
        encoded = text.encode("utf-8")
        self.assertEqual(349, opcode)
        self.assertEqual(struct.pack(">hh", 4, len(encoded)) + encoded, body)
        maximum = "á" * 16383 + "a"
        opcode, body = information(maximum)
        self.assertEqual((349, 32767), (opcode, struct.unpack(">hh", body[:4])[1]))
        self.assertEqual(maximum.encode("utf-8"), body[4:])
        for invalid in ("á" * 16384, 123, None):
            with self.subTest(invalid_type=type(invalid).__name__):
                with self.assertRaises(ValueError):
                    information(invalid)

    def test_worsening_transition_uses_actual_negative_affinity_and_spanish_decimal(
        self,
    ):
        receipt = {
            "before_value": 25,
            "after_value": 0,
            "evidence": {
                "before_population": 101,
                "after_population": 102,
                "minimum": 100,
                "maximum": 100,
                "distance_before": 1,
                "distance_after": 2,
            },
        }
        message = describe(receipt)
        self.assertIn("empeora el equilibrio", message)
        self.assertIn("0,25 puntos hacia Stasis", message)
        self.assertIn("0,25% Wakfu → Neutral", message)

    def test_neutral_inside_band_and_equal_distance_do_not_claim_a_reward(self):
        inside = {
            "before_value": 0,
            "after_value": 0,
            "evidence": {
                "before_population": 50,
                "after_population": 51,
                "minimum": 10,
                "maximum": 100,
                "distance_before": 0,
                "distance_after": 0,
            },
        }
        outside_but_equal = {
            **inside,
            "evidence": {
                **inside["evidence"],
                "before_population": 9,
                "after_population": 11,
                "distance_before": 1,
                "distance_after": 1,
            },
        }
        self.assertIn("mantiene el equilibrio", describe(inside))
        self.assertIn("sin cambio de afinidad", describe(inside))
        self.assertIn("no reduce el desequilibrio", describe(outside_but_equal))
        self.assertNotIn("puntos hacia", describe(outside_but_equal))

    def test_saturated_receipt_reports_zero_actual_change(self):
        receipt = {
            "before_value": 9900,
            "after_value": 9900,
            "evidence": {
                "before_population": 9,
                "after_population": 10,
                "minimum": 10,
                "maximum": 10,
                "distance_before": 1,
                "distance_after": 0,
            },
        }
        message = describe(receipt)
        self.assertIn("mejora el equilibrio", message)
        self.assertIn("sin cambio de afinidad", message)
        self.assertNotIn("puntos hacia Wakfu", message)


if __name__ == "__main__":
    unittest.main()
