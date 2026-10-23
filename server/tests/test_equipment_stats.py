import unittest
from unittest.mock import patch
from wakfu_server.equipment_stats import (
    bonuses,
    effective_character,
    combat_resources,
    CATALOG,
    _flat,
)
from wakfu_server.wire import proto_field
from wakfu_server.health import maximum


class EquipmentStatsTests(unittest.TestCase):
    def test_actual_npc_baseline_replays_eWW_flat_at_native_characteristic_bounds(self):
        from wakfu_server.combat.combat_actor_snapshot import native_npc_creation_values
        from wakfu_server.combat.combat_companions import COMPANION_BREEDS
        from wakfu_server.equipment_characteristics import native_rows, replay
        from wakfu_server.equipment_stats import dynamic_scalar_bonus

        effects = [
            effect
            for reference in (29115, 29116)
            for effect in CATALOG[reference]["effects"]
            if dynamic_scalar_bonus(effect) is not None
        ]
        self.assertTrue(effects)
        rows = native_rows()
        cases = []
        observed = []
        for breed in sorted(COMPANION_BREEDS):
            for level in (1, 50, 125, 200, 245):
                try:
                    profile = native_npc_creation_values(breed, level)
                except ValueError:
                    continue
                for effect in effects:
                    identity, amount = dynamic_scalar_bonus(effect)
                    native_value = profile[identity]["current"]
                    row = rows[identity]
                    observed.append(
                        (
                            row["maximum"] - native_value,
                            breed,
                            level,
                            identity,
                            amount,
                            native_value,
                            row["maximum"],
                        )
                    )
                    if (
                        native_value <= row["maximum"]
                        and native_value + amount > row["maximum"]
                    ):
                        cases.append(
                            (breed, level, identity, amount, native_value, row)
                        )
        # Use a real breed/level baseline and actual eWQ39 amount. None of the
        # published companion profiles currently sits close enough to the
        # PC120/121 ceiling to clip; the assertion still proves the NPC path
        # replays against its native baseline rather than the player default.
        self.assertTrue(
            observed, "expected actual companion NPC characteristic profiles"
        )
        gap, breed, level, identity, amount, native_value, maximum = min(observed)
        row = rows[identity]
        self.assertEqual(
            replay(
                [(identity, amount, False)],
                {identity},
                baseline={identity: native_value},
            )[identity],
            min(maximum, native_value + amount) - native_value,
        )

    def test_native_generic192_wp_passives_are_narrowly_bound_and_projected(self):
        rows = [
            effect
            for item in CATALOG.values()
            for effect in item["effects"]
            if effect.get("generic") == 192 and effect.get("runner") == "eWO"
        ]
        self.assertEqual(len(rows), 53)
        self.assertEqual({effect["values"][0] for effect in rows}, {1, 2, 3})
        for effect in rows:
            with self.subTest(effect_id=effect["id"]):
                self.assertEqual(effect["stat_id"], -1)
                self.assertEqual(_flat(effect), (4, -effect["values"][0]))

        representative = rows[0]
        for changed in (
            dict(representative, values=[-1]),
            dict(representative, parameter_count=2),
            dict(representative, effect_criteria=True),
            dict(representative, has_triggers=True),
            dict(representative, target_mask=1),
            dict(representative, runner="eWQ"),
            dict(representative, generic=191),
            dict(representative, native_variant=1),
            dict(representative, native_active_effect=True),
        ):
            with self.subTest(changed=changed):
                self.assertIsNone(_flat(changed))

    def test_native_eWW_dynamic_flat_catalog_and_fail_closed_resource_rows(self):
        from wakfu_server.equipment_characteristics import native_rows
        from wakfu_server.equipment_stats import dynamic_scalar_bonus

        rows = [
            effect
            for item in CATALOG.values()
            for effect in item["effects"]
            if effect.get("generic") == 39 and effect.get("runner") == "eWQ"
        ]
        qualified = [
            effect for effect in rows if dynamic_scalar_bonus(effect) is not None
        ]
        rejected = [effect for effect in rows if dynamic_scalar_bonus(effect) is None]
        self.assertEqual(len(rows), 218)
        self.assertEqual(len(qualified), 216)
        self.assertEqual(len(rejected), 2)

        characteristics = native_rows()
        for effect in qualified:
            with self.subTest(effect_id=effect["id"]):
                identity, amount = dynamic_scalar_bonus(effect)
                self.assertEqual(identity, effect["values"][2])
                self.assertEqual(amount, effect["values"][0])
                self.assertIn(identity, (120, 121))
                row = characteristics[identity]
                self.assertFalse(row["expandable"])
                self.assertFalse(row["frozen"])

        # Native item 30031 combines supported armor-given/received flats with
        # two HP-only roots. The whole item remains unsupported; only its two
        # armor roots qualify through this equipment path.
        mixed = CATALOG[30031]["effects"]
        armor = [
            effect
            for effect in mixed
            if effect.get("generic") == 39
            and effect.get("runner") == "eWQ"
            and dynamic_scalar_bonus(effect) is not None
        ]
        hp = [
            effect
            for effect in mixed
            if effect.get("generic") == 39
            and effect.get("runner") == "eWQ"
            and dynamic_scalar_bonus(effect) is None
        ]
        self.assertEqual(len(armor), 2)
        self.assertEqual(len(hp), 2)
        self.assertEqual({effect["values"][2] for effect in hp}, {1})

        sample = qualified[0]
        malformed = (
            dict(sample, parameter_count=2),
            dict(sample, values=[sample["values"][0], 1, sample["values"][2]]),
            dict(sample, values=[-1, 0, sample["values"][2]]),
            dict(sample, values=[True, 0, sample["values"][2]]),
            dict(sample, values=[sample["values"][0], 0, 1]),
            dict(sample, values=[sample["values"][0], 0, 999]),
            dict(sample, effect_criteria=True),
            dict(sample, has_triggers=True),
            dict(sample, target_mask=1),
            dict(sample, native_variant=1),
            dict(sample, native_active_effect=True),
            dict(sample, generic=38),
        )
        for candidate in malformed:
            with self.subTest(candidate=candidate):
                self.assertIsNone(dynamic_scalar_bonus(candidate))

    def test_false_criterion_positive_effect_is_absent_from_public_raw_projection(self):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_equipment_passive_completeness import (
            unplanned_passive_effect_ids,
        )
        from wakfu_server.equipment import RULES
        from wakfu_server.equipment_stats import inactive_passive_root
        from wakfu_server.wire import proto_field

        native = native_copied_equipment_catalog()
        candidate = None
        for raw_reference in native["definitions"]:
            reference = int(raw_reference)
            template = CATALOG.get(reference)
            slots = RULES.get(reference, {}).get("slots", ())
            if template is None or not slots:
                continue
            parent = copied_equipment_plan(reference, native)
            false_ids = {
                root["reference"]
                for root in parent["roots"]
                if root.get("criterion_raw") == "False"
            }
            identities = {effect["id"]: effect for effect in template["effects"]}
            for effect_id in false_ids:
                effect = identities[effect_id]
                candidate = reference, slots[0], effect, false_ids
                break
            if candidate:
                break

        self.assertIsNotNone(
            candidate, "catalog should expose a literal-False equipped item"
        )
        reference, slot, effect, false_ids = candidate
        uid = 987654321
        character = dict(
            id=1,
            breed=8,
            level=200,
            active_build_index=0,
            hp=1000,
            max_hp=1000,
            inventory_items=[
                dict(uid=uid, character_id=1, reference=reference, quantity=1)
            ],
            builds={
                0: dict(
                    sheet=proto_field(24, 200).hex(),
                    equipment=proto_field(
                        10, proto_field(8, uid) + proto_field(16, slot)
                    ).hex(),
                    aptitudes="",
                )
            },
        )
        parent = copied_equipment_plan(reference, native)
        omitted = unplanned_passive_effect_ids(reference, parent, (), templates=CATALOG)
        self.assertNotIn(effect["id"], omitted)
        native_root = next(
            root for root in parent["roots"] if root["reference"] == effect["id"]
        )
        self.assertTrue(
            any(
                type(value) in (int, float) and value > 0
                for value in native_root["parameters"]
            )
        )
        self.assertTrue(inactive_passive_root(reference, effect))
        actual = bonuses(character)
        self.assertFalse(
            any(row.get("effect_id") in false_ids for row in actual["unsupported"])
        )
        changed_catalog = dict(CATALOG)
        changed_catalog[reference] = dict(
            CATALOG[reference],
            effects=[
                row
                for row in CATALOG[reference]["effects"]
                if row["id"] not in false_ids
            ],
        )
        with patch("wakfu_server.equipment_stats.CATALOG", changed_catalog):
            without_false_roots = bonuses(character)
        self.assertEqual(actual, without_false_roots)

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

    def test_equipped_dragopavo_effect_scales_by_pet_level_only(self):
        pet_uid = 18682
        equipment = proto_field(10, proto_field(8, pet_uid) + proto_field(16, 24)).hex()
        pet = dict(
            uid=pet_uid,
            character_id=1,
            reference=18682,
            quantity=1,
            mount={"model_id": 76, "definition_id": 76, "xp": 0},
        )
        char = dict(self.character(), level=50, inventory_items=[pet])
        char["builds"] = {
            0: dict(
                equipment=equipment,
                sheet=proto_field(24, (1 << 64) - 1).hex(),
            )
        }

        for level, expected_damage in ((0, 0), (1, 0), (2, 1), (35, 28), (50, 40)):
            with self.subTest(level=level):
                pet["mount"]["xp"] = level * 50
                result = bonuses(char)
                self.assertEqual(result["stats"], {20: expected_damage})
                self.assertEqual(result["unsupported"], [])

        # An owned but unequipped Dragopavo must not change the passive values
        # supplied by unrelated ordinary equipment as its XP changes.
        ordinary = self.character()
        ordinary["inventory_items"].append(pet)
        baseline = bonuses(ordinary)["stats"]
        for xp in (0, 2500):
            pet["mount"]["xp"] = xp
            self.assertEqual(bonuses(ordinary)["stats"], baseline)

    def test_null_equipment_marker_does_not_hide_conditional_or_unknown_variants(self):
        from wakfu_server.equipment_stats import passive_null_marker

        marker = next(
            effect for effect in CATALOG[18682]["effects"] if effect["id"] == 119215
        )
        self.assertTrue(passive_null_marker(marker))
        for altered in (
            dict(marker, has_triggers=True),
            dict(marker, effect_criteria=True),
            dict(marker, target_mask=1),
            dict(marker, runner="unknown"),
            dict(marker, parameter_count=1, params=[1.0, 0.0], values=[1]),
        ):
            self.assertFalse(passive_null_marker(altered))
            char = self.character()
            with patch.dict(CATALOG, {2021: dict(CATALOG[2021], effects=[altered])}):
                self.assertEqual(bonuses(char)["unsupported"][0]["effect_id"], 119215)

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
            self.assertEqual([opcode for opcode, _ in packets], [12284, 12103, 13046])
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
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        baseline = native_actor_catalog()["characteristics"]["20"]
        # The native partial consumer needs an explicit baseline to clear the
        # removed equipment contribution; an omitted row can retain old damage.
        self.assertEqual(
            removed[20],
            (baseline["current"], baseline["minimum"], baseline["maximum"], 0),
        )
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
