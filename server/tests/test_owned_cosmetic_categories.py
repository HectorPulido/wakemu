"""Native singleton cosmetic categories preserve each other and finisher presets."""
import struct
import unittest
from wakfu_server.characters.cosmetics import (
    OwnedCosmetics,
    actor_component,
    finisher_request,
)
from wakfu_server.wire import proto_field
from wakfu_server.combat_cosmetic_conditions import (
    fresh_player_cosmetic_state,
    NativeCosmeticState,
    has_active_cosmetic,
)


class CosmeticCategoryTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 42,
            "account_id": 7,
            "level": 20,
            "active_build_index": 0,
            "builds": {},
        }
        self.record = OwnedCosmetics(
            7,
            (
                (3, 9727, 0, 0),
                (4, 20820, 0, 0),
                (6, 18299, 0, 0),
                (6, 18300, 0, 0),
                (5, 20753, 0, 0),
            ),
        )
        self.record = self.record.equip_finishers(
            self.character, (20753,)
        ).equip_costume(self.character, 9727)

    def request(self, record, category, reference, add=True):
        return finisher_request(
            record,
            self.character,
            13765,
            struct.pack(">iiBB", 1, category, int(add), 1) + proto_field(8, reference),
        )

    def test_sprint_and_aura_native_actor_fields_preserve_costume_and_finishers(self):
        record = self.request(self.request(self.record, 4, 20820), 6, 18299)
        saved = OwnedCosmetics.from_record(record.to_record(), account_id=7)
        character = {**self.character, "owned_cosmetics": saved.to_record()}
        self.assertEqual(
            struct.unpack_from(">iBiiHH", actor_component(character), 1),
            (9727, 1, 20820, 18299, 0, 1),
        )
        state = fresh_player_cosmetic_state(character)
        native = NativeCosmeticState(
            True, state["selected_values"], state["active_cosmetics"]
        )
        self.assertTrue(has_active_cosmetic(native, 4, 20820))
        self.assertTrue(has_active_cosmetic(native, 6, 18299))
        self.assertEqual(saved.selected_finishers(42), (20753,))

    def test_aura_replacement_removal_and_activation(self):
        record = self.request(self.request(self.record, 6, 18299), 6, 18300)
        self.assertEqual(record.selected_single(42, 6), 18300)
        inactive = record.activate_preset(self.character, False)
        self.assertEqual(inactive.selected_single(42, 6), 0)
        self.assertEqual(
            inactive.activate_preset(self.character, True).selected_single(42, 6), 18300
        )
        self.assertEqual(
            self.request(record, 6, 18300, False).selected_single(42, 6), 0
        )

    def test_wrong_category_unowned_and_malformed_records_rejected(self):
        for category, ref in ((6, 20820), (4, 18299), (6, 99999), (1, 18299)):
            with self.subTest(category=category, ref=ref), self.assertRaises(
                ValueError
            ):
                self.request(self.record, category, ref)
        for rows in (None, {}, [7], [[42, 6, 999]], [[42, 6, 18299], [42, 6, 18300]]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                OwnedCosmetics.from_record(
                    {**self.record.to_record(), "single_selections": rows}, account_id=7
                )

    def test_unrelated_category_survives_costume_and_finisher_changes(self):
        record = self.request(self.record, 6, 18299)
        record = record.equip_costume(self.character, 0).equip_finishers(
            self.character, ()
        )
        self.assertEqual(record.selected_single(42, 6), 18299)

    def test_mount_skin_projects_native_pet_visuals_without_mutating_unit(self):
        from copy import deepcopy
        from unittest.mock import patch
        from wakfu_server.mount_inventory import actor_pet
        from wakfu_server.wire import proto_fields

        record = OwnedCosmetics(7, ((1, 18708, 0, 0),)).equip_single(
            self.character, 1, 18708
        )
        character = {**self.character, "owned_cosmetics": record.to_record()}
        state = dict(
            definition_id=123,
            color_item_ref=10,
            equipped_item_ref=20,
            sleep_item_ref=30,
            health=50,
            reskin_item_ref=0,
            xp=999,
        )
        unit = {"mount": state}
        before = deepcopy(unit)
        with patch("wakfu_server.mount_inventory.equipped", return_value=unit):
            self.assertEqual(
                struct.unpack(">6i", actor_pet(character)[2:]),
                (123, 0, 18708, 30, 50, 0),
            )
            inactive = {
                **character,
                "owned_cosmetics": record.activate_preset(
                    self.character, False
                ).to_record(),
            }
            self.assertEqual(
                struct.unpack(">6i", actor_pet(inactive)[2:]), (123, 10, 20, 30, 50, 0)
            )
        self.assertEqual(unit, before)
        category = next(
            value
            for tag, value in proto_fields(record.inventory_component()[4:])
            if tag == 10
        )
        nested = dict(proto_fields(category))[18]
        item = next(value for tag, value in proto_fields(nested) if tag == 10)
        self.assertNotIn(24, dict(proto_fields(item)))

    def test_mount_skin_requires_equipped_mount_and_keeps_other_categories(self):
        from unittest.mock import patch
        from wakfu_server.mount_inventory import actor_pet

        record = OwnedCosmetics(
            7,
            self.record.items + ((1, 18708, 0, 0),),
            self.record.selections,
            (),
            self.record.costumes,
        )
        record = self.request(self.request(record, 6, 18299), 1, 18708)
        self.assertEqual(record.selected_costume(42), 9727)
        self.assertEqual(record.selected_single(42, 6), 18299)
        with patch("wakfu_server.mount_inventory.equipped", return_value=None):
            self.assertEqual(
                actor_pet({**self.character, "owned_cosmetics": record.to_record()}),
                b"\x00\x00",
            )
