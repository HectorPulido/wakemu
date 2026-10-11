"""Mandatory-gate local stages must retain annexes and reject progression bypasses."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_native_branch_spine import build


def fixture():
    cells = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [0, 2, 0]]
    pairs = [
        (cells[0], cells[1]),
        (cells[1], cells[2]),
        (cells[0], cells[3]),
        (cells[3], cells[4]),
    ]
    geometry = dict(
        map_id=1, cells=cells, edges=[e for a, b in pairs for e in ([a, b], [b, a])]
    )
    doors = [
        dict(id=10, type="Door", x=1, y=0, z=0),
        dict(id=20, type="Door", x=0, y=1, z=0),
    ]
    return geometry, doors


class NativeBranchSpineTest(unittest.TestCase):
    def test_annex_retains_native_cells_and_gate_without_extra_encounter(self):
        geometry, doors = fixture()
        topology = build(geometry, doors, [0, 0, 0], [2, 0, 0])
        self.assertEqual(len(topology["rooms"]), 2)
        self.assertEqual(topology["exploration_geometry"], geometry)
        self.assertEqual({d["source_id"] for d in topology["physical_doors"]}, {10, 20})
        annex = next(d for d in topology["physical_doors"] if d["source_id"] == 20)
        self.assertEqual((annex["source_room"], annex["destination_room"]), (1, 1))
        self.assertIn([0, 2, 0], topology["rooms"][0]["cells"])
        self.assertEqual(
            topology["local_mainspine_evidence"]["mandatory_gate_ids"], [10]
        )
        from wakfu_server.dungeon_physical_doors import blocked_cells

        self.assertEqual(blocked_cells(topology, 1), frozenset({(1, 0, 0)}))
        self.assertEqual(blocked_cells(topology, 2), frozenset())

    def test_directed_bypass_cannot_be_a_locked_stage(self):
        geometry, doors = fixture()
        geometry["edges"].extend([[[0, 0, 0], [2, 0, 0]], [[2, 0, 0], [0, 0, 0]]])
        with self.assertRaisesRegex(ValueError, "No mandatory native gate"):
            build(geometry, doors, [0, 0, 0], [2, 0, 0])

    def test_parallel_native_gates_form_one_required_frontier(self):
        geometry, doors = fixture()
        geometry["edges"].extend([[[0, 2, 0], [2, 0, 0]], [[2, 0, 0], [0, 2, 0]]])
        topology = build(geometry, doors, [0, 0, 0], [2, 0, 0])
        self.assertEqual(
            topology["local_mainspine_evidence"]["mandatory_gate_groups"], [[10, 20]]
        )
        from wakfu_server.dungeon_physical_doors import blocked_cells

        self.assertEqual(blocked_cells(topology, 1), frozenset({(1, 0, 0), (0, 1, 0)}))

    def test_deepest_stage_uses_native_regions_and_retains_annexes(self):
        from build_native_branch_spine import deepest_native_stage

        geometry, doors = fixture()
        topology = deepest_native_stage(geometry, doors, [0, 0, 0])
        self.assertEqual(len(topology["rooms"]), 2)
        self.assertEqual(topology["exploration_geometry"], geometry)
        self.assertIn("final_stage_selection", topology["local_mainspine_evidence"])

    def test_physical_return_requires_literal_free_native_exit(self):
        from prepare_native_physical_candidates import bind_exits

        geometry, doors = fixture()
        topology = build(geometry, doors, [0, 0, 0], [2, 0, 0])
        source = dict(
            map_id=1,
            id=100,
            x=0,
            y=0,
            z=0,
            approach_positions=[dict(x=0, y=0, z=0)],
            approach_blocks_center=False,
            destinations=[
                dict(
                    map_id=2,
                    x=10,
                    y=10,
                    z=0,
                    destination_id=200,
                    criterion="",
                    cyZ=-1,
                    cyX=0,
                    cyW=0,
                    native_altitude_walkable=True,
                )
            ],
        )
        bindings = bind_exits(
            topology, dict(entry_map_id=2), [source], allow_physical_return=True
        )
        self.assertEqual(len(bindings), 1)
        witness = topology["completed_exit_witness"]
        self.assertEqual(witness["kind"], "physical_return_walk")
        self.assertEqual(
            tuple(witness["walking_path"][0]), tuple(topology["rooms"][-1]["anchor"])
        )
        self.assertEqual(tuple(witness["walking_path"][-1]), (0, 0, 0))

    def test_undirected_connection_is_not_directed_exit_authority(self):
        geometry, doors = fixture()
        geometry["edges"] = [
            edge for edge in geometry["edges"] if edge != [[1, 0, 0], [2, 0, 0]]
        ]
        with self.assertRaisesRegex(ValueError, "directed-reachable"):
            build(geometry, doors, [0, 0, 0], [2, 0, 0])

    def test_unwalkable_literal_exit_is_not_snapped(self):
        geometry, doors = fixture()
        with self.assertRaisesRegex(ValueError, "outside a closed region"):
            build(geometry, doors, [0, 0, 0], [3, 0, 0])


if __name__ == "__main__":
    unittest.main()
