import struct
import unittest
from tests import test_equipment_stats
from wakfu_server.combat_lifecycle import outside_progression
from wakfu_server.health import maximum


class EquipmentReturnTests(unittest.TestCase):
    def test_outside_refresh_retains_owned_equipment_resources_and_wounds(self):
        character = test_equipment_stats.EquipmentStatsTests().character()
        character.update(account_id=2, x=3, y=4, z=0, map_id=1134)
        opcode, body = outside_progression(character, wp=6)
        self.assertEqual(opcode, 13046)
        self.assertEqual(struct.unpack_from(">q", body)[0], character["id"])
        self.assertEqual(struct.unpack_from(">h", body, 8)[0], len(body) - 10)
        body = body[:8] + body[10:]
        self.assertEqual(body[8], 3)
        self.assertEqual(struct.unpack_from(">i", body, 37)[0], -1)
        offset = 47
        count = struct.unpack_from(">H", body, offset)[0]
        stats = {}
        for i in range(count):
            key, current, minimum, maximum_value, bonus = struct.unpack_from(
                ">Biiii", body, offset + 2 + i * 17
            )
            stats[key] = (current, maximum_value)
        self.assertEqual(
            stats[1], (41, maximum(character["breed"], character["level"]) + 6)
        )
        self.assertEqual(stats[2], (7, 7))
        # Breed 8 has four native MP; this amulet adds no MP.
        self.assertEqual(stats[3], (4, 4))
        self.assertEqual(stats[4], (6, 6))
        self.assertEqual(
            character["max_hp"], maximum(character["breed"], character["level"])
        )
        self.assertEqual(character["inventory_items"][0]["uid"], 1000)

    def test_unequipped_refresh_has_base_resources(self):
        character = test_equipment_stats.EquipmentStatsTests().character()
        character.update(account_id=2, x=3, y=4, z=0, map_id=1134, builds={})
        _, body = outside_progression(character, wp=5)
        body = body[:8] + body[10:]
        # First stat isHP, second isAP: typed native PC current/min/max tuple.
        self.assertEqual(struct.unpack_from(">Biiii", body, 49 + 17)[:2], (2, 6))
