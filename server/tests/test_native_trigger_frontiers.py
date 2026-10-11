"""Synthetic regressions for literal native PositionTrigger cut extraction."""
import unittest

from extract_native_trigger_frontiers import extract


def trigger(identity, position, *, map_id=7, object_type="PositionTrigger"):
    return dict(
        id=identity,
        x=position[0],
        y=position[1],
        z=position[2],
        map_id=map_id,
        type=object_type,
    )


def geometry(cells, edges, *, map_id=7):
    return dict(
        map_id=map_id,
        cells=[list(c) for c in cells],
        edges=[[list(a), list(b)] for a, b in edges],
    )


class NativeTriggerFrontierTests(unittest.TestCase):
    def test_unique_linear_chain_orders_each_native_cut(self):
        a, t1, b, t2, c = [(x, 0, 0) for x in range(5)]
        graph = geometry([a, t1, b, t2, c], [(a, t1), (t1, b), (b, t2), (t2, c)])
        result = extract(
            graph, [trigger(101, t1), trigger(102, t2)], a, c, expected_rooms=3
        )
        self.assertEqual(len(result["rooms"]), 3)
        self.assertEqual([f["source_ids"] for f in result["frontiers"]], [[101], [102]])
        self.assertEqual(
            [(f["source_room"], f["destination_room"]) for f in result["frontiers"]],
            [(1, 2), (2, 3)],
        )
        self.assertEqual([r["native_cell_count"] for r in result["rooms"]], [1, 1, 1])

    def test_connected_parallel_trigger_cells_form_one_mandatory_frontier(self):
        a, top, bottom, b = (0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 0, 0)
        graph = geometry(
            [a, top, bottom, b], [(a, top), (top, bottom), (top, b), (bottom, b)]
        )
        result = extract(
            graph, [trigger(201, top), trigger(202, bottom)], a, b, expected_rooms=2
        )
        self.assertEqual(len(result["frontiers"]), 1)
        self.assertEqual(result["frontiers"][0]["source_ids"], [201, 202])
        self.assertEqual(result["frontiers"][0]["source_room"], 1)
        self.assertEqual(result["frontiers"][0]["destination_room"], 2)

    def test_disconnected_parallel_lanes_merge_when_they_separate_same_regions(self):
        left_top, gate_top, right_top = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        left_low, gate_low, right_low = (0, 2, 0), (1, 2, 0), (2, 2, 0)
        cells = [left_top, gate_top, right_top, left_low, gate_low, right_low]
        edges = [
            (left_top, left_low),
            (right_top, right_low),
            (left_top, gate_top),
            (gate_top, right_top),
            (left_low, gate_low),
            (gate_low, right_low),
        ]
        result = extract(
            geometry(cells, edges),
            [trigger(301, gate_top), trigger(302, gate_low)],
            left_top,
            right_top,
            expected_rooms=2,
        )
        self.assertEqual(len(result["frontiers"]), 1)
        self.assertEqual(result["frontiers"][0]["source_ids"], [301, 302])
        self.assertEqual(result["frontiers"][0]["regions"], [0, 1])

    def test_missing_parallel_lane_is_a_rejected_bypass(self):
        left_top, gate_top, right_top = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        left_low, open_low, right_low = (0, 2, 0), (1, 2, 0), (2, 2, 0)
        cells = [left_top, gate_top, right_top, left_low, open_low, right_low]
        edges = [
            (left_top, left_low),
            (right_top, right_low),
            (left_top, gate_top),
            (gate_top, right_top),
            # This second path is open because its trigger is omitted.
            (left_low, open_low),
            (open_low, right_low),
        ]
        with self.assertRaisesRegex(
            ValueError, "ambiguous region adjacency|does not separate"
        ):
            extract(
                geometry(cells, edges), [trigger(401, gate_top)], left_top, right_top
            )

    def test_invalid_duplicate_nonintegral_unwalkable_and_blocked_triggers_reject(self):
        a, gate, b = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        graph = geometry([a, gate, b], [(a, gate), (gate, b)])
        good = trigger(501, gate)
        malformed = [
            ([trigger(501, gate, object_type="Door")], "identity/type/map"),
            ([trigger(501, gate, map_id=8)], "identity/type/map"),
            ([trigger(0, gate)], "identity/type/map"),
            ([good, trigger(501, (1, 1, 0))], "duplicated"),
            ([good, trigger(502, gate)], "position is duplicated"),
            ([trigger(502, (1.5, 0, 0))], "exactly integral"),
            ([trigger(502, (9, 9, 0))], "not a distinct walkable cut cell"),
        ]
        for triggers, message in malformed:
            with self.subTest(message=message), self.assertRaisesRegex(
                ValueError, message
            ):
                extract(graph, triggers, a, b)
        with self.assertRaisesRegex(ValueError, "not a distinct walkable cut cell"):
            extract(graph, [good], a, b, blocked_cells=[gate])
        with self.assertRaisesRegex(ValueError, "contradicts required encounter count"):
            extract(graph, [good], a, b, expected_rooms=3)

    def test_cycle_and_branching_region_graphs_fail_closed(self):
        # Three regions connected in a ring by three actual trigger cuts.
        r1, t12, r2, t23, r3, t31 = [(x, 0, 0) for x in range(6)]
        cycle = geometry(
            [r1, t12, r2, t23, r3, t31],
            [(r1, t12), (t12, r2), (r2, t23), (t23, r3), (r3, t31), (t31, r1)],
        )
        with self.assertRaisesRegex(ValueError, "branched or cyclic"):
            extract(
                cycle,
                [trigger(601, t12), trigger(602, t23), trigger(603, t31)],
                r1,
                r3,
                expected_rooms=3,
            )

        # The middle region has three distinct cut neighbors, so no unique order.
        a, t1, middle, t2, b, t3, branch = [(x, 0, 0) for x in range(7)]
        branched = geometry(
            [a, t1, middle, t2, b, t3, branch],
            [(a, t1), (t1, middle), (middle, t2), (t2, b), (middle, t3), (t3, branch)],
        )
        with self.assertRaisesRegex(ValueError, "branched or cyclic"):
            extract(
                branched, [trigger(611, t1), trigger(612, t2), trigger(613, t3)], a, b
            )

    def test_trigger_without_two_closed_regions_is_not_a_frontier(self):
        a, gate, b = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        graph = geometry([a, gate, b], [(a, gate), (gate, b)])
        # The selected cell is on the alternate route rather than a cut.
        alternate = geometry(
            [a, gate, b, (1, 1, 0)],
            [(a, gate), (gate, b), (a, (1, 1, 0)), ((1, 1, 0), b)],
        )
        with self.assertRaisesRegex(ValueError, "does not separate terrain"):
            extract(alternate, [trigger(701, gate)], a, b)
        self.assertEqual(
            len(extract(graph, [trigger(702, gate)], a, b)["frontiers"]), 1
        )


if __name__ == "__main__":
    unittest.main()
