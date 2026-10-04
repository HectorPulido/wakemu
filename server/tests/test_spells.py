import struct
import unittest
from wakfu_server import spells


class SpellsTests(unittest.TestCase):
    def character(self, breed):
        return {"id": 3, "breed": breed, "level": 1}

    def test_level_one_spell_ownership_differs_by_breed(self):
        self.assertEqual(
            [s["id"] for s in spells.available_spells(2, 1)], [7307, 7312, 7317]
        )
        self.assertEqual(
            [s["id"] for s in spells.available_spells(8, 1)], [4778, 4780, 4785]
        )
        self.assertEqual(
            [s["id"] for s in spells.available_spells(15, 1)], [6260, 6261, 6266]
        )
        for breed in (2, 8, 15):
            body = spells.spell_inventory(self.character(breed))
            self.assertEqual(len(body), 46)
            self.assertEqual(struct.unpack_from(">H", body)[0], 3)
            self.assertEqual(body[-2:], b"\x00\x00")
            self.assertEqual(
                spells.validate_deck(
                    spells.default_deck(self.character(breed)), breed, 1
                )["level_cap"],
                -1,
            )

    def test_empty_deck_and_sparse_slots_are_valid(self):
        self.assertEqual(spells.validate_deck(spells.encode_deck(), 8, 1)["active"], [])
        self.assertEqual(
            spells.validate_deck(spells.encode_deck([0, 4778]), 8, 1)["active"],
            [0, 4778],
        )

    def test_locked_wrong_breed_duplicate_and_wrong_kind_are_rejected(self):
        wrongs = [
            spells.encode_deck([7307]),
            spells.encode_deck([4778, 4778]),
            spells.encode_deck([0] * 6 + [4778]),
            spells.encode_deck([], [4778]),
            spells.encode_deck([4778], [], 2),
        ]
        for body in wrongs:
            with self.assertRaises(ValueError):
                spells.validate_deck(body, 8, 1)

    def test_malformed_lengths_and_trailing_data_are_rejected(self):
        body = spells.default_deck(self.character(8))
        for invalid in (
            body[:-1],
            body + b"\x00",
            struct.pack(">i", -1),
            struct.pack(">i", 13),
        ):
            with self.assertRaises(ValueError):
                spells.validate_deck(invalid, 8, 1)
