import unittest
from wakfu_server.combat_target_copy_book import TargetCopyBookAction, copy_target_book


class TargetCopyBookTests(unittest.TestCase):
    def test_native_filter_order_capacity_and_borrowed_identity(self):
        objects = [object() for _ in range(9)]
        rows = [
            TargetCopyBookAction(objects[i], kinds, elemental)
            for i, (kinds, elemental) in enumerate(
                [
                    ((307,), True),
                    ((2,), True),
                    ((324,), True),
                    ((2,), None),
                    ((2,), False),
                    ((2,), True),
                    ((2,), True),
                    ((2,), True),
                    ((2,), True),
                ]
            )
        ]
        selected = copy_target_book(rows)
        self.assertEqual(selected, tuple(objects[i] for i in (1, 5, 6, 7)))
        self.assertIs(selected[0], objects[1])

    def test_empty_is_preserved_and_malformed_operands_fail_closed(self):
        self.assertEqual(copy_target_book([]), ())
        for rows in (
            None,
            [object()],
            [TargetCopyBookAction(object(), (True,), True)],
            [TargetCopyBookAction(object(), (), 1)],
        ):
            with self.assertRaises(ValueError):
                copy_target_book(rows)
