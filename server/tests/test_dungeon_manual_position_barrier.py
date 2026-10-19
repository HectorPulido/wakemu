"""PostgreSQL/Redis regressions for manually requested dungeon travel."""

import os
import struct
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
import test_dungeon_instances
from wakfu_server import player_parties
from wakfu_server.maps import dungeon_doors, dungeon_exit
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    settle_encounter,
)
from wakfu_server.position_redis import Journal, RedisPositions


class DungeonManualPositionBarrierPostgresTests(PostgresCase):
    """Exercise SQL travel with real isolated PostgreSQL and Redis state."""

    install_context_policy = (
        test_dungeon_instances.DungeonInstanceTests.install_context_policy
    )
    player = test_dungeon_instances.DungeonInstanceTests.player
    party = test_dungeon_instances.DungeonInstanceTests.party
    enter = test_dungeon_instances.DungeonInstanceTests.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.members, self.party_id = self.party(2)
        self.instance = self.enter(self.members[0])
        self.instance_id = self.instance["instance_id"]
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="c" * 64,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)

        self.namespace = (
            "wakfu:test:dungeon-manual-position-barrier:" + uuid.uuid4().hex
        )
        redis_url = os.environ.get("WAKFU_REDIS_TEST_URL") or os.environ.get(
            "WAKFU_REDIS_URL"
        )
        if not redis_url:
            self.skipTest("Local Redis URL required for position barrier regression")
        import redis

        self.redis = redis.Redis.from_url(
            redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        self.redis.ping()
        self.addCleanup(self.redis.delete, self.namespace)
        self.journal = Journal(self.redis, namespace=self.namespace)
        self._refresh_positions()

    def _refresh_positions(self):
        leases = {
            (member["account"], member["generation"], member["character"]["id"])
            for member in self.members
        }
        self.positions = RedisPositions(
            self.store,
            lease_active=lambda *key: key in leases,
            journal=self.journal,
        )

    def _initialize_run(self):
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="c" * 64,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)

    def _move(self, member, *, dx=3, dy=2):
        character = self.store.character(member["account"], member["character"]["id"])
        self.positions.attach(member["account"], member["generation"], character)
        return self.positions.move(
            member["account"],
            member["generation"],
            character["id"],
            character,
            {
                "x": character["x"] + dx,
                "y": character["y"] + dy,
                "z": character["z"],
                "direction": 5,
            },
        )

    def _authorize_first_room(self):
        member = self.members[0]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, member["character"]["id"], member["account"]),
            )
            bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                member["character"]["id"],
                fight_id,
                player_team=0,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            receipt = settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
        self.assertTrue(receipt["victory"])

    def _door_topology_room(self, map_id, x, y, z):
        if map_id != 1086 or z != 0:
            return None
        return {(0, -27): 1, (152, -10): 2}.get((int(x), int(y)))

    def _door_source_check(self, character, source):
        return tuple(round(character[key]) for key in ("x", "y")) == (4, -12)

    def _door_request(self):
        return struct.pack(">qiBi", 26845, 2506, 0, 2)

    def _advance(self, *, positions):
        member = self.members[0]
        return dungeon_doors.advance(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            self._door_request(),
            source_allowed=self._door_source_check,
            room_for_position=self._door_topology_room,
            in_fight=lambda _identity: False,
            positions=positions,
        )

    def _door_outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT character_id,source_x,source_y,source_z FROM dungeon_transition_outbox "
                "WHERE instance_id=%s AND transition_kind='door' ORDER BY character_id",
                (self.instance_id,),
            ).fetchall()

    def test_manual_door_flushes_dirty_other_account_before_party_travel(self):
        self._authorize_first_room()
        moved = self._move(self.members[1])

        self._advance(positions=self.positions)

        rows = {row["character_id"]: row for row in self._door_outbox()}
        companion_id = self.members[1]["character"]["id"]
        self.assertEqual(
            (moved["x"], moved["y"], moved["z"]),
            tuple(
                rows[companion_id][key] for key in ("source_x", "source_y", "source_z")
            ),
        )
        saved = self.store.character(self.members[1]["account"], companion_id)
        self.assertEqual((152, -10), (saved["x"], saved["y"]))
        self.assertEqual(
            (moved["x"], moved["y"]),
            (rows[companion_id]["source_x"], rows[companion_id]["source_y"]),
        )
        key = (
            self.members[1]["account"],
            self.members[1]["generation"],
            companion_id,
        )
        self.assertFalse(self.positions.entries[key]["dirty"])
        self.assertEqual(
            (152, -10),
            tuple(
                self.positions.entries[key]["persisted"][axis] for axis in ("x", "y")
            ),
        )
        self.assertEqual([], list(self.journal.records()))

        next_move = self._move(self.members[1], dx=1, dy=0)
        self.positions.flush(account_id=self.members[1]["account"])
        self.assertEqual(
            (next_move["x"], next_move["y"]),
            tuple(
                self.store.character(self.members[1]["account"], companion_id)[axis]
                for axis in ("x", "y")
            ),
        )
        self.assertEqual([], list(self.journal.records()))

    def test_manual_exit_flushes_dirty_owned_hero_on_same_account(self):
        from wakfu_server.characters import heroes

        main = self.player("manual-exit-main")
        hero = self.store.create_character(main["account"], "Dng Manual Exit Hero")
        heroes.add(
            self.store,
            main["account"],
            main["generation"],
            main["character"]["id"],
            hero["id"],
        )
        # The hero must be the active selected character before its run starts;
        # the company freeze correctly blocks switching characters mid-run.
        self.store.select_character(main["account"], main["generation"], hero["id"])
        hero_member = {
            "account": main["account"],
            "generation": main["generation"],
            "character": self.store.character(main["account"], hero["id"]),
        }
        run = self.enter(hero_member)
        self.assertIn(hero["id"], run["members"])
        hero_row = self.store.character(main["account"], hero["id"])

        self.members = [hero_member]
        self._refresh_positions()
        moved_hero = self._move(self.members[0])
        body = struct.pack(">qiBi", 26843, 2517, 0, 2)
        source = {
            "id": 26843,
            "map_id": hero_row["map_id"],
            "x": 4,
            "y": -12,
            "z": 0,
            "destinations": [
                {
                    "destination_id": 2517,
                    "map_id": 527,
                    "x": -245,
                    "y": -90,
                    "z": 0,
                    "criterion": "",
                    "cyZ": -1,
                    "cyX": 0,
                    "cyW": 0,
                    "item_reference": 0,
                    "native_altitude_walkable": True,
                }
            ],
        }
        with patch(
            "wakfu_server.maps.dungeon_exit.generic_transports.source",
            return_value=source,
        ):
            result = dungeon_exit.leave(
                self.store,
                main["account"],
                main["generation"],
                hero["id"],
                body,
                source_allowed=lambda _character, _source: True,
                in_fight=lambda _identity: False,
                positions=self.positions,
            )

        saved_hero = self.store.character(main["account"], hero["id"])
        self.assertEqual(
            (527, -245, -90),
            (saved_hero["map_id"], saved_hero["x"], saved_hero["y"]),
        )
        self.assertEqual(527, result["map_id"])
        with self.store.connection() as db:
            event = db.execute(
                "SELECT source_x,source_y,source_z FROM dungeon_transition_outbox "
                "WHERE instance_id=%s AND character_id=%s AND transition_kind='exit'",
                (run["instance_id"], hero["id"]),
            ).fetchone()
        self.assertEqual(
            (moved_hero["x"], moved_hero["y"], moved_hero["z"]),
            (event["source_x"], event["source_y"], event["source_z"]),
        )
        self.assertEqual([], list(self.journal.records()))

    def test_manual_owner_exit_flushes_before_returning_owned_hero_only(self):
        from wakfu_server.characters import heroes

        self.members, self.party_id = self.party(2)
        owner, other_account_member = self.members
        hero = self.store.create_character(owner["account"], "Dng Exit Companion")
        heroes.add(
            self.store,
            owner["account"],
            owner["generation"],
            owner["character"]["id"],
            hero["id"],
        )
        run = self.enter(owner)
        self.assertIn(hero["id"], run["members"])
        self.assertIn(other_account_member["character"]["id"], run["members"])
        self._refresh_positions()
        moved_owner = self._move(owner)

        with self.store.connection() as db:
            inventory_before = {
                identity: db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (identity,),
                ).fetchone()["n"]
                for identity in (owner["character"]["id"], hero["id"])
            }
        body = struct.pack(">qiBi", 26843, 2517, 0, 2)
        source = {
            "id": 26843,
            "map_id": 1086,
            "x": 4,
            "y": -12,
            "z": 0,
            "destinations": [
                {
                    "destination_id": 2517,
                    "map_id": 527,
                    "x": -245,
                    "y": -90,
                    "z": 0,
                    "criterion": "",
                    "cyZ": -1,
                    "cyX": 0,
                    "cyW": 0,
                    "item_reference": 0,
                    "native_altitude_walkable": True,
                }
            ],
        }
        with patch(
            "wakfu_server.maps.dungeon_exit.generic_transports.source",
            return_value=source,
        ):
            result = dungeon_exit.leave(
                self.store,
                owner["account"],
                owner["generation"],
                owner["character"]["id"],
                body,
                source_allowed=lambda _character, _source: True,
                in_fight=lambda _identity: False,
                positions=self.positions,
            )

        owner_saved = self.store.character(owner["account"], owner["character"]["id"])
        hero_saved = self.store.character(owner["account"], hero["id"])
        other_saved = self.store.character(
            other_account_member["account"], other_account_member["character"]["id"]
        )
        self.assertEqual((527, 0), (owner_saved["map_id"], owner_saved["instance_id"]))
        self.assertEqual((527, 0), (hero_saved["map_id"], hero_saved["instance_id"]))
        self.assertEqual(
            (run["instance_id"], 1086),
            (other_saved["instance_id"], other_saved["map_id"]),
        )
        self.assertEqual(0, result["instance_id"])
        with self.store.connection() as db:
            event = db.execute(
                "SELECT source_x,source_y,source_z FROM dungeon_transition_outbox "
                "WHERE instance_id=%s AND character_id=%s AND transition_kind='exit'",
                (run["instance_id"], owner["character"]["id"]),
            ).fetchone()
            inventory_after = {
                identity: db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (identity,),
                ).fetchone()["n"]
                for identity in (owner["character"]["id"], hero["id"])
            }
        self.assertEqual(
            (moved_owner["x"], moved_owner["y"], moved_owner["z"]),
            (event["source_x"], event["source_y"], event["source_z"]),
        )
        self.assertEqual(inventory_before, inventory_after)
        self.assertEqual([], list(self.journal.records()))

    def test_manual_door_rejects_raced_member_outside_locked_account_scope(self):
        # The third character is an existing party member who was not in the
        # initial active instance roster. Rejoin it after the wrapper snapshots
        # and flushes account scope, before the SQL door operation locks members.
        self.members, self.party_id = self.party(3)
        self.instance = self.enter(self.members[0])
        self.instance_id = self.instance["instance_id"]
        self._initialize_run()
        outsider = self.members[2]
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_instance_members SET status='removed',ended_at=%s "
                "WHERE instance_id=%s AND character_id=%s",
                (self.store.now(), self.instance_id, outsider["character"]["id"]),
            )
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-245,y=-90,z=2 WHERE id=%s",
                (outsider["character"]["id"],),
            )
        self._refresh_positions()
        self._authorize_first_room()
        with self.store.connection() as db:
            revision_before = db.execute(
                "SELECT revision FROM dungeon_instances WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()["revision"]
        original_flush = self.positions.flush
        inserted = []

        def flush_then_race(*args, **kwargs):
            result = original_flush(*args, **kwargs)
            if not inserted:
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE dungeon_instance_members SET status='active',ended_at=NULL "
                        "WHERE instance_id=%s AND character_id=%s",
                        (self.instance_id, outsider["character"]["id"]),
                    )
                    db.execute(
                        "UPDATE characters SET map_id=1086,instance_id=%s,x=4,y=-12,z=0 WHERE id=%s",
                        (self.instance_id, outsider["character"]["id"]),
                    )
                inserted.append(True)
            return result

        self.positions.flush = flush_then_race
        try:
            with self.assertRaisesRegex(ValueError, "outside position barrier"):
                self._advance(positions=self.positions)
        finally:
            self.positions.flush = original_flush

        with self.store.connection() as db:
            revision_after = db.execute(
                "SELECT revision FROM dungeon_instances WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()["revision"]
        self.assertEqual(revision_before, revision_after)
        self.assertEqual([], self._door_outbox())
