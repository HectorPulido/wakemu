import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from contract_dungeon_transit_regions import contract


class TransitRegionTests(unittest.TestCase):
    def topology(self):
        return dict(
            rooms=[
                dict(
                    order=i, anchor=[i, 0, 0], cells=[[i, 0, 0]] * (1 if i == 3 else 2)
                )
                for i in range(1, 5)
            ],
            physical_doors=[
                dict(source_id=i, source_room=i, destination_room=i + 1)
                for i in range(1, 4)
            ],
            physical_exit_objects=[dict(room_order=4)],
        )

    def test_preserves_gates_and_merges_transit_downstream(self):
        original = self.topology()
        result = contract(original)
        self.assertEqual(len(original["rooms"]), 4)
        self.assertEqual(len(result["rooms"]), 3)
        self.assertEqual(
            [
                (d["source_room"], d["destination_room"])
                for d in result["physical_doors"]
            ],
            [(1, 2), (2, 3), (2, 3)],
        )
        self.assertIn([3, 0, 0], result["rooms"][2]["cells"])
        self.assertEqual(result["physical_exit_objects"][0]["room_order"], 3)

    def test_refuses_branch(self):
        topology = self.topology()
        topology["physical_doors"].append(dict(source_room=1, destination_room=3))
        with self.assertRaises(ValueError):
            contract(topology)

    def test_never_contracts_first_or_final_room(self):
        topology = self.topology()
        topology["rooms"][0]["cells"] = [[1, 0, 0]]
        topology["rooms"][-1]["cells"] = [[4, 0, 0]]
        result = contract(topology)
        self.assertEqual(result["rooms"][0]["anchor"], [1, 0, 0])
        self.assertEqual(result["rooms"][-1]["anchor"], [4, 0, 0])
