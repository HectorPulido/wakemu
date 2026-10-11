"""Native exit binding refuses guessed approaches and unsupported costs."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_native_physical_candidates import bind_exits


class PhysicalCandidateExitTests(unittest.TestCase):
    def setUp(self):
        self.topology = dict(
            asset_map_id=99,
            rooms=[dict(order=1, cells=[[0, 0, 0]]), dict(order=2, cells=[[3, 0, 0]])],
        )
        self.route = dict(entry_map_id=10)
        self.sources = [
            dict(
                map_id=99,
                id=i,
                x=x,
                y=0,
                z=0,
                approach_positions=[],
                approach_blocks_center=False,
                destinations=[
                    dict(
                        destination_id=4,
                        map_id=10,
                        x=1,
                        y=1,
                        z=0,
                        native_altitude_walkable=True,
                    )
                ],
            )
            for i, x in ((20, 0), (30, 3))
        ]

    def test_zero_mask_nonblocking_center_binds_both_native_exit_rooms(self):
        bindings = bind_exits(self.topology, self.route, self.sources)
        self.assertEqual(
            [(b["source_id"], b["room_order"]) for b in bindings], [(20, 1), (30, 2)]
        )

    def test_blocked_center_requires_literal_native_approach(self):
        self.sources[0]["approach_blocks_center"] = True
        with self.assertRaises(ValueError):
            bind_exits(self.topology, self.route, self.sources)
        self.sources[0]["approach_positions"] = [dict(x=0, y=0, z=0)]
        self.assertEqual(len(bind_exits(self.topology, self.route, self.sources)), 2)

    def test_ambiguous_entrance_is_not_selected_by_id_or_distance(self):
        duplicate = copy.deepcopy(self.sources[0])
        duplicate["id"] = 21
        with self.assertRaises(ValueError):
            bind_exits(self.topology, self.route, self.sources + [duplicate])

    def test_paid_or_criterion_exit_is_not_activated_implicitly(self):
        for field, value in (
            ("criterion", "Mi=44"),
            ("cyZ", 0),
            ("native_altitude_walkable", False),
        ):
            sources = copy.deepcopy(self.sources)
            sources[1]["destinations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                bind_exits(self.topology, self.route, sources)


class BackwardCompletedExitTests(unittest.TestCase):
    def setUp(self):
        self.topology = dict(
            asset_map_id=99,
            policy="native_teleport_victory_policy",
            rooms=[
                dict(order=i, anchor=[i, 0, 0], cells=[[i, 0, 0]]) for i in (1, 2, 3)
            ],
            exploration_geometry=dict(edges=[]),
            doors=[
                dict(
                    source_id=40,
                    source_room=3,
                    destination_room=2,
                    destination_id=8,
                    source_position=[3, 0, 0],
                    native_approach_cells=[[3, 0, 0]],
                    destination_position=[2, 0, 0],
                )
            ],
        )
        self.route = dict(entry_map_id=10)
        self.sources = [
            dict(
                map_id=99,
                id=i,
                x=x,
                y=0,
                z=0,
                approach_positions=[],
                approach_blocks_center=False,
                destinations=[
                    dict(
                        destination_id=7,
                        map_id=10,
                        x=0,
                        y=0,
                        z=0,
                        native_altitude_walkable=True,
                    )
                ],
            )
            for i, x in ((20, 1), (30, 2))
        ]
        self.sources.append(
            dict(
                map_id=99,
                id=40,
                x=3,
                y=0,
                z=0,
                approach_positions=[],
                approach_blocks_center=False,
                destinations=[
                    dict(
                        destination_id=8,
                        map_id=99,
                        x=2,
                        y=0,
                        z=0,
                        native_altitude_walkable=True,
                    )
                ],
            )
        )

    def test_literal_adjacent_return_proves_intermediate_final_exit(self):
        bindings = bind_exits(self.topology, self.route, self.sources)
        self.assertEqual([b["room_order"] for b in bindings], [1, 2])
        witness = self.topology["completed_exit_witness"]
        self.assertEqual(witness["source_id"], 30)
        self.assertEqual([s["source_id"] for s in witness["steps"]], [40, 30])

    def test_completed_exit_can_return_to_entry_only_via_literal_backward_chain(self):
        self.sources = [s for s in self.sources if s["id"] != 30]
        source = copy.deepcopy(self.sources[-1])
        source.update(id=41, x=2)
        source["destinations"][0].update(destination_id=9, x=1)
        self.sources.append(source)
        self.topology["doors"].append(
            dict(
                source_id=41,
                source_room=2,
                destination_room=1,
                destination_id=9,
                source_position=[2, 0, 0],
                native_approach_cells=[[2, 0, 0]],
                destination_position=[1, 0, 0],
            )
        )
        bindings = bind_exits(self.topology, self.route, self.sources)
        self.assertEqual([b["room_order"] for b in bindings], [1])
        witness = self.topology["completed_exit_witness"]
        self.assertEqual(witness["room_order"], 1)
        self.assertEqual([step["source_id"] for step in witness["steps"]], [40, 41, 20])

    def test_changed_arrival_cannot_be_used_as_a_guessed_return(self):
        self.sources[-1]["destinations"][0]["x"] = 1
        with self.assertRaises(ValueError):
            bind_exits(self.topology, self.route, self.sources)

    def test_criterion_or_nonliteral_approach_blocks_return(self):
        for change in ("criterion", "approach"):
            topology, sources = copy.deepcopy(self.topology), copy.deepcopy(
                self.sources
            )
            if change == "criterion":
                sources[-1]["destinations"][0]["criterion"] = "Mi=44"
            else:
                sources[-1]["approach_blocks_center"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                bind_exits(topology, self.route, sources)

    def test_unreachable_source_has_no_completed_exit_witness(self):
        self.topology["rooms"][-1]["cells"].append([4, 0, 0])
        self.topology["rooms"][-1]["anchor"] = [4, 0, 0]
        with self.assertRaises(ValueError):
            bind_exits(self.topology, self.route, self.sources)
