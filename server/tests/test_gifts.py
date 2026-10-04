import unittest
from wakfu_server.gifts import empty_message


class GiftTests(unittest.TestCase):
    def test_local_account_has_no_claimable_official_gift(self):
        self.assertEqual(empty_message(12722), b"\x00")
        self.assertEqual(empty_message(13369), b"\x00\x00\x00")
        with self.assertRaises(ValueError):
            empty_message(12723)
