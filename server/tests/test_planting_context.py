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

    def test_wrong_native_region_does_not_enable_wonejo(self):
        with self.assertRaises(ValueError):
            context.authorize_family(1134, 79001, RESOURCES[823])
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

    def test_explicit_open_policy_family_does_not_change_native_catalog(self):
        packet = context.bootstrap(1134, 79101, test_monster_families=(81,))
        count = struct.unpack_from(">i", packet[1], 8)[0]
        self.assertEqual(count, 3)
        self.assertNotIn(
            81,
            {f["family_id"] for f in context.region(1134, 79101)["monster_families"]},
        )

    def test_open_families_are_suitable_native_species(self):
        from wakfu_server.planting_cells import open_families

        self.assertIn(81, open_families(1134, 79101))
        self.assertIn(68, open_families(1134, 79101))
