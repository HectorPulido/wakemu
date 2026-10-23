"""Actual guild bonus projection and wound-preserving membership lifecycle."""

import os
from datetime import datetime, timedelta, timezone
import time

from postgres_case import PostgresCase
import test_guild_progression_postgres as _progression_fixture


class GuildMemberEffectsPostgresTests(PostgresCase):
    def setUp(self):
        if os.environ.get("WAKFU_RUN_GUILD_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_GUILD_POSTGRES_TESTS=1 for isolated guild DB tests"
            )
        fixture_type = _progression_fixture.GuildProgressionPostgresTests
        fixture = fixture_type(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for attribute in (
            "store",
            "service",
            "owner",
            "guild_id",
            "base_policy",
            "policy",
        ):
            setattr(self, attribute, getattr(fixture, attribute))
        self.member = (
            _progression_fixture._guild_fixture.GuildServicePostgresTests._player(
                self, "Member Effect Member"
            )
        )
        invite = self.service.invite(
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.member["name"],
        )
        self.assertEqual(self.member["character"], invite["target_id"])
        self.service.respond_invitation(
            self.member["account"],
            self.member["generation"],
            self.member["character"],
            True,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE guilds SET current_points=1000 WHERE id=%s", (self.guild_id,)
            )

    def test_member_bonus_updates_live_hp_and_removal_preserves_wound_after_reconnect(
        self,
    ):
        from wakfu_server.characters import (
            guild_economy,
            guild_member_lifecycle,
            guild_progression,
        )
        from wakfu_server.health_store import initialize, sync
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.guild_dispatch import Guilds
        from wakfu_server.maps.world import World

        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        self.store.clock = lambda: now.timestamp()
        character_id = self.member["character"]
        account_id = self.member["account"]
        generation = self.member["generation"]

        with _progression_fixture.patch.object(self.store, "now", return_value=now):
            baseline = initialize(
                self.store,
                account_id,
                generation,
                character_id,
                exploration=True,
                now_ms=int(now.timestamp() * 1000),
            )
            baseline_max = effective_character(baseline, include_consumable_buffs=True)[
                "max_hp"
            ]
            wounded = sync(
                self.store,
                account_id,
                generation,
                character_id,
                baseline["hp"],
                baseline["hp"] - 20,
                now_ms=int(now.timestamp() * 1000),
            )
            self.assertEqual(20, wounded["hp_damage"])

        pending = guild_economy.bonus_operation(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.guild_id,
            1,
            activate=False,
            operation_key="member-effect-1",
        )
        self.assertEqual(800, pending["points"])
        self.assertEqual(
            2 * 60 * 60 * 1000,
            pending["bonus"]["learned_at_ms"] - pending["bonus"]["purchased_at_ms"],
        )

        # Keep an actual online World identity with the pre-activation
        # guild records. The owned guild publication updates that snapshot;
        # the idle reconciler then rereads SQL and adjusts HP once.
        sent = []
        peer = object()
        world = World(
            lambda _: b"spawn",
            lambda _: b"remove",
            lambda _peer, opcode, body: sent.append((opcode, body)),
        )
        world.join(generation, peer, wounded)
        with _progression_fixture.patch.object(
            self.store, "now", return_value=now + timedelta(hours=2, milliseconds=1)
        ):
            self.assertEqual(
                ((self.guild_id, (1,)),), guild_progression.tick(self.store)
            )
            guilds = Guilds(self.store, world, local_entity=lambda: b"")
            snapshot = self.service.snapshot(
                self.owner["account"], self.owner["generation"], self.owner["character"]
            )
            guilds._projection(character_id, generation, snapshot)
            live = world.live_identity(character_id=character_id)[1]
            live.update(world.guild_projection(character_id, generation))
            refreshed, changed = guild_member_lifecycle.synchronize(
                self.store, account_id, generation, live, in_combat=False
            )
        self.assertTrue(changed)
        self.assertEqual(1, len(refreshed["guild_member_effects"]))
        self.assertEqual(
            baseline_max + 5,
            effective_character(refreshed, include_consumable_buffs=True)["max_hp"],
        )
        self.assertEqual(20, refreshed["hp_damage"])
        self.assertEqual(wounded["hp"] + 5, refreshed["hp"])
        self.assertEqual(
            1,
            len(
                world.guild_projection(character_id, generation)[
                    "guild_member_bonus_records"
                ]
            ),
        )
        # Keep the online World copy in sync with the reconciled HP and
        # owned effects before testing a later guild removal publication.
        world.join(generation, peer, refreshed)

        # Combat snapshots stay pinned to their current projection. The
        # same online publication is reconciled at the next idle boundary.
        frozen, changed = guild_member_lifecycle.synchronize(
            object(), account_id, generation, dict(refreshed), in_combat=True
        )
        self.assertFalse(changed)
        self.assertEqual(
            refreshed["guild_member_effects"], frozen["guild_member_effects"]
        )

        removed = self.service.remove_member(
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            character_id,
        )
        self.assertNotIn(
            character_id, {row["character_id"] for row in removed["members"]}
        )
        guilds._projection(character_id, generation, None)
        live_after_remove = world.live_identity(character_id=character_id)[1]
        live_after_remove.update(world.guild_projection(character_id, generation))
        self.assertIsNone(live_after_remove["guild_native"])
        self.assertEqual({}, live_after_remove["guild_member_bonus_records"])
        with _progression_fixture.patch.object(
            self.store, "now", return_value=now + timedelta(hours=2, milliseconds=2)
        ):
            cleared, changed = guild_member_lifecycle.synchronize(
                self.store, account_id, generation, live_after_remove, in_combat=False
            )
        self.assertTrue(changed)
        self.assertEqual((), cleared["guild_member_effects"])
        self.assertEqual(
            baseline_max,
            effective_character(cleared, include_consumable_buffs=True)["max_hp"],
        )
        self.assertEqual(20, cleared["hp_damage"])
        self.assertEqual(wounded["hp"], cleared["hp"])

        world.leave(character_id, generation)
        # Restore wall-clock behavior before issuing the fresh reconnect
        # lease; earlier assertions intentionally advanced a fake guild clock.
        self.store.__dict__.pop("now", None)
        self.store.clock = time.time
        reconnected_generation = self.store.begin_session(account_id)
        with self.store.connection() as db:
            lease = db.execute(
                "SELECT generation,expires_at FROM sessions WHERE account_id=%s",
                (account_id,),
            ).fetchone()
            character_owner = db.execute(
                "SELECT account_id FROM characters WHERE id=%s", (character_id,)
            ).fetchone()
        self.assertEqual(reconnected_generation, lease["generation"])
        self.assertGreater(lease["expires_at"], self.store.now())
        self.assertEqual(account_id, character_owner["account_id"])
        reconnected = self.store.select_character(
            account_id, reconnected_generation, character_id
        )
        self.assertEqual((), reconnected["guild_member_effects"])
        self.assertEqual(20, reconnected["hp_damage"])
        self.assertEqual(
            baseline_max,
            effective_character(reconnected, include_consumable_buffs=True)["max_hp"],
        )
