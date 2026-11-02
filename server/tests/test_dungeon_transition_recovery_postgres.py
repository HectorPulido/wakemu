"""One isolated PostgreSQL/Redis journey for recovery of a pinned Pohl run."""
import json
import os
from pathlib import Path
import unittest
import uuid
from types import SimpleNamespace

from postgres_case import PostgresCase
import test_dungeon_instances
from wakfu_server.maps import dungeon_auto_transition, dungeon_runtime_config
from wakfu_server.maps.dungeon_position_barrier import run_auto_transition
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    settle_encounter,
)


def _fixture_path():
    local = (
        Path(__file__).resolve().parent
        / "fixtures/dungeon_transition_recovery/bad184v5.json"
    )
    packaged = Path("/app/tests/fixtures/dungeon_transition_recovery/bad184v5.json")
    return local if local.is_file() else packaged


class DungeonTransitionRecoveryPostgresTests(PostgresCase):
    """Keep a committed win and real Redis position journal across repair."""

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
        self.config = json.loads(_fixture_path().read_text(encoding="utf8"))[
            "configuration"
        ]
        self.topology = self.config["topology"]
        self.members, self.party_id = self.party(2)
        self.instance_id = self.enter(self.members[0])["instance_id"]
        self._pin_legacy_configuration()
        self.fight_id = self._settle_room_one_victory()
        self._setup_positions()

    def _pin_legacy_configuration(self):
        context = self.config["context_policy"]
        fields = tuple(context)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_context_policy_versions("
                + ",".join(fields)
                + ") VALUES ("
                + ",".join(["%s"] * len(fields))
                + ")",
                tuple(context[field] for field in fields),
            )
            db.execute(
                "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) "
                "VALUES(%s,%s,%s::jsonb)",
                (
                    self.config["route"]["key"],
                    self.config["version"],
                    json.dumps(self.config),
                ),
            )
            db.execute(
                "UPDATE dungeon_instances SET template_id=%s,definition_id=%s,"
                "entry_map_id=%s,entry_object_id=%s,entry_destination_id=%s,start_map_id=%s,"
                "context_route_key=%s,context_policy_version=%s WHERE instance_id=%s",
                (
                    self.config["route"]["template_id"],
                    self.config["route"]["definition_id"],
                    self.config["route"]["entry_map_id"],
                    self.config["route"]["entry_object_id"],
                    self.config["route"]["destination_id"],
                    self.config["route"]["start_map_id"],
                    self.config["route"]["key"],
                    self.config["version"],
                    self.instance_id,
                ),
            )
            room = self.topology["rooms"][0]
            anchor = room["anchor"]
            for member in self.members:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        self.topology["asset_map_id"],
                        self.instance_id,
                        *anchor,
                        member["character"]["id"],
                    ),
                )
            plan = dungeon_runtime_config.plan_from_configuration(self.config)
            initialize_run(db, self.instance_id, self.party_id, plan)

    def _settle_room_one_victory(self):
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
        self.assertEqual(2, receipt["current_room"])
        return fight_id

    def _setup_positions(self):
        redis_url = os.environ.get("WAKFU_REDIS_TEST_URL") or os.environ.get(
            "WAKFU_REDIS_URL"
        )
        if not redis_url:
            self.skipTest("Local Redis URL required for recovery position journal")
        import redis

        # Match local_game_server's production import path. Importing the
        # filesystem package name here would create a second position_buffer
        # module identity and a different PositionOwnerBusy class.
        from wakfu_server.position_redis import Journal, RedisPositions

        self.redis = redis.Redis.from_url(
            redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        self.redis.ping()
        self.namespace = "wakfu:test:dungeon-recovery:" + uuid.uuid4().hex
        self.addCleanup(self.redis.delete, self.namespace)
        self.journal = Journal(self.redis, namespace=self.namespace)
        leases = {
            (m["account"], m["generation"], m["character"]["id"]) for m in self.members
        }
        self.positions = RedisPositions(
            self.store, lease_active=lambda *key: key in leases, journal=self.journal
        )
        for member in self.members:
            character = self.store.character(
                member["account"], member["character"]["id"]
            )
            self.positions.attach(member["account"], member["generation"], character)
        member = self.members[0]
        character = self.store.character(member["account"], member["character"]["id"])
        self.positions.move(
            member["account"],
            member["generation"],
            character["id"],
            character,
            {
                "x": character["x"] + 1,
                "y": character["y"],
                "z": character["z"],
                "direction": character["direction"],
            },
        )

    def _active_fight_for(self, character_id):
        with self.store.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                    "WHERE p.character_id=%s AND f.status='active' LIMIT 1",
                    (character_id,),
                ).fetchone()
                is not None
            )

    def _transition(self):
        return run_auto_transition(
            self.store,
            self.positions,
            self.instance_id,
            self.fight_id,
            transition=dungeon_auto_transition.advance,
            topology=self.topology,
            in_fight=self._active_fight_for,
        )

    def test_verified_repair_preserves_victory_and_redis_checkpoint_idempotently(self):
        member = self.members[1]
        with self.store.connection() as db:
            active_fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (active_fight, member["character"]["id"], member["account"]),
            )

        deferred = self._transition()
        self.assertTrue(deferred["deferred"])
        self.assertEqual("members_not_ready", deferred["reason"])
        # The barrier flushed and ACKed the actual dirty movement before the
        # combat check; no destination or door event was committed yet.
        self.assertEqual([], list(self.journal.records()))
        with self.store.connection() as db:
            saved_position = db.execute(
                "SELECT x,y FROM characters WHERE id=%s",
                (self.members[0]["character"]["id"],),
            ).fetchone()
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s",
                (active_fight,),
            )
        self.assertEqual(-1, saved_position["x"])
        self.assertEqual(-20, saved_position["y"])

        first = self._transition()
        self.assertFalse(first.get("deferred"))
        self.assertFalse(first["replay"])
        self.assertEqual("verified_room_anchor", first["recovery"]["mode"])
        self.assertEqual([-5, -55, -15], first["recovery"]["verified_anchor"])
        replay = self._transition()
        self.assertTrue(replay["replay"])
        self.assertEqual(first["revision"], replay["revision"])
        expected = (1369, self.instance_id, -5, -55, -15)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s) ORDER BY id",
                ([m["character"]["id"] for m in self.members],),
            ).fetchall()
            receipt = db.execute(
                "SELECT status,result FROM dungeon_room_encounters WHERE fight_id=%s",
                (self.fight_id,),
            ).fetchone()
            run = db.execute(
                "SELECT current_room,revision,status FROM dungeon_room_runs WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
            outbox = db.execute(
                "SELECT character_id,status,transition_kind,destination_map_id,destination_x,destination_y,destination_z "
                "FROM dungeon_transition_outbox WHERE instance_id=%s AND transition_kind='door' ORDER BY character_id",
                (self.instance_id,),
            ).fetchall()
        self.assertTrue(
            all(
                (r["map_id"], r["instance_id"], r["x"], r["y"], r["z"]) == expected
                for r in rows
            )
        )
        self.assertEqual(
            (2, 2, "active"), (run["current_room"], run["revision"], run["status"])
        )
        self.assertEqual("victory", receipt["status"])
        self.assertEqual(
            first["revision"], receipt["result"]["auto_transition_revision"]
        )
        self.assertEqual(2, len(outbox))
        self.assertTrue(
            all(
                r["status"] == "pending" and r["destination_map_id"] == 1369
                for r in outbox
            )
        )
        self.assertEqual(2, sum(r["transition_kind"] == "door" for r in outbox))
        self.assertEqual([], list(self.journal.records()))
        for member in self.members:
            key = (member["account"], member["generation"], member["character"]["id"])
            self.assertFalse(self.positions.entries[key]["dirty"])
            self.assertEqual(
                expected[2:],
                tuple(
                    self.positions.entries[key]["current"][k] for k in ("x", "y", "z")
                ),
            )
