"""Owned world updates clear previous sheet contributions without combat changes."""
import copy
import struct
import unittest

from tests import test_equipment_stats
from wakfu_server.combat_lifecycle import outside_progression
from wakfu_server.wire import complete_public_characteristics


def rows(payload):
    count = struct.unpack_from(">H", payload)[0]
    return {
        row[0]: row[1:]
        for row in (
            struct.unpack_from(">Biiii", payload, 2 + index * 17)
            for index in range(count)
        )
    }


def world_rows(body):
    identity, size = struct.unpack_from(">qh", body)
    if size != len(body) - 10:
        raise AssertionError("Invalid native owned envelope")
    blob = body[10:]
    return identity, rows(blob[39:])


class WorldBuildStatResetTests(unittest.TestCase):
    def character(self):
        character = test_equipment_stats.EquipmentStatsTests().character()
        character.update(account_id=2, x=3, y=4, z=0, map_id=1134)
        return character

    def test_actual_equipped_then_empty_updates_clear_removed_mastery_and_critical(
        self,
    ):
        character = self.character()
        before = copy.deepcopy(character)
        first = world_rows(outside_progression(character)[1])[1]
        character["builds"][0]["equipment"] = ""
        second = world_rows(outside_progression(character)[1])[1]
        # Native ffh.b is partial: explicitly present zero/default rows are
        # necessary to overwrite the first message on an existing actor.
        received = dict(first)
        received.update(second)
        self.assertEqual((first[20][0], second[20][0], received[20][0]), (9, 0, 0))
        # The original native critical baseline is3; the amulet contributes2.
        self.assertEqual((first[9][0], second[9][0], received[9][0]), (5, 3, 3))
        self.assertEqual(set(first), set(second))
        self.assertEqual(character["hp"], before["hp"])
        self.assertEqual(character["inventory_items"], before["inventory_items"])

    def test_resource_overrides_initiative_and_wounds_survive_completion(self):
        character = self.character()
        identity, actual = world_rows(
            outside_progression(character, wp=9, ap=4, mp=2)[1]
        )
        self.assertEqual(identity, character["id"])
        self.assertEqual(actual[1][0], 41)
        self.assertEqual(actual[2][:3], (5, 0, 5))  # Override4 + equipped AP1.
        self.assertEqual(actual[3][:3], (2, 0, 2))
        self.assertEqual(actual[4][:3], (9, 0, 9))
        self.assertEqual(actual[35][0], 0)
        payload = struct.pack(">H", 1) + struct.pack(
            ">Biiii", 35, 17, -2147483648, 2147483647, 0
        )
        self.assertEqual(rows(complete_public_characteristics(payload))[35][0], 17)

    def test_native_nonzero_baseline_and_sparse_input_validation(self):
        contribution = struct.pack(">Biiii", 12, 2, -2147483648, 2147483647, 0)
        actual = rows(
            complete_public_characteristics(struct.pack(">H", 1) + contribution)
        )
        self.assertEqual(actual[12][0], 3)  # Native stat12 baseline1 + contribution2.
        for malformed in (
            b"",
            b"\x00",
            struct.pack(">H", 1),
            struct.pack(">H", 2) + contribution + contribution,
            struct.pack(">H", 1) + struct.pack(">Biiii", 255, 1, 0, 1, 0),
        ):
            with self.subTest(payload=malformed), self.assertRaises(ValueError):
                complete_public_characteristics(malformed)
