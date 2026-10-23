"""Native primary identity notifications and capability isolation."""
from contextlib import nullcontext
from types import SimpleNamespace
import unittest

from wakfu_server import guild_wire, guild_model
from wakfu_server.guild_service import GuildService


class GuildPrimaryResultTests(unittest.TestCase):
    def test_original_success_bodies_use_utf8_bytes_and_empty_blazon(self):
        for name in ("Guild Test", "Guilde Étoile"):
            payload = name.encode("utf-8")
            expected = bytes((len(payload),)) + payload
            self.assertEqual(guild_wire.creation_ack(name), (1000, expected))
            self.assertEqual(
                guild_wire.identity_change_ack("name", name), (1162, expected)
            )
        self.assertEqual(guild_wire.identity_change_ack("blazon", 123), (1053, b""))
        with self.assertRaises(ValueError):
            guild_wire.identity_change_ack("name", "é" * 64)
        with self.assertRaises(ValueError):
            guild_wire.identity_change_ack("description", "unavailable")

    def test_primary_request_scope_keeps_unqualified_guild_mutations_disabled(self):
        policy = dict(
            enabled=True, native_sync_enabled=True, primary_identity_only=True
        )
        query = SimpleNamespace(fetchone=lambda: {"value": policy})
        db = SimpleNamespace(execute=lambda *args: query)
        service = GuildService(SimpleNamespace(connection=lambda: nullcontext(db)))
        for opcode in (13757, 12937, 12575, 15877):
            service.authorize_native_request(opcode)
        for opcode in (13744, 15542, 15613, 14447, 15481):
            with self.assertRaisesRegex(ValueError, "identity-only"):
                service.authorize_native_request(opcode)
        policy["enabled"] = False
        with self.assertRaisesRegex(ValueError, "disabled"):
            service.authorize_native_request(13757)
        policy.update(enabled=True, primary_identity_only=False)
        service.authorize_native_request(15542)

    def test_primary_projection_rejects_enabled_economy_and_fake_owners(self):
        policy = dict(
            primary_identity_only=True,
            owner_id_semantics="account",
            weekly_points_limit=0,
            earned_points_limit=0,
            last_earning_point_week=0,
            moderation_bonus_learning_factor=0,
            economy=dict(
                treasury_enabled=False, progression_enabled=False, bonuses_enabled=False
            ),
        )
        # Native model must reject fake identities before attempting the rest
        # of a required guild/member projection.
        snapshot = dict(
            policy=policy, guild={}, members=[dict(character_id=7, account_id=0)]
        )
        with self.assertRaisesRegex(ValueError, "actual owner identities"):
            guild_model.native_model(snapshot)
        policy["economy"]["progression_enabled"] = True
        with self.assertRaisesRegex(ValueError, "disabled economy"):
            guild_model.native_model(snapshot)
        policy["economy"]["progression_enabled"] = False
        policy["owner_id_semantics"] = "character"
        with self.assertRaisesRegex(ValueError, "real account owner"):
            guild_model.native_model(snapshot)
