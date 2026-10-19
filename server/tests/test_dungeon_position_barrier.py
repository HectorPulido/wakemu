"""PostgreSQL/Redis regressions for automatic dungeon position barriers."""
import os
import struct
import threading
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
import test_dungeon_instances
from wakfu_server.maps import dungeon_auto_transition
from wakfu_server import dungeon_transport, player_parties
import test_dungeon_instances
from wakfu_server.maps.dungeon_position_barrier import run_auto_transition
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    settle_encounter,
)
from wakfu_server.position_buffer import Positions
from wakfu_server.position_redis import Journal, PositionJournalError, RedisPositions


class DungeonPositionBarrierPostgresTests(PostgresCase):
    """Use real disposable SQL schemas and an isolated Redis key namespace."""

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
        self.instance_id = self.enter(self.members[0])["instance_id"]
        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="d" * 64,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)
        self.fight_id = self._settle_victory()
        self.namespace = "wakfu:test:dungeon-position-barrier:" + uuid.uuid4().hex
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
        leases = {
            (member["account"], member["generation"], member["character"]["id"])
            for member in self.members
        }
        self.positions = RedisPositions(
            self.store, lease_active=lambda *key: key in leases, journal=self.journal
        )

    @property
    def topology(self):
        return {
            "asset_map_id": 1086,
            "rooms": [
                {"order": 1, "anchor": (4, -12, 0)},
                {"order": 2, "anchor": (152, -10, 0)},
            ],
            "doors": [
                {"source_room": 1, "destination_room": 2, "anchor": (152, -10, 0)}
            ],
        }

    def _settle_victory(self):
        member = self.members[0]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
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
            settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
        return fight_id

    def _attach_and_move(self, member, delta=1):
        character = self.store.character(member["account"], member["character"]["id"])
        self.positions.attach(member["account"], member["generation"], character)
        return self.positions.move(
            member["account"],
            member["generation"],
            character["id"],
            character,
            {
                "x": character["x"] + delta,
                "y": character["y"] + 2,
                "z": character["z"],
                "direction": 5,
            },
        )

    def _transition(self, **overrides):
        transition = overrides.pop("transition", dungeon_auto_transition.advance)
        return run_auto_transition(
            self.store,
            self.positions,
            self.instance_id,
            self.fight_id,
            transition=transition,
            topology=self.topology,
            in_fight=lambda _character_id: False,
            **overrides,
        )

    def test_dirty_redis_movement_is_committed_before_travel_and_rebind_allows_attach(
        self,
    ):
        member = self.members[0]
        moved = self._attach_and_move(member)
        self.assertEqual(1, len(list(self.journal.records())))
        result = self._transition()
        self.assertFalse(result.get("deferred"))
        row = self.store.character(member["account"], member["character"]["id"])
        self.assertEqual(
            (1086, self.instance_id, 152, -10, 0),
            tuple(row[k] for k in ("map_id", "instance_id", "x", "y", "z")),
        )
        event = next(
            e for e in self._outbox() if e["character_id"] == member["character"]["id"]
        )
        self.assertEqual(
            (moved["x"], moved["y"], moved["z"]),
            (event["source_x"], event["source_y"], event["source_z"]),
        )
        entry = self.positions.entries[
            (member["account"], member["generation"], member["character"]["id"])
        ]
        self.assertFalse(entry["dirty"])
        self.assertEqual(row["x"], entry["persisted"]["x"])
        # Bootstrap may attach the authoritative destination, then the next move
        # must flush against that new baseline rather than the old room.
        self.positions.attach(member["account"], member["generation"], row)
        fresh = self.positions.move(
            member["account"],
            member["generation"],
            row["id"],
            row,
            {"x": row["x"] + 1, "y": row["y"], "z": row["z"]},
        )
        self.positions.flush(account_id=member["account"])
        saved = self.store.character(member["account"], row["id"])
        self.assertEqual(fresh["x"], saved["x"])
        self.assertEqual([], list(self.journal.records()))

    def test_busy_account_defers_without_flushing_or_travel(self):
        member = self.members[0]
        moved = self._attach_and_move(member)
        acquired, release = threading.Event(), threading.Event()

        def hold_lock():
            with self.positions.account_barrier(member["account"]):
                acquired.set()
                release.wait(3)

        thread = threading.Thread(target=hold_lock)
        thread.start()
        self.assertTrue(acquired.wait(2))
        try:
            result = self._transition()
        finally:
            release.set()
            thread.join(3)
        self.assertTrue(result["deferred"])
        self.assertEqual("position_owner_busy", result["reason"])
        saved = self.store.character(member["account"], member["character"]["id"])
        self.assertNotEqual(moved["x"], saved["x"])
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]))
        self.assertEqual([], self._outbox())

    def test_postgres_cas_conflict_preserves_dirty_journal_and_skips_transition(self):
        member = self.members[0]
        self._attach_and_move(member)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=x+7 WHERE id=%s", (member["character"]["id"],)
            )
        callback_called = []
        with self.assertRaisesRegex(ValueError, "storage CAS conflict"):
            self._transition(
                transition=lambda *args, **kwargs: callback_called.append(True)
            )
        self.assertEqual([], callback_called)
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]))
        self.assertEqual(1, len(list(self.journal.records())))
        self.assertEqual([], self._outbox())

    def test_revoked_selected_lease_preserves_journal_and_skips_transition(self):
        member = self.members[0]
        self._attach_and_move(member)
        self.positions.lease_active = lambda *_key: False
        called = []
        with self.assertRaisesRegex(ValueError, "Live lease unavailable"):
            self._transition(transition=lambda *args, **kwargs: called.append(True))
        self.assertEqual([], called)
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]))
        self.assertEqual(1, len(list(self.journal.records())))
        self.assertEqual([], self._outbox())

    def test_redis_ack_failure_keeps_transition_from_traveling(self):
        member = self.members[0]
        self._attach_and_move(member)
        original_ack = self.journal.ack
        self.journal.ack = lambda *_args: False
        called = []
        try:
            with self.assertRaisesRegex(
                PositionJournalError, "changed after committed flush"
            ):
                self._transition(transition=lambda *args, **kwargs: called.append(True))
        finally:
            self.journal.ack = original_ack
        self.assertEqual([], called)
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]) is False)
        self.assertEqual(1, len(list(self.journal.records())))
        self.assertEqual([], self._outbox())

    def _outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT character_id,source_x,source_y,source_z FROM dungeon_transition_outbox WHERE instance_id=%s AND transition_kind='door' ORDER BY character_id",
                (self.instance_id,),
            ).fetchall()


class DungeonEntryPositionBarrierPostgresTests(PostgresCase):
    install_context_policy = (
        test_dungeon_instances.DungeonInstanceTests.install_context_policy
    )
    player = test_dungeon_instances.DungeonInstanceTests.player
    party = test_dungeon_instances.DungeonInstanceTests.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.members, self.party_id = self.party(2)
        self.leader, self.companion = self.members
        self.body = struct.pack(">qiBi", 26842, 2504, 0, 2)
        self.namespace = "wakfu:test:dungeon-entry-position-barrier:" + uuid.uuid4().hex
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
        leases = {
            (member["account"], member["generation"], member["character"]["id"])
            for member in self.members
        }
        self.positions = RedisPositions(
            self.store, lease_active=lambda *key: key in leases, journal=self.journal
        )

    def _enter(self, *, initialize_instance=None):
        return dungeon_transport.enter(
            self.store,
            self.leader["account"],
            self.leader["generation"],
            self.leader["character"]["id"],
            527,
            self.body,
            source_allowed=lambda *_: True,
            criterion_allowed=lambda *_: True,
            initialize_instance=initialize_instance,
            positions=self.positions,
        )

    def _outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT character_id,source_map_id,source_instance_id,source_x,source_y,source_z,"
                "destination_map_id,destination_instance_id,destination_x,destination_y,destination_z "
                "FROM dungeon_transition_outbox ORDER BY character_id"
            ).fetchall()

    def _grant_entry_item(self, character_id):
        with self.store.connection() as db:
            bag = db.execute(
                "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                "VALUES(%s,1,0,30,0) ON CONFLICT(character_id,kind) "
                "DO UPDATE SET capacity=excluded.capacity RETURNING uid",
                (character_id,),
            ).fetchone()["uid"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,15133,1,%s,0) RETURNING uid",
                (character_id, bag),
            ).fetchone()["uid"]

    def test_entry_flushes_dirty_companion_before_atomic_party_travel_and_rebinds(self):
        member = self.companion
        character = self.store.character(member["account"], member["character"]["id"])
        self.positions.attach(member["account"], member["generation"], character)
        moved = self.positions.move(
            member["account"],
            member["generation"],
            character["id"],
            character,
            {
                "x": character["x"] + 3,
                "y": character["y"] + 2,
                "z": character["z"],
                "direction": 6,
            },
        )

        entered = self._enter()
        rows = {row["character_id"]: row for row in self._outbox()}
        self.assertEqual({m["character"]["id"] for m in self.members}, set(rows))
        event = rows[member["character"]["id"]]
        self.assertEqual(
            (moved["x"], moved["y"], moved["z"]),
            (event["source_x"], event["source_y"], event["source_z"]),
        )
        self.assertEqual(
            (1086, entered["instance_id"], 4, -12, 0),
            tuple(
                event[k]
                for k in (
                    "destination_map_id",
                    "destination_instance_id",
                    "destination_x",
                    "destination_y",
                    "destination_z",
                )
            ),
        )
        saved = self.store.character(member["account"], member["character"]["id"])
        key = (member["account"], member["generation"], member["character"]["id"])
        self.assertFalse(self.positions.entries[key]["dirty"])
        self.positions.attach(member["account"], member["generation"], saved)
        next_move = self.positions.move(
            member["account"],
            member["generation"],
            saved["id"],
            saved,
            {"x": saved["x"] + 1, "y": saved["y"], "z": saved["z"]},
        )
        self.positions.flush(account_id=member["account"])
        self.assertEqual(
            next_move["x"], self.store.character(member["account"], saved["id"])["x"]
        )
        self.assertEqual([], list(self.journal.records()))

    def test_raced_party_account_is_rejected_before_fee_or_travel(self):
        third = self.player("raced")
        invitation = player_parties.invite(
            self.store,
            self.leader["account"],
            self.leader["generation"],
            self.leader["character"]["id"],
            third["character"]["id"],
        )
        uid = self._grant_entry_item(self.leader["character"]["id"])
        native = dungeon_transport.resolve_request(527, self.body)
        native["native_destination"] = dict(
            native["native_destination"], item_reference=15133, cyW=1
        )
        original_flush = self.positions.flush
        raced = []

        def add_party_member_then_flush(**scope):
            if not raced:
                player_parties.answer(
                    self.store,
                    third["account"],
                    third["generation"],
                    third["character"]["id"],
                    invitation,
                    True,
                )
                raced.append(True)
            return original_flush(**scope)

        self.positions.flush = add_party_member_then_flush
        initializer_calls = []
        with patch.object(dungeon_transport, "resolve_request", return_value=native):
            with self.assertRaisesRegex(ValueError, "outside position barrier"):
                self._enter(
                    initialize_instance=lambda *_: initializer_calls.append(True)
                )
        self.assertEqual([True], raced)
        self.assertEqual([], initializer_calls)
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox"
                ).fetchone()["n"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
                ).fetchone()["quantity"],
            )
            positions = list(
                db.execute("SELECT map_id,instance_id FROM characters ORDER BY id")
            )
        self.assertTrue(
            all((row["map_id"], row["instance_id"]) == (527, 0) for row in positions)
        )
