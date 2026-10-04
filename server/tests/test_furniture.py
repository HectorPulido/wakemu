import unittest
from wakfu_server.haven_bag_furniture import encode_furniture, decode_furniture


class FurnitureTests(unittest.TestCase):
    def test_minimal_wire_and_roundtrip(self):
        values = dict(
            template_id=91,
            item_uid=701,
            item_ref=804,
            quantity=1,
            x=-2,
            y=7,
            z=3,
            direction=4,
            virtual=False,
        )
        blob = encode_furniture(**values)
        self.assertEqual(len(blob), 43)
        self.assertEqual(blob[34:], bytes(9))
        self.assertEqual(decode_furniture(blob), values)

    def test_no_silent_option_discard(self):
        blob = bytearray(
            encode_furniture(template_id=1, item_uid=2, item_ref=3, x=0, y=0)
        )
        for index in (34, 42):
            changed = blob.copy()
            changed[index] = 1
            with self.assertRaises(ValueError):
                decode_furniture(changed)
        with self.assertRaises(ValueError):
            decode_furniture(bytes(blob) + b"\0")

    def test_reject_invalid_own_item(self):
        for uid in (0, -1):
            with self.assertRaises(ValueError):
                encode_furniture(template_id=1, item_uid=uid, item_ref=3, x=0, y=0)
