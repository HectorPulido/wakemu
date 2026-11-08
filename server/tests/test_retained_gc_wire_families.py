"""Strict native QI metadata schemas that add no graph-reference edges."""
import unittest

from wakfu_server.combat_retained_gc import _wire_references


def _varint(value):
    value &= (1 << 64) - 1
    output = bytearray()
    while value > 0x7F:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _encode(items):
    output = bytearray()
    for number, wire, value in items:
        output.extend(_varint(number * 8 + wire))
        if wire == 0:
            output.extend(_varint(value))
        elif wire == 2:
            output.extend(_varint(len(value)))
            output.extend(value)
        else:
            raise AssertionError(
                "test encoder supports only varint and length-delimited fields"
            )
    return bytes(output)


def _payload(family, fields):
    nested = _encode(fields)
    return _encode(
        [
            (2, 0, 9001),
            (6, 0, -191),
            (7, 0, -196),
            (8, 2, nested),
            (9, 0, 3),
            (10, 0, 444),
        ]
    ).hex()


class RetainedGCWireFamilyTests(unittest.TestCase):
    def test_maximum_resource_families_accept_only_scalar_metadata(self):
        expected = ({-191, -196}, {9001}, {444})
        for family in (20, 31, 41, 191, 991):
            for delta in (-(1 << 31), -1, 0, (1 << 31) - 1):
                for apply_current, remove_current in ((0, 0), (0, 1), (1, 0), (1, 1)):
                    payload = _payload(
                        family,
                        [
                            (10, 0, delta),
                            (31, 0, apply_current),
                            (32, 0, remove_current),
                        ],
                    )
                    with self.subTest(
                        family=family,
                        delta=delta,
                        flags=(apply_current, remove_current),
                    ):
                        self.assertEqual(_wire_references(payload, family), expected)

    def test_family57_boolean_pair_adds_no_roots_and_preserves_outer_edges(self):
        expected = ({-191, -196}, {9001}, {444})
        for restore in (0, 1):
            for reduce_current in (0, 1):
                payload = _payload(57, [(34, 0, restore), (35, 0, reduce_current)])
                with self.subTest(flags=(restore, reduce_current)):
                    self.assertEqual(_wire_references(payload, 57), expected)
        with self.assertRaises(ValueError):
            _wire_references(_payload(42, [(34, 0, 1), (35, 0, 0)]), 42)

    def test_malformed_duplicate_unknown_and_wrong_family_fields_fail_closed(self):
        invalid_fields = (
            [(10, 0, 1), (31, 0, 0)],
            [(10, 0, 1), (31, 0, 0), (32, 0, 2)],
            [(10, 0, 1 << 31), (31, 0, 0), (32, 0, 0)],
            [(10, 0, 1), (31, 2, b""), (32, 0, 0)],
            [(10, 0, 1), (31, 0, 0), (32, 0, 0), (33, 0, 1)],
        )
        for fields in invalid_fields:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                _wire_references(_payload(41, fields), 41)
        duplicate_nested = _encode(
            [
                (34, 0, 1),
                (35, 0, 0),
                (35, 0, 1),
            ]
        )
        duplicate_outer = _encode(
            [
                (6, 0, -191),
                (7, 0, -196),
                (8, 2, duplicate_nested),
            ]
        ).hex()
        with self.assertRaises(ValueError):
            _wire_references(duplicate_outer, 57)
        with self.assertRaises(ValueError):
            _wire_references(_payload(57, [(10, 0, 1), (31, 0, 0), (32, 0, 0)]), 57)
        with self.assertRaises(ValueError):
            _wire_references(_payload(41, [(34, 0, 1), (35, 0, 0)]), 41)


if __name__ == "__main__":
    unittest.main()
