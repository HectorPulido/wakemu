"""Guild projections must preserve actor combat state and reject stale leases."""
import struct
import unittest
from copy import deepcopy

from wakfu_server.characters import guild_model, guild_wire
from wakfu_server.world import World


class GuildProjectionTests(unittest.TestCase):
    def snapshot(self):
        return {
            "policy": {
                "owner_id_semantics": "account",
                "moderation_bonus_learning_factor": 0.0,
            },
            "guild": dict(
                id=9,
                level=1,
                blazon=2,
                name="Audit Guild",
                description="",
                message="",
                current_points=0,
                total_points=0,
                weekly_points_limit=7500,
                earned_points_limit=0,
                last_earning_point_week=0,
            ),
            "ranks": [dict(id=10, name="Leader", permissions=1 << 40, position=0)],
            "members": [
                dict(
                    character_id=42,
                    account_id=7,
                    rank_id=10,
                    points=0,
                    xp=12345,
                    connected=False,
                    sex=False,
                    breed=1,
                    name="Audit Member",
                    save_date=1729000000123,
                    language_mask=3,
                    community=1,
                )
            ],
            "bonuses": [
                dict(bonus_id=1, activation_date=1729000000000, buy_date=1728000000000)
            ],
        }

    def test_native_projection_preserves_authoritative_identity_xp_and_milliseconds(
        self,
    ):
        source = self.snapshot()
        saved = deepcopy(source)
        model = guild_model.native_model(source)
        self.assertEqual(model["members"][0]["ownerId"], 7)
        self.assertEqual(model["members"][0]["saveDate"], 1729000000123)
        self.assertEqual(model["members"][0]["xp"], 12345)
        self.assertFalse(model["members"][0]["isConnected"])
        self.assertEqual(model["members"][0]["serializedLanguages"], b"\x03")
        self.assertEqual(model["ranks"][0]["authorizations"], 1 << 40)
        self.assertTrue(guild_wire.serialize_guild(model))
        self.assertEqual(source, saved)

    def test_unknown_owner_semantics_and_missing_required_member_data_fail(self):
        source = self.snapshot()
        source["policy"]["owner_id_semantics"] = None
        with self.assertRaises(ValueError):
            guild_model.native_model(source)
        source["policy"]["owner_id_semantics"] = "account"
        del source["members"][0]["save_date"]
        with self.assertRaises(KeyError):
            guild_model.native_model(source)

    def test_moderation_factor_is_explicit_and_finite(self):
        source = self.snapshot()
        for factor in (None, True, float("nan"), float("inf"), -1):
            source["policy"]["moderation_bonus_learning_factor"] = factor
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                guild_model.moderation_factor(source)
        self.assertEqual(0.0, guild_model.moderation_factor(None))

    def test_native_point_policy_requires_explicit_bounded_counters(self):
        policy = dict(
            native_sync_enabled=True,
            weekly_points_limit=7500,
            earned_points_limit=0,
            last_earning_point_week=0,
        )
        for field in (
            "weekly_points_limit",
            "earned_points_limit",
            "last_earning_point_week",
        ):
            incomplete = dict(policy)
            del incomplete[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                guild_model.point_limits(incomplete, {})
            invalid = dict(policy, **{field: 2**31})
            with self.subTest(field=field), self.assertRaises(ValueError):
                guild_model.point_limits(invalid, {})
        guild = {"weekly_capacity_bonus": 500}
        policy["economy"] = dict(progression_enabled=True, weekly_point_cap=7500)
        guild_model.point_limits(policy, guild)
        self.assertEqual(8000, guild["weekly_points_limit"])
        guild["weekly_capacity_bonus"] = 2**31
        with self.assertRaises(ValueError):
            guild_model.point_limits(policy, guild)

    def test_projection_changes_only_guild_fields_and_is_detached(self):
        world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        original = dict(
            id=42,
            account_id=7,
            map_id=1,
            instance_id=0,
            hp=37,
            spells=[{"id": 8, "level": 12}],
            x=3,
            y=4,
        )
        world.join("current", object(), original)
        model = guild_model.native_model(self.snapshot())
        self.assertTrue(world.set_guild_projection(42, "current", model, 0.0))
        model["name"] = "Altered input"
        projected = world.guild_projection(42, "current")
        self.assertEqual("Audit Guild", projected["guild_native"]["name"])
        projected["guild_native"]["name"] = "Altered output"
        live = world.live_identity(character_id=42)[1]
        for key, value in original.items():
            self.assertEqual(value, live[key])
        self.assertEqual("Audit Guild", live["guild_native"]["name"])
        self.assertFalse(world.set_guild_projection(42, "stale", None, 0.0))
        self.assertEqual({}, world.guild_projection(42, "stale"))

    def test_remote_update_carries_no_combat_sections(self):
        opcode, body = guild_wire.remote_actor_update(42, 9, 2, 1, "Audit Guild")
        self.assertEqual(15548, opcode)
        actor, length = struct.unpack_from(">qH", body)
        self.assertEqual(42, actor)
        self.assertEqual(len(body) - 10, length)
        self.assertEqual(12, body[10])
        self.assertEqual(bytes(31), body[11:42])
        self.assertEqual(guild_wire.remote_info(9, 2, 1, "Audit Guild"), body[42:])
