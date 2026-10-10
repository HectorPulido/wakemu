"""Native title IDs differ from source scroll references and require ownership."""
import struct
import unittest
from wakfu_server.characters.cosmetics import (
    OwnedCosmetics,
    actor_component,
    finisher_request,
)
from wakfu_server.combat_cosmetic_conditions import fresh_player_cosmetic_state
from wakfu_server.wire import proto_field


class OwnedTitleTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 42,
            "account_id": 7,
            "appearance": {"currentTitle": 999},
        }
        self.record = OwnedCosmetics(
            7, ((7, 137, 0, 0), (3, 9727, 0, 0), (6, 18299, 0, 0), (5, 20753, 0, 0))
        )
        self.record = (
            self.record.equip_finishers(self.character, (20753,))
            .equip_costume(self.character, 9727)
            .equip_single(self.character, 6, 18299)
        )

    def test_native_selection_persists_title_id_and_preserves_other_categories(self):
        selected = finisher_request(
            self.record,
            self.character,
            13765,
            struct.pack(">iiBB", 1, 7, 1, 1) + proto_field(8, 137),
        )
        saved = OwnedCosmetics.from_record(selected.to_record(), account_id=7)
        character = {**self.character, "owned_cosmetics": saved.to_record()}
        self.assertEqual(
            struct.unpack_from(">iBiiHH", actor_component(character), 1),
            (9727, 1, 0, 18299, 137, 1),
        )
        self.assertEqual(
            fresh_player_cosmetic_state(character)["selected_values"][7], 137
        )
        self.assertEqual(saved.selected_finishers(42), (20753,))
        self.assertEqual(
            saved.activate_preset(self.character, False).selected_single(42, 7), 0
        )

    def test_unowned_scroll_reference_and_legacy_appearance_title_are_not_selected(
        self,
    ):
        self.assertEqual(
            struct.unpack_from(
                ">iBiiHH",
                actor_component(
                    {**self.character, "owned_cosmetics": self.record.to_record()}
                ),
                1,
            )[4],
            0,
        )
        for reference in (11431, 999, 65536):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                finisher_request(
                    self.record,
                    self.character,
                    13765,
                    struct.pack(">iiBB", 1, 7, 1, 1) + proto_field(8, reference),
                )

    def test_remove_title_and_reactivate_preserve_other_selections(self):
        selected = self.record.equip_single(self.character, 7, 137)
        removed = finisher_request(
            selected, self.character, 13765, struct.pack(">iiBB", 1, 7, 0, 0)
        )
        self.assertEqual(removed.selected_single(42, 7), 0)
        self.assertEqual(removed.selected_single(42, 6), 18299)
        self.assertEqual(removed.selected_costume(42), 9727)
