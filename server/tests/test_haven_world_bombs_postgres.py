"""Focused PostgreSQL coverage for explicitly assigned private guild worlds."""
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase


class HavenWorldBombsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server.guild_service import GuildService
        from wakfu_server.guild_native_validators import encode_blazon

        self.service = GuildService(self.store)
        self.blazon = encode_blazon(
            emblem_id=1, background_id=2, background_color=3, emblem_color=4
        )
        from wakfu_server.guild_primary_policy import management_policy

        policy = management_policy(enabled=True)
        policy["haven_world"] = {"enabled": True}
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(policy),),
            )

        # Reuse the established guild integration fixture without inheriting its
        # TestCase methods, which would cause unittest to discover unrelated tests.
        from test_guild_service_postgres import (
            GuildServicePostgresTests as _guild_tests,
        )

        self.owner = _guild_tests._player(self, "World Bomb Owner")
        self.created = _guild_tests._create(self, self.owner, "World Bomb Guild")
        self.guild_id = self.created["guild"]["id"]
        self.instance_id = 700000 + self.guild_id
        with self.store.connection() as db:
            db.execute(
                "UPDATE accounts SET is_admin=TRUE WHERE id=%s",
                (self.owner["account"],),
            )
        from wakfu_server.combat_terrain import map_geometry

        geometry = map_geometry(1134)
        self.entry = tuple(geometry["cells"][0])
        from wakfu_server.guild_haven_world import assign

        self.binding = assign(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            guild_id=self.guild_id,
            native_world_id=-self.guild_id,
            map_id=1134,
            instance_id=self.instance_id,
            entry=self.entry,
        )
        self.context = dict(
            map_id=1134,
            instance_id=self.instance_id,
            native_world_id=-self.guild_id,
            x=self.entry[0],
            y=self.entry[1],
            z=self.entry[2],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (self.instance_id, *self.entry, self.owner["character"]),
            )
            self.bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.owner["character"],),
            ).fetchone()["uid"]

    def _bomb(self, reference, quantity=1):
        from wakfu_server.inventory_items import grant

        with self.store.connection() as db:
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (self.bag,),
            ).fetchone()["slot"]
        return grant(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            reference=reference,
            quantity=quantity,
            container=self.bag,
            slot=slot,
            allowed_references={reference},
        )

    def _register_group(self, group_id, members, status="available"):
        from wakfu_server.combat_group_store import PersistentGroups

        groups = PersistentGroups(self.store)
        groups.register(1134, self.instance_id, group_id, members)
        if status == "fighting":
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
            groups.claim(
                (1134, self.instance_id, group_id), "haven-bomb-fighting", fight_id
            )

    def _member(self, monster_id, x, y, z):
        from wakfu_server.monsters import owned_instance

        return owned_instance(
            5525,
            1,
            monster_id,
            map_id=1134,
            instance_id=self.instance_id,
            x=x,
            y=y,
            z=z,
        )

    def _use(self, action, uid, x=None, y=None, *, context=None, in_fight=False):
        from wakfu_server.haven_world_bombs import use

        x = self.entry[0] if x is None else x
        y = self.entry[1] if y is None else y
        return use(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            struct.pack(">iqii", action, uid, x, y),
            in_fight=in_fight,
            context=self.context if context is None else context,
        )

    def test_database_owned_world_identity_reaches_native_position_wire(self):
        from wakfu_server.guild_haven_world import world_identity
        from wakfu_server import wire

        character = self.reopen().character(
            self.owner["account"], self.owner["character"]
        )
        self.assertEqual(character["native_world_id"], -self.guild_id)
        self.assertEqual(world_identity(character), -self.guild_id)
        captured = (
            b"prefix"
            + wire.INITIAL_POSITION
            + struct.pack(">qBB", 1134, 3, 1)
            + b"suffix"
        )
        encoded = wire.position(captured, character)
        expected = (
            b"prefix"
            + struct.pack(">iihqBB", *self.entry, -self.guild_id, 3, 1)
            + b"suffix"
        )
        self.assertEqual(encoded, expected)
        forged = dict(character, native_world_id=-(self.guild_id + 1))
        with self.assertRaisesRegex(ValueError, "Unverified private"):
            world_identity(forged)

    def test_native_bomb_radii_remove_only_matching_available_groups(self):
        from wakfu_server.haven_world_bombs import ACTIONS

        self.assertEqual(
            ACTIONS, {4728: (17551, 4), 4838: (17592, 8), 4828: (17593, 16)}
        )
        from wakfu_server.combat_terrain import map_geometry

        cz = self.entry[2]
        candidates = [
            tuple(cell)
            for cell in map_geometry(1134)["cells"]
            if abs(cell[2] - cz) <= 1
        ]
        centers = []
        for candidate in candidates:
            if all(
                (candidate[0] - prior[0]) ** 2 + (candidate[1] - prior[1]) ** 2
                > 36**2
                for prior in centers
            ):
                centers.append(candidate)
            if len(centers) == len(ACTIONS):
                break
        self.assertEqual(
            len(centers),
            len(ACTIONS),
            "native test terrain needs three separated targets",
        )
        group_ids = []
        full_ids = []
        for index, ((action, (reference, radius)), (cx, cy, target_z)) in enumerate(
            zip(ACTIONS.items(), centers)
        ):
            inside = self._member(-81001 - index * 10, cx + radius, cy, target_z)
            outside = self._member(-81002 - index * 10, cx + radius + 1, cy, target_z)
            key = 81001 + index
            group_ids.append((key, inside["id"], outside["id"]))
            self._register_group(key, [inside, outside])
            full = self._member(-81003 - index * 10, cx, cy, target_z)
            full_key = 81101 + index
            full_ids.append((full_key, full["id"]))
            self._register_group(full_key, [full])
            if index == 0:
                fighting = self._member(-81999, cx, cy, target_z)
                self._register_group(81999, [fighting], status="fighting")

        results = []
        for (action, (reference, _radius)), (cx, cy, _target_z) in zip(
            ACTIONS.items(), centers
        ):
            source = self._bomb(reference)
            results.append(self._use(action, source["uid"], x=cx, y=cy))
        self.assertEqual([row["removed_count"] for row in results], [2, 2, 2])
        self.assertTrue(all(row["applied"] and row["consumed"] == 1 for row in results))
        with self.store.connection() as db:
            rows = {
                row["group_id"]: row
                for row in db.execute(
                    "SELECT group_id,members,status,ecology_admin_removed_ids FROM combat_groups "
                    "WHERE map_id=1134 AND instance_id=%s",
                    (self.instance_id,),
                )
            }
        for key, inside_id, outside_id in group_ids:
            self.assertEqual(rows[key]["ecology_admin_removed_ids"], [inside_id])
            self.assertEqual(
                [member["id"] for member in rows[key]["members"]], [outside_id]
            )
        for key, member_id in full_ids:
            self.assertEqual(rows[key]["status"], "defeated")
            self.assertEqual(rows[key]["ecology_admin_removed_ids"], [member_id])
            self.assertEqual(
                [member["id"] for member in rows[key]["members"]], [member_id]
            )
        self.assertEqual(rows[81999]["status"], "fighting")
        self.assertEqual(rows[81999]["ecology_admin_removed_ids"], [])
        from wakfu_server.combat_group_store import PersistentGroups

        visible = PersistentGroups(self.store).available(1134, self.instance_id)
        self.assertEqual(
            {row["key"][2] for row in visible}, {key for key, _, _ in group_ids}
        )

    def test_native_bomb_scope_rejections_and_post_mutation_rollback(self):
        from wakfu_server.haven_world_bombs import use

        source = self._bomb(17551, quantity=2)
        member = self._member(-82001, self.entry[0], self.entry[1], self.entry[2])
        self._register_group(82001, [member])
        wrong = dict(self.context, native_world_id=999)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb({"enabled": False}),),
            )
        with self.assertRaisesRegex(ValueError, "disabled"):
            self._use(4728, source["uid"])
        from wakfu_server.guild_primary_policy import management_policy

        native_policy = management_policy(enabled=True)
        native_policy["haven_world"] = {"enabled": True}
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(native_policy),),
            )
            leader = db.execute(
                "SELECT rank_id FROM guild_members WHERE character_id=%s",
                (self.owner["character"],),
            ).fetchone()["rank_id"]
            leader_mask = db.execute(
                "SELECT permissions FROM guild_ranks WHERE id=%s", (leader,)
            ).fetchone()["permissions"]
            db.execute("UPDATE guild_ranks SET permissions=0 WHERE id=%s", (leader,))
        with self.assertRaisesRegex(ValueError, "permission denied"):
            self._use(4728, source["uid"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE guild_ranks SET permissions=%s WHERE id=%s",
                (leader_mask, leader),
            )
        for call in (
            lambda: self._use(4728, source["uid"], context=wrong),
            lambda: self._use(4728, source["uid"], in_fight=True),
            lambda: self._use(4728, source["uid"], x=10**6, y=10**6),
            lambda: use(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                b"bad",
                in_fight=False,
                context=self.context,
            ),
        ):
            with self.assertRaises(ValueError):
                call()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT ecology_admin_removed_ids FROM combat_groups WHERE group_id=82001"
                ).fetchone()["ecology_admin_removed_ids"],
                [],
            )

        original = __import__(
            "wakfu_server.haven_world_bombs", fromlist=["_remove_available"]
        )._remove_available

        def mutate_then_fail(*args):
            original(*args)
            raise RuntimeError("injected post-population failure")

        with patch(
            "wakfu_server.haven_world_bombs._remove_available",
            side_effect=mutate_then_fail,
        ):
            with self.assertRaisesRegex(RuntimeError, "post-population"):
                self._use(4728, source["uid"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT ecology_admin_removed_ids FROM combat_groups WHERE group_id=82001"
                ).fetchone()["ecology_admin_removed_ids"],
                [],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM haven_world_bomb_uses"
                ).fetchone()["n"],
                0,
            )
