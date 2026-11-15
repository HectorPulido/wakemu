import unittest

from wakfu_server.wire_native import patch


class NativeWirePatchTests(unittest.TestCase):
    def test_original_spans_preserve_binary_gaps_insertions_and_deletions(self):
        base = b"\x00\xffabc\x80tail\x00"
        self.assertEqual(
            patch(base, [(5, 6, b""), (0, 0, b"prefix\xff"), (2, 5, b"\x00\x80")]),
            b"prefix\xff\x00\xff\x00\x80tail\x00",
        )
        self.assertEqual(patch(b"", [(0, 0, b"\x00\xff")]), b"\x00\xff")
        self.assertEqual(patch(base, []), base)

    def test_malformed_spans_fail_before_any_output_is_returned(self):
        for spans in (
            [(-1, 1, b"x")],
            [(2, 1, b"x")],
            [(0, 4, b"x")],
            [(0, 2, b"x"), (1, 3, b"y")],
        ):
            with self.subTest(spans=spans), self.assertRaises(ValueError):
                patch(b"abc", spans)
