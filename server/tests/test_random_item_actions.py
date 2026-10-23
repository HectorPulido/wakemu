"""Native random-box policy and private deterministic draw regressions."""
import copy
import json
from pathlib import Path
import unittest

from wakfu_server.random_item_actions import (
    PrivateDraw,
    blind_box_packets,
    draw_products,
)


def entry(reference, weight=1, *, lower=1, upper=1, nested=False):
    return dict(
        aAi=reference,
        cmY=weight,
        bfh=1,
        cqy=lower,
        cqz=upper,
        cqA=nested,
        csE=1,
        czl=0,
        czk="",
        gBO=[],
    )


def table(reference, *entries):
    return dict(d=reference, czg=1, gBN=list(entries))


class Rolls:
    def __init__(self, *values):
        self.values = iter(values)

    def randbelow(self, upper):
        if upper == 1:
            return 0
        value = next(self.values)
        if not 0 <= value < upper:
            raise AssertionError(f"Fixture roll {value} is outside {upper}")
        return value


class RandomItemDrawTests(unittest.TestCase):
    def test_optional_native_blind_box_dialog_receives_exact_winning_reference(self):
        import struct

        self.assertEqual(
            [(13817, struct.pack(">i", 12127))], blind_box_packets(["2158"], {12127: 1})
        )
        self.assertEqual([], blind_box_packets(["2875", "False"], {12127: 1, 12131: 2}))
        self.assertEqual([], blind_box_packets(["2870", "False"], {}))
        with self.assertRaises(ValueError):
            blind_box_packets(["2158"], {})

    def test_weight_boundaries_guarantees_and_empty_outcome_are_preserved(self):
        source = table(
            1, entry(88, -1, lower=2, upper=2), entry(10, 0.1), entry(0, 0.2)
        )
        self.assertEqual(
            {88: 2, 10: 1}, draw_products(1, {1: source}.__getitem__, Rolls(0))
        )
        self.assertEqual({88: 2}, draw_products(1, {1: source}.__getitem__, Rolls(1)))
        self.assertEqual({88: 2}, draw_products(1, {1: source}.__getitem__, Rolls(2)))
        self.assertEqual(
            {}, draw_products(1, {1: table(1, entry(0))}.__getitem__, Rolls())
        )

    def test_nested_quantity_makes_independent_child_draws_and_merges_products(self):
        tables = {
            1: table(1, entry(2, -1, lower=2, upper=2, nested=True)),
            2: table(2, entry(10), entry(20)),
        }
        self.assertEqual(
            {10: 1, 20: 1}, draw_products(1, tables.__getitem__, Rolls(0, 1))
        )
        self.assertEqual({10: 2}, draw_products(1, tables.__getitem__, Rolls(0, 0)))
        tables[2] = table(2, entry(10, lower=1, upper=3))
        self.assertEqual({10: 4}, draw_products(1, tables.__getitem__, Rolls(0, 2)))

    def test_rejects_cycles_unknown_kinds_criteria_and_unsupported_rolls(self):
        cycle = {1: table(1, entry(1, -1, nested=True))}
        with self.assertRaisesRegex(ValueError, "recursion"):
            draw_products(1, cycle.__getitem__, Rolls())
        variants = [
            dict(czg=3),
            dict(gBN=[dict(entry(10), czk="IsNeoServer()")]),
            dict(gBN=[dict(entry(10), bfh=2)]),
            dict(gBN=[entry(10, -2)]),
            dict(gBN=[entry(10, float("nan"))]),
        ]
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                draw_products(
                    1, {1: dict(table(1, entry(10)), **changes)}.__getitem__, Rolls()
                )

    def test_same_uid_committed_counter_replays_and_next_use_changes_stream(self):
        secret = bytes(range(32))

        def stream(nonce):
            rng = PrivateDraw(secret, 7, 123, 987, nonce)
            return [rng.randbelow(1000000000000000000) for _ in range(8)]

        self.assertEqual(stream(0), stream(0))
        self.assertNotEqual(stream(0), stream(1))
        for upper in (1, 2, 3, 17, 256, 2**80 + 1):
            rng = PrivateDraw(secret, 7, 123, 987, 0)
            self.assertTrue(all(0 <= rng.randbelow(upper) < upper for _ in range(20)))

    def test_all_390_qualified_native_boxes_produce_resolved_products(self):
        document = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "protocol/native-random-item-actions.json"
            ).read_text()
        )
        tables = {row["d"]: row for row in document["tables"]}
        available = [row for row in document["actions"] if row["available"]]
        self.assertEqual(390, len(available))
        for action in available:
            rng = PrivateDraw(
                bytes(range(32)), 7, action["action_id"], action["item_ref"], 0
            )
            products = draw_products(action["root_table"], tables.__getitem__, rng)
            self.assertTrue(
                all(
                    type(ref) is int and ref > 0 and quantity > 0
                    for ref, quantity in products.items()
                )
            )
        self.assertEqual(46, sum(not row["available"] for row in document["actions"]))
