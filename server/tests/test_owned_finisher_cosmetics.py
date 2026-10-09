import struct
import unittest

from wakfu_server.characters.cosmetics import (
    OwnedCosmetics,
    actor_component,
    actor_update,
    finisher_request,
)
from wakfu_server.combat_cosmetic_conditions import (
    NativeCosmeticState,
    active_cosmetic_id,
    fresh_player_cosmetic_state,
    has_active_cosmetic,
    initialize_fresh_player_cosmetics,
)
from wakfu_server.combat_state import Actor
from wakfu_server.wire import proto_field


class OwnedFinisherCosmeticTests(unittest.TestCase):
    def setUp(self):
        self.character = {"id": 2**40 + 17, "account_id": 2**40 + 3}
        self.record = OwnedCosmetics(
            self.character["account_id"],
            ((5, 20753, 0, 0), (5, 20754, 4, 9)),
        )

    def test_selected_owned_finisher_flows_to_native_actor_component(self):
        selected = self.record.equip_finishers(self.character, (20753,))
        saved = OwnedCosmetics.from_record(
            selected.to_record(), account_id=self.character["account_id"]
        )
        character = {**self.character, "owned_cosmetics": saved.to_record()}
        state = fresh_player_cosmetic_state(character)
        actor = Actor(character["id"], 0, (0, 0, 0), 100, 6, 3, 10, 1, 1, True)
        initialize_fresh_player_cosmetics(actor, character)

        self.assertEqual(state["selected_values"][5], (20753,))
        self.assertEqual(state["active_cosmetics"][5], (20753,))
        self.assertEqual(actor.native_cosmetic_state, state)
        native = NativeCosmeticState(
            True, state["selected_values"], state["active_cosmetics"]
        )
        self.assertEqual(active_cosmetic_id(native, 5), 20753)
        self.assertTrue(has_active_cosmetic(native, 5, 20753))
        self.assertFalse(has_active_cosmetic(native, 5, 20754))

    def test_selection_cannot_cross_accounts_or_reference_unowned_item(self):
        other = {
            "id": self.character["id"] + 1,
            "account_id": self.character["account_id"] + 1,
        }
        with self.assertRaisesRegex(ValueError, "another account"):
            self.record.equip_finishers(other, (20753,))
        with self.assertRaisesRegex(ValueError, "not owned"):
            self.record.equip_finishers(self.character, (999999,))

    def test_actor_wire_component_contains_only_selected_owned_finisher_refs(self):
        selected = self.record.equip_finishers(self.character, (20753,))
        character = {**self.character, "owned_cosmetics": selected.to_record()}
        encoded = actor_component(character)
        expected = (
            b"\x01"
            + struct.pack(">iBiiHH", 0, 1, 0, 0, 0, 1)
            + struct.pack(">i", 20753)
        )
        self.assertEqual(encoded, expected)
        self.assertEqual(actor_component({"id": self.character["id"]}), b"\x00")

        opcode, packet = actor_update(character)
        identity, length = struct.unpack_from(">qh", packet)
        body = packet[10:]
        self.assertEqual(opcode, 13046)
        self.assertEqual(identity, self.character["id"])
        self.assertEqual(length, len(body))
        self.assertEqual(body, b"\x1e" + struct.pack(">q", identity) + expected)
        with self.assertRaisesRegex(
            ValueError, "Invalid owned account cosmetic record"
        ):
            actor_update({**character, "account_id": 99})

    def test_native_preset_activation_and_item_add_remove_keep_stable_selection(self):
        selected = self.record.equip_finishers(self.character, (20753,))
        deactivated = finisher_request(
            selected,
            self.character,
            12455,
            struct.pack(">iqB", 1, self.character["id"], 0),
        )
        saved_inactive = OwnedCosmetics.from_record(
            deactivated.to_record(), account_id=self.character["account_id"]
        )
        self.assertEqual(saved_inactive.selected_finishers(self.character["id"]), ())
        self.assertEqual(saved_inactive.selections, selected.selections)
        activated_again = finisher_request(
            saved_inactive,
            self.character,
            12455,
            struct.pack(">iqB", 1, self.character["id"], 1),
        )
        self.assertEqual(
            activated_again.selected_finishers(self.character["id"]), (20753,)
        )

        activated = finisher_request(
            activated_again,
            self.character,
            12455,
            struct.pack(">iqB", 1, self.character["id"], 1),
        )
        self.assertEqual(activated.selected_finishers(self.character["id"]), (20753,))

        item = proto_field(8, 20754) + proto_field(16, 4) + proto_field(24, 9)
        added = finisher_request(
            activated,
            self.character,
            13765,
            struct.pack(">iiBB", 1, 5, 1, 1) + item,
        )
        self.assertEqual(added.selected_finishers(self.character["id"]), (20753, 20754))
        removed = finisher_request(
            added,
            self.character,
            13765,
            struct.pack(">iiBB", 1, 5, 0, 1) + item,
        )
        self.assertEqual(removed.selected_finishers(self.character["id"]), (20753,))
        self.assertEqual(removed.to_record()["selections"][0][0], self.character["id"])

    def test_account_and_preset_requests_reject_foreign_or_malformed_identity(self):
        selected = self.record.equip_finishers(self.character, (20753,))
        with self.assertRaisesRegex(ValueError, "Missing owned finisher account"):
            finisher_request(
                selected,
                {"id": self.character["id"], "account_id": 99},
                12455,
                struct.pack(">iqB", 1, self.character["id"], 1),
            )
        with self.assertRaisesRegex(ValueError, "activation"):
            finisher_request(
                selected,
                self.character,
                12455,
                struct.pack(">iqB", 1, self.character["id"] + 1, 1),
            )
        with self.assertRaisesRegex(ValueError, "preset request"):
            finisher_request(
                selected,
                self.character,
                13765,
                struct.pack(">iiBB", 1, 4, 1, 1) + proto_field(8, 20753),
            )


if __name__ == "__main__":
    unittest.main()
