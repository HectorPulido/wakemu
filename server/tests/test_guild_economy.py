"""Offline boundary tests; these do not establish PostgreSQL atomicity."""
import unittest
from unittest.mock import Mock, patch
from wakfu_server.characters import guild_economy as economy


class GuildEconomyTests(unittest.TestCase):
    def test_balances_reject_bool_negative_and_overflow(self):
        for value in (True, -1, 2**63, 1.5, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                economy._integer(value, "balance")
        self.assertEqual(economy._integer(2**63 - 1, "balance"), 2**63 - 1)

    def test_keys_are_bounded(self):
        for value in ("", "a" * 201, None, 4):
            with self.assertRaises(ValueError):
                economy._key(value)

    def test_receipt_rejects_conflicting_retry(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = {
            "request": {"amount": 3},
            "result": {"ok": True},
        }
        self.assertEqual(economy._receipt(db, 1, "key", {"amount": 3}), {"ok": True})
        with self.assertRaises(ValueError):
            economy._receipt(db, 1, "key", {"amount": 4})

    def test_noncombat_level_requires_next_level(self):
        db = Mock()
        guild = {"id": 1, "level": 2}
        economy._apply_effect(
            db, guild, {"kind": "unlock_level", "value": 3, "duration_ms": -1}
        )
        db.execute.assert_called_once_with(
            "UPDATE guilds SET level=%s WHERE id=%s", (3, 1)
        )
        for level in (2, 4, 11):
            with self.assertRaises(ValueError):
                economy._apply_effect(
                    db,
                    guild,
                    {"kind": "unlock_level", "value": level, "duration_ms": -1},
                )

    def test_temporary_and_combat_effects_do_not_write(self):
        db = Mock()
        for effect in (
            {"kind": "member_capacity", "value": 50, "duration_ms": 60000},
            {"kind": "combat_damage", "value": 10, "duration_ms": -1},
        ):
            with self.assertRaises(NotImplementedError):
                economy._apply_effect(db, {"id": 1}, effect)
        db.execute.assert_not_called()

    def test_capacity_overflow_and_duplicate_compartment_do_not_write(self):
        db = Mock()
        with self.assertRaises(ValueError):
            economy._apply_effect(
                db,
                {"id": 1, "member_capacity_bonus": 2**31 - 1},
                {"kind": "member_capacity", "value": 50, "duration_ms": -1},
            )
        with self.assertRaises(ValueError):
            economy._apply_effect(
                db,
                {"id": 1, "unlocked_compartments": [4]},
                {"kind": "unlock_compartment", "value": 4, "duration_ms": -1},
            )
        db.execute.assert_not_called()

    def test_chest_uses_shared_transaction_authority(self):
        with patch(
            "wakfu_server.characters.guild_chest.transfer",
            return_value={"applied": True},
        ) as transfer:
            self.assertEqual(
                {"applied": True},
                economy.transfer_chest_item("store", operation_key="once"),
            )
        transfer.assert_called_once_with("store", operation_key="once")

    def test_permission_bit_27_is_supported_and_leader_has_no_bypass(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"permissions": 1 << 27}
        economy._member(db, 1, 2, {"permission_bits": {"withdraw": 27}}, "withdraw")
        with self.assertRaises(ValueError):
            economy._member(
                db, 1, 2, {"permission_bits": {"withdraw": True}}, "withdraw"
            )


if __name__ == "__main__":
    unittest.main()
