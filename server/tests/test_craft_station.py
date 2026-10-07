import json
import tempfile
import unittest
from pathlib import Path

from wakfu_server import world_static
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.craft_station import load_interactions, resolve
from wakfu_server.items.craft_catalog import load_catalog


class CraftStationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def test_native_table_uses_exact_mask_and_orientation_candidate(self):
        table_id = 31515
        character = dict(map_id=1134, instance_id=0, x=-19, y=10, z=-4)
        station = resolve(
            character,
            table_id,
            self.catalog,
            objects=world_static.objects,
            geometry=map_geometry,
        )
        self.assertEqual(
            {
                "table_uid": table_id,
                "map_id": 1134,
                "instance_id": 0,
                "definition_id": 113,
                "profession_id": 73,
                "in_range": True,
                "position": (-20, 10, -4),
            },
            station,
        )

    def test_rejects_cells_outside_exact_mask_even_if_adjacent(self):
        # This table faces SOUTH_EAST with FRONT-only mask1, so its only native
        # interaction candidate is (-19,10,-4). (-20,9,-4) is walkable but not
        # authorized by the native table mask.
        character = dict(map_id=1134, instance_id=0, x=-20, y=9, z=-4)
        with self.assertRaisesRegex(ValueError, "not reachable"):
            resolve(
                character,
                31515,
                self.catalog,
                objects=world_static.objects,
                geometry=map_geometry,
            )

    def test_rejects_wrong_instance_unknown_table_and_catalog_object_mismatch(self):
        character = dict(map_id=1134, instance_id=0, x=-19, y=10, z=-4)
        for changed, table_id in (
            (dict(character, instance_id=1), 31515),
            (character, 999999),
        ):
            with self.subTest(changed=changed, table_id=table_id), self.assertRaises(
                ValueError
            ):
                resolve(
                    changed,
                    table_id,
                    self.catalog,
                    objects=world_static.objects,
                    geometry=map_geometry,
                )

        bad_objects = lambda _map: [
            dict(id=31515, type="CraftTable", x=-19, y=10, z=-4)
        ]
        with self.assertRaisesRegex(ValueError, "position is inconsistent"):
            resolve(
                character,
                31515,
                self.catalog,
                objects=bad_objects,
                geometry=map_geometry,
            )

    def test_interaction_export_is_complete_and_rejects_truncated_rows(self):
        interactions = load_interactions()
        self.assertEqual(len(interactions), 330)
        self.assertEqual(sum(len(row["cells"]) for row in interactions.values()), 457)
        self.assertEqual(interactions[(1134, 31515)]["interaction_mask"], 1)
        self.assertEqual(interactions[(1134, 31515)]["facing"], "SOUTH_EAST")
        self.assertEqual(interactions[(1134, 31515)]["cells"], ((-19, 10, -4),))

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "partial.json"
            path.write_text(
                json.dumps({"schema_version": 1, "row_count": 330, "instances": []})
            )
            with self.assertRaisesRegex(
                ValueError, "Incomplete native crafting interaction export"
            ):
                load_interactions(path)

    def test_every_native_filtered_cell_matches_its_static_map_export(self):
        interactions = load_interactions()
        by_map = {}
        for (map_id, _), row in interactions.items():
            by_map.setdefault(map_id, set()).update(row["cells"])
        self.assertEqual(sum(len(row["cells"]) for row in interactions.values()), 457)
        for map_id, cells in by_map.items():
            with self.subTest(map_id=map_id):
                walkable = {tuple(cell) for cell in map_geometry(map_id)["cells"]}
                self.assertTrue(cells.issubset(walkable))


if __name__ == "__main__":
    unittest.main()
