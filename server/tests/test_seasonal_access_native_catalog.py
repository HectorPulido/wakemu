"""Read-only regression against the published native event entrance bindings."""
import unittest

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.maps import seasonal_access


class SeasonalNativeCatalogTests(unittest.TestCase):
    def test_reviewed_windows_and_native_menu_filter_flags_match_catalog(self):
        sources = native_catalog.load(DATA_ROOT / "native-generic-teleporters.json")
        bindings = {
            443: (527, 20179, 955, False, False),
            1075: (458, 26727, 2482, False, False),
            146: (235, 18012, 4810, True, True),
        }
        for map_id, (
            source_map,
            identity,
            destination_id,
            cvd,
            cy_y,
        ) in bindings.items():
            with self.subTest(map_id=map_id):
                source = next(
                    row
                    for row in sources
                    if (row["map_id"], row["id"]) == (source_map, identity)
                )
                destination = next(
                    row
                    for row in source["destinations"]
                    if row["destination_id"] == destination_id
                )
                self.assertEqual(destination["map_id"], map_id)
                self.assertEqual(
                    destination["criterion"].count(
                        seasonal_access.EVENT_WINDOWS[map_id]
                    ),
                    1,
                )
                self.assertIs(destination["cvd"], cvd)
                self.assertIs(destination["cyY"], cy_y)


if __name__ == "__main__":
    unittest.main()
