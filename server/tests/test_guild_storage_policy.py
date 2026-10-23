"""Native guild storage rights and original installed interaction cells."""
import struct
import unittest
from wakfu_server.guild_storage_policy import (
    MODEL,
    catalog,
    storage_policy,
    chest_permission,
    treasury_permission,
)
from wakfu_server.guild_chest_dispatch import validate_access


class GuildStoragePolicyTests(unittest.TestCase):
    def test_policy_is_detached_opt_in_and_does_not_enable_points_or_bonuses(self):
        base = dict(
            enabled=True,
            native_sync_enabled=True,
            primary_identity_only=False,
            economy=dict(progression_enabled=False, bonuses_enabled=False),
        )
        disabled = storage_policy(base)
        self.assertFalse(disabled["chest"]["enabled"])
        self.assertNotIn("chest", base)
        policy = storage_policy(base, enabled=True)
        self.assertTrue(policy["economy"]["treasury_enabled"])
        self.assertFalse(policy["economy"]["progression_enabled"])
        self.assertFalse(policy["economy"]["bonuses_enabled"])
        self.assertTrue(policy["chest"]["compartments"]["0"]["requires_unlock"])
        self.assertTrue(policy["chest"]["compartments"]["1"]["requires_unlock"])
        policy["chest"]["access_points"][0]["use_cells"][0][0] += 100
        self.assertNotEqual(policy["chest"]["access_points"][0], catalog()["chests"][0])
        with self.assertRaises(ValueError):
            storage_policy(dict(base, primary_identity_only=True), enabled=True)

    def test_native_global_or_scoped_withdraw_right_and_membership_actions(self):
        for compartment in range(4):
            definition = dict(permission_model=MODEL, compartment_id=compartment)
            for action in ("view", "deposit", "move"):
                self.assertTrue(chest_permission(definition, 0, action))
            self.assertFalse(chest_permission(definition, 0, "withdraw"))
            self.assertTrue(chest_permission(definition, 1 << 5, "withdraw"))
            self.assertTrue(
                chest_permission(definition, 1 << (11 + compartment), "withdraw")
            )
            self.assertFalse(
                chest_permission(
                    definition, 1 << (11 + (compartment + 1) % 4), "withdraw"
                )
            )
        self.assertTrue(treasury_permission(0, "treasury_deposit"))
        self.assertFalse(treasury_permission(1 << 5, "treasury_withdraw"))
        self.assertTrue(treasury_permission(1 << 8, "treasury_withdraw"))

    def test_all_nine_original_objects_require_exact_native_ground_use_cells(self):
        for point in catalog()["chests"]:
            row = dict(
                id=point["object_id"],
                map_id=point["map_id"],
                type="GuildStorageBox",
                **dict(zip(("x", "y", "z"), point["object_position"]))
            )
            body = struct.pack(">qHH", point["object_id"], 12, 0)
            for cell in point["use_cells"]:
                char = dict(
                    id=7,
                    map_id=point["map_id"],
                    instance_id=0,
                    **dict(zip(("x", "y", "z"), cell))
                )
                self.assertEqual(
                    validate_access(char, body, [row], [point])["object_id"], row["id"]
                )
            char["x"] += 10
            with self.assertRaises(ValueError):
                validate_access(char, body, [row], [point])
            char.update(zip(("x", "y", "z"), point["use_cells"][0]))
            with self.assertRaises(ValueError):
                validate_access(char, body, [dict(row, x=row["x"] + 1)], [point])

    def test_original_native_global_treasury_signed_long_grammar(self):
        from wakfu_server.guild_wire import decode_storage_request

        for value in (1, 5000, -1, -5000, (1 << 63) - 1):
            self.assertEqual(
                decode_storage_request(13994, struct.pack(">q", value)),
                dict(operation=4 if value < 0 else 3, amount=abs(value)),
            )
        for body in (b"", bytes(8), bytes(9), struct.pack(">q", -(1 << 63))):
            with self.assertRaises((ValueError, struct.error)):
                decode_storage_request(13994, body)
