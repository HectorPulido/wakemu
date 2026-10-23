"""Focused real-store coverage for Haven World entry, reconnect, and return."""

import os

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase


class HavenWorldTravelPostgresTests(PostgresCase):
    def setUp(self):
        if os.environ.get("WAKFU_RUN_GUILD_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_GUILD_POSTGRES_TESTS=1 for isolated guild DB tests"
            )
        super().setUp()
        from test_guild_service_postgres import (
            GuildServicePostgresTests as GuildFixture,
        )
        from wakfu_server.guild_native_validators import encode_blazon
        from wakfu_server.guild_primary_policy import management_policy
        from wakfu_server.guild_service import GuildService

        self.service = GuildService(self.store)
        self.blazon = encode_blazon(
            emblem_id=1, background_id=2, background_color=3, emblem_color=4
        )
        policy = management_policy(enabled=True)
        policy["haven_world"] = {"enabled": True}
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(policy),),
            )
        self.owner = GuildFixture._player(self, "Haven Travel Owner")
        self.guild = GuildFixture._create(self, self.owner, "Haven Travel Guild")[
            "guild"
        ]
        self.guild_id = self.guild["id"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE accounts SET is_admin=TRUE WHERE id=%s",
                (self.owner["account"],),
            )
        from wakfu_server.guild_haven_world import create_assignment

        self.binding = create_assignment(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.guild_id,
        )
        self.live = {
            (self.owner["account"], self.owner["generation"], self.owner["character"])
        }
        from wakfu_server.characters import heroes

        self.hero = self.store.create_character(
            self.owner["account"],
            "Haven Follower",
            selection_generation=self.owner["generation"],
        )
        heroes.add(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.hero["id"],
        )
        self.live.add(
            (self.owner["account"], self.owner["generation"], self.hero["id"])
        )
        from wakfu_server.position_buffer import Positions

        self.positions = Positions(
            self.store, lease_active=lambda a, g, c: (a, g, c) in self.live
        )
        self.character = self.store.character(
            self.owner["account"], self.owner["character"]
        )
        self.positions.attach(
            self.owner["account"], self.owner["generation"], self.character
        )
        self.hero_character = self.store.character(
            self.owner["account"], self.hero["id"]
        )

    def test_entry_pending_reconnect_npc_identity_and_return_are_consistent(self):
        from wakfu_server import haven_world_travel, wire
        from wakfu_server.combat_monster_world import world_actor
        from wakfu_server.guild_haven_world import bootstrap_packet, scene_context
        from wakfu_server.haven_world_terrain import ENTRY, TEMPLATE_MAP_ID
        from wakfu_server.monsters import owned_instance

        account = self.owner["account"]
        generation = self.owner["generation"]
        character_id = self.owner["character"]
        exterior = {
            key: self.character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        }

        entered = haven_world_travel.travel(
            self.store, self.positions, account, generation, character_id
        )
        token = entered["transition"]["token"]
        self.assertEqual("entry", entered["transition"]["kind"])
        self.assertIn(self.hero["id"], entered["transition"]["cohort"])
        self.assertEqual(
            (TEMPLATE_MAP_ID, self.binding["instance_id"], *ENTRY),
            tuple(
                entered["character"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            ),
        )
        self.assertEqual(-self.guild_id, entered["character"]["native_world_id"])
        self.assertEqual(12957, bootstrap_packet(entered["character"])[0])
        import struct

        captured = b"prefix" + wire.INITIAL_POSITION + struct.pack(">qBB", 123, 3, 1)
        native_position = wire.position(captured, entered["character"])
        self.assertEqual(
            -self.guild_id,
            struct.unpack_from(">q", native_position, len(b"prefix") + 10)[0],
        )
        self.assertEqual(
            entered["character"]["x"],
            self.positions.entries[(account, generation, character_id)]["current"]["x"],
        )
        # A Haven Bag is another private scene nested inside the signed Haven
        # World position. It must retain the signed source on the exterior
        # snapshot while stripping it from every map-9 interior projection.
        from wakfu_server.haven_bag import HavenBagSession

        bag = HavenBagSession(entered["character"])
        self.assertEqual(-self.guild_id, bag.outside["native_world_id"])
        self.assertIn("_native_haven_world_position", bag.outside)
        self.assertNotIn("native_world_id", bag.inside)
        self.assertNotIn("_native_haven_world_position", bag.inside)
        bag.refresh(bag.inside, entered["character"])
        self.assertNotIn("native_world_id", bag.inside)
        rebound_inside = bag.rebind(bag.inside, entered["character"])
        self.assertNotIn("native_world_id", rebound_inside)
        self.assertNotIn("_native_haven_world_position", rebound_inside)
        self.assertEqual(-self.guild_id, bag.leave(rebound_inside)["native_world_id"])
        hero_inside = self.store.character(account, self.hero["id"])
        self.assertEqual(
            tuple(
                entered["transition"]["destination"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            ),
            tuple(hero_inside[key] for key in ("map_id", "instance_id", "x", "y", "z")),
        )
        self.assertEqual(-self.guild_id, hero_inside["native_world_id"])

        # A company member added after entry inherits the active visit and
        # private-world identity from the real main-character source.
        following_hero = self.store.create_character(
            account, "Late Haven Follower", selection_generation=generation
        )
        from wakfu_server.characters import heroes

        heroes.add(self.store, account, generation, character_id, following_hero["id"])
        with self.store.connection() as db:
            heroes.follow_main(db, self.store, account, generation, character_id)
        self.live.add((account, generation, following_hero["id"]))
        following = self.store.character(account, following_hero["id"])
        self.assertEqual(-self.guild_id, following["native_world_id"])
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM haven_world_visits WHERE character_id=%s "
                    "AND guild_id=%s AND returned_at IS NULL",
                    (following_hero["id"], self.guild_id),
                ).fetchone()["n"],
            )

        pending = haven_world_travel.pending(
            self.store, account, generation, character_id
        )
        self.assertEqual(token, pending["transition"]["token"])
        self.assertEqual(
            entered["transition"]["destination"], pending["transition"]["destination"]
        )
        context = scene_context(
            self.store, TEMPLATE_MAP_ID, self.binding["instance_id"]
        )
        monster = owned_instance(
            5525,
            1,
            -99123,
            map_id=TEMPLATE_MAP_ID,
            instance_id=self.binding["instance_id"],
            x=ENTRY[0] + 1,
            y=ENTRY[1],
            z=ENTRY[2],
        )
        actor = world_actor(monster, group_id=99123, world_context=context)
        from wakfu_server.monsters import reference

        actor_world_offset = (
            1
            + struct.calcsize(">qBqH")
            + len(reference(5525)["name"].encode("utf-8"))
            + struct.calcsize(">h")
            + struct.calcsize(">iih")
        )
        self.assertEqual(
            -self.guild_id, struct.unpack_from(">q", actor, actor_world_offset)[0]
        )

        haven_world_travel.acknowledge(
            self.store, account, generation, character_id, token
        )
        self.assertIsNone(
            haven_world_travel.pending(self.store, account, generation, character_id)
        )

        returned = haven_world_travel.travel(
            self.store, self.positions, account, generation, character_id, leave=True
        )
        self.assertEqual("return", returned["transition"]["kind"])
        self.assertIn(self.hero["id"], returned["transition"]["cohort"])
        self.assertIn(following_hero["id"], returned["transition"]["cohort"])
        self.assertEqual(
            exterior, {key: returned["character"][key] for key in exterior}
        )
        self.assertEqual(-self.guild_id, context["native_world_id"])
        haven_world_travel.acknowledge(
            self.store,
            account,
            generation,
            character_id,
            returned["transition"]["token"],
        )
        self.assertIsNone(
            haven_world_travel.pending(self.store, account, generation, character_id)
        )
        self.assertEqual(
            exterior,
            {key: self.store.character(account, character_id)[key] for key in exterior},
        )
        self.assertEqual(exterior["instance_id"], 0)
        for companion_id in (self.hero["id"], following_hero["id"]):
            self.assertEqual(
                exterior,
                {
                    key: self.store.character(account, companion_id)[key]
                    for key in exterior
                },
            )

        # A real administrative/public-scene departure must retire the visit
        # and its undelivered transition before the next character selection.
        entered_again = haven_world_travel.travel(
            self.store, self.positions, account, generation, character_id
        )
        private = entered_again["character"]
        public = dict(map_id=527, instance_id=0, x=0, y=0, z=0)
        from wakfu_server.dungeon_position_barrier import run_account_exit

        run_account_exit(
            self.store,
            self.positions,
            account,
            transition=lambda: self.store.transition_map(
                account,
                generation,
                character_id,
                {key: private[key] for key in ("map_id", "instance_id", "x", "y", "z")},
                public,
            ),
        )
        self.assertIsNone(
            haven_world_travel.pending(self.store, account, generation, character_id)
        )
        self.assertEqual(
            public,
            {key: self.store.character(account, character_id)[key] for key in public},
        )
        for companion_id in (self.hero["id"], following_hero["id"]):
            self.assertEqual(
                public,
                {
                    key: self.store.character(account, companion_id)[key]
                    for key in public
                },
            )
        with self.store.connection() as db:
            visit = db.execute(
                "SELECT returned_at FROM haven_world_visits WHERE character_id=%s",
                (character_id,),
            ).fetchone()
            self.assertIsNotNone(visit["returned_at"])
        self.assertEqual(
            public["map_id"],
            self.positions.entries[(account, generation, character_id)]["current"][
                "map_id"
            ],
        )

        self.live.clear()
        self.positions.release(account, generation, character_id, discard_stale=True)
        next_generation = self.store.begin_session(account)
        selected = self.store.select_character(account, next_generation, character_id)
        self.assertEqual(public, {key: selected[key] for key in public})
        self.assertNotIn("native_world_id", selected)
