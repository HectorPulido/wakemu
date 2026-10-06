import unittest
from unittest.mock import patch
from wakfu_server.equipment_stats import (
    bonuses,
    effective_character,
    combat_resources,
    CATALOG,
)
from wakfu_server.wire import proto_field
from wakfu_server.health import maximum


class EquipmentStatsTests(unittest.TestCase):
    def character(self):
        equipment = proto_field(10, proto_field(8, 1000) + proto_field(16, 4)).hex()
        return dict(
            id=1,
            breed=8,
            level=6,
            hp=41,
            max_hp=maximum(8, 6),
            inventory_items=[
                dict(uid=1000, character_id=1, reference=2021, quantity=1)
            ],
            builds={
                0: dict(equipment=equipment, sheet=proto_field(24, (1 << 64) - 1).hex())
            },
        )

    def test_native_amulet_resources_and_stats_without_double_count_or_healing(self):
        char = self.character()
        before = dict(char)
        self.assertEqual(bonuses(char)["stats"], {2: 1, 1: 6, 9: 2, 20: 9})
        resources = combat_resources(char, wp=6)
        self.assertEqual(
            (
                resources["ap"],
                resources["mp"],
                resources["wp"],
                resources["initiative"],
            ),
            (7, 4, 6, 0),
        )
        effective = effective_character(char)
        self.assertEqual(
            (effective["hp"], effective["max_hp"]), (41, maximum(8, 6) + 6)
        )
        self.assertEqual(effective_character(effective)["max_hp"], effective["max_hp"])
        self.assertEqual(char, before)

    def test_unequipping_removes_bonus_and_caps_current_hp_to_base(self):
        char = effective_character(self.character())
        char["hp"] = char["max_hp"]
        char["builds"] = {
            0: dict(equipment="", sheet=proto_field(24, (1 << 64) - 1).hex())
        }
        result = effective_character(char)
        self.assertEqual(
            (result["hp"], result["max_hp"]), (maximum(8, 6), maximum(8, 6))
        )
        self.assertEqual(combat_resources(char, wp=5)["ap"], 6)

    def test_build_ack_precedes_effective_snapshot_and_removal_restores_base(self):
        import struct
        from wakfu_server.builds import response_messages
        from wakfu_server.spells import default_deck

        char = dict(self.character(), account_id=2, x=0, y=0, z=0, map_id=1134)
        char["builds"][0].update(
            sheet=(b"\x08\x00" + proto_field(24, (1 << 64) - 1)).hex(),
            deck=default_deck(char).hex(),
            aptitudes="",
        )

        def stats(packets):
            self.assertEqual(
                [opcode for opcode, _ in packets], [12284, 12393, 12103, 13046]
            )
            outer = packets[-1][1]
            identity, length = struct.unpack_from(">qh", outer)
            self.assertEqual(identity, char["id"])
            self.assertEqual(length, len(outer) - 10)
            blob = outer[10:]
            self.assertEqual(struct.unpack_from(">i", blob, 29)[0], -1)
            offset = 39
            count = struct.unpack_from(">H", blob, offset)[0]
            return {
                entry[0]: entry[1:]
                for entry in (
                    struct.unpack_from(">Biiii", blob, offset + 2 + 17 * i)
                    for i in range(count)
                )
            }

        equipped = stats(response_messages(char, 0, wp=6))
        self.assertEqual(equipped[2], (7, 0, 7, 0))
        self.assertEqual(equipped[1], (41, 0, maximum(8, 6) + 6, 0))
        self.assertEqual(equipped[20][0], 9)
        char["builds"][0]["equipment"] = ""
        removed = stats(response_messages(char, 0, wp=6))
        self.assertEqual(removed[2], (6, 0, 6, 0))
        self.assertEqual(removed[1], (41, 0, maximum(8, 6), 0))
        self.assertNotIn(20, removed)
        self.assertEqual(
            [opcode for opcode, _ in response_messages(char, 0, wp=6, status=7)],
            [12284],
        )

    def test_owned_sheet_validation_precedes_evaluation(self):
        char = self.character()
        for invalid in (
            dict(char, inventory_items=[]),
            dict(char, level=5),
            dict(
                char, inventory_items=[dict(char["inventory_items"][0], character_id=2)]
            ),
        ):
            with self.assertRaises(ValueError):
                bonuses(invalid)
        # Unselected build items must not grant statistics.
        char["builds"][1] = char["builds"].pop(0)
        self.assertEqual(bonuses(char)["stats"], {})
        self.assertEqual(bonuses(char, build_index=1)["stats"][2], 1)

    def test_conditional_trigger_and_unknown_effects_are_reported_without_fake_bonuses(
        self,
    ):
        char = self.character()
        template = CATALOG[2021]
        effect = dict(template["effects"][0], effect_criteria=True)
        with patch.dict(CATALOG, {2021: dict(template, effects=[effect])}):
            result = bonuses(char)
        self.assertEqual(result["stats"], {})
        self.assertEqual(result["unsupported"][0]["effect_id"], 360361)
        with patch.dict(
            CATALOG,
            {
                2021: dict(
                    template,
                    effects=[dict(effect, effect_criteria=False, has_triggers=True)],
                )
            },
        ):
            self.assertEqual(bonuses(char)["stats"], {})
