"""Costume ownership, native preset transitions and actor appearance regressions."""
import struct
import unittest
from wakfu_server.characters.cosmetics import (
    OwnedCosmetics,
    actor_component,
    finisher_request,
)
from wakfu_server.combat_cosmetic_conditions import (
    fresh_player_cosmetic_state,
    NativeCosmeticState,
    has_active_cosmetic,
)
from wakfu_server.wire import proto_field, proto_fields


class OwnedCostumeTests(unittest.TestCase):
    def setUp(self):
        self.character = {"id": 42, "account_id": 7}
        self.record = OwnedCosmetics(
            7, ((3, 9727, 0, 0), (3, 12202, 0, 0), (5, 20753, 0, 0))
        )
        self.record = self.record.equip_finishers(self.character, (20753,))

    def request(self, record, reference, add=True):
        return finisher_request(
            record,
            self.character,
            13765,
            struct.pack(">iiBB", 1, 3, int(add), 1) + proto_field(8, reference),
        )

    def test_both_native_costumes_replace_without_removing_finisher(self):
        guard = self.request(self.record, 9727)
        ninja = self.request(guard, 12202)
        self.assertEqual(ninja.selected_costume(42), 12202)
        self.assertEqual(ninja.selected_finishers(42), (20753,))
        saved = OwnedCosmetics.from_record(ninja.to_record(), account_id=7)
        character = {**self.character, "owned_cosmetics": saved.to_record()}
        self.assertEqual(
            struct.unpack_from(">i", actor_component(character), 1)[0], 12202
        )
        state = fresh_player_cosmetic_state(character)
        self.assertEqual(state["selected_values"][3], 12202)
        self.assertTrue(
            has_active_cosmetic(
                NativeCosmeticState(
                    True, state["selected_values"], state["active_cosmetics"]
                ),
                3,
                12202,
            )
        )
        self.assertEqual(self.request(saved, 12202, False).selected_costume(42), 0)

    def test_native_preset_carries_costume_and_finisher_positions(self):
        selected = self.request(self.record, 9727)
        payload = selected.preset_component()[4:]
        preset = next(value for tag, value in proto_fields(payload) if tag == 10)
        categories = {
            dict(proto_fields(value))[8]
            for tag, value in proto_fields(preset)
            if tag == 42
        }
        self.assertEqual(categories, {3, 5})

    def test_activation_clears_and_restores_both_appearance_categories(self):
        selected = self.request(self.record, 9727)
        inactive = finisher_request(
            selected, self.character, 12455, struct.pack(">iqB", 1, 42, 0)
        )
        self.assertEqual(inactive.selected_costume(42), 0)
        self.assertEqual(inactive.selected_finishers(42), ())
        restored = finisher_request(
            inactive, self.character, 12455, struct.pack(">iqB", 1, 42, 1)
        )
        self.assertEqual(restored.selected_costume(42), 9727)

    def test_unowned_foreign_and_malformed_costumes_rejected(self):
        with self.assertRaises(ValueError):
            self.request(self.record, 999)
        with self.assertRaises(ValueError):
            self.record.equip_costume({"id": 42, "account_id": 8}, 9727)
        data = self.record.to_record()
        for invalid in (None, {}, [7], [[42, 999]]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                OwnedCosmetics.from_record({**data, "costumes": invalid}, account_id=7)

    def test_malformed_shared_learning_packets_reject_before_database_access(self):
        from wakfu_server.cosmetic_learning import learn_item

        for body in (b"", b"\x00" * 11, b"\x00" * 13, None):
            with self.subTest(body=body), self.assertRaises(ValueError):
                learn_item(None, 7, "generation", 42, body)

    def test_old_finisher_records_remain_valid(self):
        data = self.record.to_record()
        del data["costumes"]
        self.assertEqual(
            OwnedCosmetics.from_record(data, account_id=7).selected_finishers(42),
            (20753,),
        )
