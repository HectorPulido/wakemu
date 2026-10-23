import struct
import unittest
from wakfu_server import planting_context as context
from wakfu_server.planting import RESOURCES


class ContextTests(unittest.TestCase):
    def test_native_wonejo_region_present_zero_population(self):
        opcode, body = context.bootstrap(1385, 93601)
        self.assertEqual(opcode, 12789)
        region, length = struct.unpack_from(">ii", body)
        self.assertEqual((region, length), (93601, 12))
        self.assertEqual(struct.unpack_from(">iii", body, 8), (1, 1113, 0))
        context.authorize_family(1385, 93601, RESOURCES[823])

    def test_non_native_families_can_be_planted_without_changing_region_display(self):
        for resource in RESOURCES.values():
            with self.subTest(resource=resource["resource_reference"]):
                context.authorize_family(1134, 79001, resource)
        with self.assertRaises(ValueError):
            context.bootstrap(1134, 93601)

    def test_local_population_and_invalid_foreign_family(self):
        body = context.bootstrap(1385, 93601, monster_counts={1113: 4})[1]
        self.assertEqual(struct.unpack_from(">iii", body, 8), (1, 1113, 4))
        with self.assertRaises(ValueError):
            context.bootstrap(1385, 93601, monster_counts={68: 5})
        with self.assertRaises(ValueError):
            context.bootstrap(1385, 93601, monster_counts={1113: -1})


class NativeSurfaceTests(unittest.TestCase):
    def test_planting_foreign_region_keeps_surface_and_occupation_checks(self):
        from unittest.mock import MagicMock, patch
        from wakfu_server import planting_cells

        store = MagicMock()
        db = store.connection.return_value.__enter__.return_value
        db.execute.return_value.fetchone.return_value = None
        character = {"map_id": 1134, "instance_id": 0}
        request = {"x": 3, "y": 4}
        surfaces = {(3, 4): [dict(z=0, ground_id=681, region_id=79001)]}
        with patch.object(planting_cells, "cells", return_value=surfaces), patch.object(
            planting_cells, "suitability", return_value=1
        ):
            self.assertEqual(
                planting_cells.authorize(
                    store, character, request, None, RESOURCES[823]
                ),
                0,
            )
            db.execute.return_value.fetchone.return_value = {"occupied": 1}
            with self.assertRaises(ValueError):
                planting_cells.authorize(
                    store, character, request, None, RESOURCES[823]
                )
            surfaces[(3, 4)] = []
            with self.assertRaises(ValueError):
                planting_cells.authorize(
                    store, character, request, None, RESOURCES[823]
                )

    def test_exact_native_region_and_ground(self):
        from wakfu_server.planting_cells import surface, cells, suitability

        native = surface(1385, 3, -13, 1)
        self.assertEqual(native["region_id"], 93601)
        self.assertEqual(native["ground_id"], 0)
        self.assertEqual(suitability(681, RESOURCES[823]), 1)
        self.assertEqual(suitability(681, RESOURCES[192]), 0)
        territories = {
            v["region_id"] for values in cells(1134).values() for v in values
        }
        self.assertTrue({79301, 79001, 79101, 79201}.issubset(territories))

    def test_unknown_height_rejected(self):
        from wakfu_server.planting_cells import surface

        with self.assertRaises(ValueError):
            surface(1385, 3, -13, 32767)

    def test_foreign_test_family_cannot_overflow_native_display(self):
        with self.assertRaises(ValueError):
            context.bootstrap(1134, 79101, test_monster_families=(81,))

    def test_open_permissions_preserve_regional_family_list_and_counts(self):
        from wakfu_server.planting_cells import region_context

        character = {"map_id": 1134}
        kwargs = {"monster_counts": {113: 7, 219: 9, 81: 100, 952: 20}}
        normal = region_context(character, 79101, **kwargs)
        opened = region_context(character, 79101, open_test_policy=True, **kwargs)
        self.assertEqual(normal, opened)
        self.assertEqual(
            struct.unpack_from(">iiiii", opened[1], 8), (2, 113, 7, 219, 9)
        )

    def test_all_native_regions_fit_named_unique_display_slots(self):
        for map_id, world in context.MAPS.items():
            for region in world["regions"]:
                with self.subTest(map_id=map_id, region_id=region["region_id"]):
                    body = context.bootstrap(map_id, region["region_id"])[1]
                    offset = 4
                    for kind in ("monster", "plant"):
                        length = struct.unpack_from(">i", body, offset)[0]
                        offset += 4
                        count = struct.unpack_from(">i", body, offset)[0]
                        self.assertLessEqual(count, 3)
                        self.assertEqual(length, 4 + 8 * count)
                        rows = [
                            struct.unpack_from(">ii", body, offset + 4 + 8 * i)
                            for i in range(count)
                        ]
                        expected = list(
                            dict.fromkeys(
                                r["family_id"]
                                for r in region[kind + "_families"]
                                if r["family_id"] > 0
                            )
                        )
                        self.assertEqual(rows, [(family, 0) for family in expected])
                        offset += length
                    self.assertEqual(offset, len(body))

    def test_empty_native_sentinel_is_not_an_unnamed_family(self):
        body = context.bootstrap(1365, 92601)[1]
        self.assertEqual(struct.unpack_from(">iii", body, 8), (1, 1106, 0))

    def test_duplicate_catalog_family_is_encoded_once_and_overflow_rejected(self):
        from unittest.mock import patch

        definition = {
            "monster_families": [{"family_id": f} for f in (113, 113, 219)],
            "plant_families": [],
        }
        with patch.object(context, "region", return_value=definition):
            body = context.bootstrap(1, 1, monster_counts={113: 8})[1]
            self.assertEqual(struct.unpack_from(">iiiii", body, 8), (2, 113, 8, 219, 0))
            definition["monster_families"] = [{"family_id": f} for f in (1, 2, 3, 4)]
            with self.assertRaises(ValueError):
                context.bootstrap(1, 1)

    def test_every_display_family_has_installed_native_localized_name(self):
        import zipfile
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        families = {
            kind: {
                family
                for world in context.MAPS.values()
                for region in world["regions"]
                for family in context.display_families(region, kind)
            }
            for kind in ("monster", "plant")
        }
        for locale in ("en", "es", "fr", "pt"):
            with zipfile.ZipFile(
                root / "client" / "contents" / "i18n" / ("i18n_" + locale + ".jar")
            ) as archive:
                content = archive.read("texts_" + locale + ".properties").decode("utf8")
            names = dict(
                line.split("=", 1) for line in content.splitlines() if "=" in line
            )
            for kind, table in (("monster", 38), ("plant", 37)):
                for family in families[kind]:
                    with self.subTest(locale=locale, kind=kind, family=family):
                        self.assertTrue(
                            names.get(f"content.{table}.{family}", "").strip()
                        )
