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

    def test_native_shard_effect_level_and_matching_equipment_family(self):
        char = self.character()
        from wakfu_server.wire import proto_field

        # Add a low-level head item to the active sheet.
        hat = dict(uid=1001, character_id=1, reference=6823, quantity=1)
        char["inventory_items"].append(hat)
        head = proto_field(10, proto_field(8, 1001) + proto_field(16, 0))
        char["builds"][0]["equipment"] = (
            bytes.fromhex(char["builds"][0]["equipment"]) + head
        ).hex()
        baseline = bonuses(char)["stats"]

        # Native ProtoShard slot: position 0, shard ref 27109, non-empty color,
        # slot level 3 -> effective level 2. Its family includes HEAD (0),
        # matching the hat's validated equipment slot; the level-2 native
        # value is 8 HP and the native family match doubles it.
        slot = (
            proto_field(80, 0)
            + proto_field(88, 27109)
            + proto_field(96, 1)
            + proto_field(112, 3)
        )
        hat["shard_state"] = proto_field(10, slot)
        self.assertEqual(bonuses(char)["stats"][1] - baseline[1], 16)

        # fpG.WA saturates for values above its final native threshold. A
        # signed-int32 wire value still maps to that same final effect level.
        slot = (
            proto_field(80, 0)
            + proto_field(88, 27109)
            + proto_field(96, 1)
            + proto_field(112, 2**31 - 1)
        )
        hat["shard_state"] = proto_field(10, slot)
        self.assertEqual(bonuses(char)["stats"][1] - baseline[1], 176)

        negative_level = b"\x70\xff\xff\xff\xff\x0f"
        slot = (
            proto_field(80, 0)
            + proto_field(88, 27109)
            + proto_field(96, 1)
            + negative_level
        )
        hat["shard_state"] = proto_field(10, slot)
        with self.assertRaises(ValueError):
            bonuses(char)

    def test_nonmatching_family_adds_once_and_empty_color_adds_nothing(self):
        char = self.character()
        item = char["inventory_items"][0]
        from wakfu_server.wire import proto_field

        slot = (
            proto_field(80, 0)
            + proto_field(88, 27094)
            + proto_field(96, 1)
            + proto_field(112, 0)
        )
        item["shard_state"] = proto_field(10, slot)
        # 27094 targets CHEST/BACK, not this NECK equipment slot.
        self.assertEqual(bonuses(char)["stats"][20], 10)

        slot = (
            proto_field(80, 0)
            + proto_field(88, 27094)
            + proto_field(96, 0)
            + proto_field(112, 0)
        )
        item["shard_state"] = proto_field(10, slot)
        self.assertEqual(bonuses(char)["stats"][20], 9)

    def test_malformed_native_socket_positions_and_colors_fail_closed(self):
        from wakfu_server.shard_bonuses import bonuses as shard_bonuses

        item = dict(uid=1001, reference=6823)

        def slot(position, color=1, reference=27109, level=0):
            return proto_field(
                10,
                proto_field(80, position)
                + proto_field(88, reference)
                + proto_field(96, color)
                + proto_field(112, level),
            )

        item["shard_state"] = slot(0) + slot(0)
        with self.assertRaisesRegex(ValueError, "positions"):
            shard_bonuses(item, 0)

        item["shard_state"] = slot(0, color=99)
        with self.assertRaisesRegex(ValueError, "color enum"):
            shard_bonuses(item, 0)

        item["shard_state"] = b"".join(slot(position) for position in range(5))
        with self.assertRaisesRegex(ValueError, "position"):
            shard_bonuses(item, 0)

    def test_socket_effect_is_independent_of_host_effect_catalog_row(self):
        char = self.character()
        item = char["inventory_items"][0]
        from wakfu_server.wire import proto_field

        slot = (
            proto_field(80, 0)
            + proto_field(88, 27110)
            + proto_field(96, 1)
            + proto_field(112, 0)
        )
        item["shard_state"] = proto_field(10, slot)
        with patch.dict(CATALOG, {2021: None}):
            result = bonuses(char)
        self.assertEqual(result["stats"][18], 2)
