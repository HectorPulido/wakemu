"""Original pt/pw and cAv/cAu wire layouts for existing-character editing."""
import struct
import unittest

from wakfu_server import character_recustomization as recustom


class RecustomizationWireTests(unittest.TestCase):
    def test_native_presence_and_pending_mode_layout(self):
        for mode in (13, 29):
            character = dict(id=73, name="Same Name", recustomization=dict(mode=mode))
            self.assertEqual(
                recustom.creation_section(character),
                b"\x01\x00\x01" + struct.pack(">h", mode) + b"\x00",
            )
            self.assertEqual(
                recustom.transition_packets(character),
                [
                    (12707, struct.pack(">h", mode)),
                    (
                        22797,
                        struct.pack(">qB", 73, 9)
                        + b"Same Name"
                        + struct.pack(">hB", mode, 0),
                    ),
                ],
            )
            self.assertEqual(mode & 2, 0)

    def test_missing_or_invalid_entitlement_cannot_open_dressing_room(self):
        for pending in (None, {}, dict(mode=127), dict(mode=31)):
            with self.assertRaises(ValueError):
                recustom.transition_packets(
                    dict(id=73, name="Same Name", recustomization=pending)
                )

    def test_item_use_grammar_rejected_before_accessing_storage(self):
        for body in (
            b"",
            b"\0" * 11,
            b"\0" * 20,
            struct.pack(">iq", 5556, 0),
            struct.pack(">iq", -1, 99),
        ):
            with self.assertRaises(ValueError):
                recustom.request(None, 1, "generation", 73, body)


if __name__ == "__main__":
    unittest.main()
