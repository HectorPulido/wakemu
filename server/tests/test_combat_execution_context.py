import unittest

from wakfu_server.combat.combat_execution_context import constructed_execution_context


class NativeExecutionContextTests(unittest.TestCase):
    def test_original_constructor_preserves_true_ban_and_explicit_none(self):
        context = constructed_execution_context()
        self.assertTrue(context.ban)
        self.assertEqual(
            context.payload().hex(),
            "0800100020ffffffffffffffffff0128013000380040004800",
        )

    def test_original_scalar_mutators_and_negative_int32_wire(self):
        context = constructed_execution_context().sp(3).mb(False).set_mc(True)
        context = context.mark_bb_i().force(-17, 2)
        self.assertEqual(
            context.payload().hex(),
            "080010002003280030efffffffffffffffff01380140014802",
        )

    def test_unknown_values_are_rejected(self):
        context = constructed_execution_context()
        for change in (
            lambda: context.sp(True),
            lambda: context.mb(1),
            lambda: context.force(1, 0),
            lambda: context.force(1 << 31, 1),
        ):
            with self.assertRaises(ValueError):
                change()
