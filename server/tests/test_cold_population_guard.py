"""Cold scalar guard matches the previous expression without callback reads."""
import unittest
from wakfu_server import combat_retained_runtime as retained


def reference(uid, record):
    return (
        type(uid) is int
        and type(record) is dict
        and len(record) <= 17
        and all(
            type(key) is str
            and len(key) <= 64
            and (
                type(value) is int
                or type(value) is bool
                or type(value) is str
                or type(value) is type(None)
            )
            and (type(value) is not str or len(value) <= 128)
            and (type(value) is not int or value.bit_length() <= 64)
            for key, value in record.items()
        )
    )


class ColdPopulationGuardTests(unittest.TestCase):
    def test_scalar_bounds_shape_types_and_key_order_match(self):
        values = [
            None,
            True,
            False,
            0,
            -1,
            2**64 - 1,
            -(2**64 - 1),
            2**64,
            -(2**64),
            "",
            "a" * 128,
            "a" * 129,
            1.0,
            [],
            {},
            (),
            object(),
        ]
        keys = ["", "uid", "a" * 64, "a" * 65, 1, None]
        for uid in (0, 1, -1, True, None, "1"):
            for key in keys:
                for value in values:
                    row = {key: value}
                    with self.subTest(
                        uid=uid, key_type=type(key), value_type=type(value)
                    ):
                        self.assertIs(
                            (
                                type(uid) is int
                                and retained._cacheable_retained_record(row)
                            ),
                            reference(uid, row),
                        )
        for size in (0, 1, 16, 17, 18):
            row = {str(i): i for i in range(size)}
            self.assertIs(retained._cacheable_retained_record(row), reference(1, row))
            reversed_row = dict(reversed(tuple(row.items())))
            self.assertIs(
                retained._cacheable_retained_record(reversed_row),
                reference(1, reversed_row),
            )

    def test_custom_containers_scalars_and_metaclasses_do_not_execute_callbacks(self):
        calls = []

        class CustomMap(dict):
            def items(self):
                calls.append("items")
                raise AssertionError("must not read custom mapping")

            def __len__(self):
                calls.append("len")
                raise AssertionError("must not read custom mapping")

        class CustomInt(int):
            def bit_length(self):
                calls.append("bit_length")
                raise AssertionError("must not inspect custom scalar")

        class CustomStr(str):
            def __len__(self):
                calls.append("str_len")
                raise AssertionError("must not inspect custom scalar")

        class EqualMeta(type):
            def __eq__(self, other):
                calls.append("meta_eq")
                raise AssertionError("types are compared by identity")

        class Custom(metaclass=EqualMeta):
            pass

        for uid, row in [
            (CustomInt(1), {}),
            (1, CustomMap()),
            (1, {"uid": CustomInt(1)}),
            (1, {"uid": CustomStr("x")}),
            (1, {CustomStr("uid"): 1}),
            (1, {"uid": Custom()}),
        ]:
            self.assertIs(
                (type(uid) is int and retained._cacheable_retained_record(row)),
                reference(uid, row),
            )
        self.assertEqual(calls, [])
