"""Room spawn receipts bind deterministic group registration to progression."""

from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from test_dungeon_progression import DungeonProgressionPostgresTests as Fixture
from wakfu_server import combat_group_store, dungeon_room_spawns
from wakfu_server.maps.dungeon_progression import initialize_run


class DungeonRoomSpawnReceiptTests(PostgresCase):
    install_context_policy = Fixture.install_context_policy
    player = Fixture.player
    party = Fixture.party
    create = Fixture.create
    make_fight = Fixture.make_fight
    bind = Fixture.bind
    finish = Fixture.finish

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        self.groups = combat_group_store.PersistentGroups(self.store)
        monster = SimpleNamespace(
            ref_id=6,
            count=1,
            native_min_level=4,
            native_max_level=8,
            role="monster",
        )
        rooms = tuple(
            SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
        )
        with self.store.connection() as db:
            initialize_run(
                db,
                self.instance_id,
                self.party_id,
                SimpleNamespace(
                    roster_ready=True,
                    document_sha256="c" * 64,
                    rooms=rooms,
                ),
            )

    def geometry(self, anchor):
        anchor = tuple(anchor)
        cell = (anchor[0] + 1, anchor[1], anchor[2])
        return {"cells": [anchor, cell], "edges": [[anchor, cell]]}

    def ensure(self, anchor=(4, -12, 0), *, db=None):
        kwargs = dict(
            asset_map_id=1086,
            anchor=anchor,
            geometry=self.geometry(anchor),
            select_level=lambda native, _roster: native["min_level"],
            # This receipt fixture intentionally has only two synthetic cells;
            # formation capacity is exercised against native terrain elsewhere.
            player_slots=0,
        )
        if db is not None:
            return dungeon_room_spawns.ensure_room_group(
                db, self.groups, self.instance_id, **kwargs
            )
        with self.store.connection() as connection:
            return dungeon_room_spawns.ensure_room_group(
                connection, self.groups, self.instance_id, **kwargs
            )

    def advance_room(self):
        fight_id = self.make_fight(self.members[0])
        self.bind(fight_id)
        return self.finish(fight_id)

    def counts(self):
        with self.store.connection() as db:
            receipts = db.execute(
                "SELECT count(*) AS n FROM dungeon_room_spawn_receipts WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()["n"]
            groups = db.execute(
                "SELECT count(*) AS n FROM combat_groups WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()["n"]
        return receipts, groups

    def test_repeat_reuses_group_without_duplicate_rows(self):
        first = self.ensure()
        replay = self.ensure()
        self.assertFalse(first["replay"])
        self.assertTrue(replay["replay"])
        self.assertEqual(first["group_id"], replay["group_id"])
        self.assertEqual(first["members"], replay["members"])
        self.assertEqual((1, 1), self.counts())

    def test_defeat_retry_reuses_same_available_group(self):
        first = self.ensure()
        fight_id = self.make_fight(self.members[0])
        lease, _members = self.groups.claim(
            (1086, self.instance_id, first["group_id"]),
            self.members[0]["generation"],
            fight_id,
        )
        self.assertTrue(self.groups.finish(lease, defeated=False))
        retry = self.ensure()
        self.assertEqual(first["group_id"], retry["group_id"])
        self.assertEqual("available", retry["status"])
        self.assertTrue(retry["replay"])
        self.assertEqual((1, 1), self.counts())

    def test_room_advance_creates_a_distinct_group_identity(self):
        first = self.ensure()
        self.advance_room()
        second = self.ensure(anchor=(20, 20, 0))
        self.assertEqual(2, second["room_order"])
        self.assertNotEqual(first["group_id"], second["group_id"])
        self.assertEqual((2, 2), self.counts())

    def test_receipt_and_group_registration_roll_back_together(self):
        with self.assertRaisesRegex(RuntimeError, "force rollback"):
            with self.store.connection() as db:
                self.ensure(db=db)
                raise RuntimeError("force rollback")
        self.assertEqual((0, 0), self.counts())
        self.assertFalse(self.ensure()["replay"])
        self.assertEqual((1, 1), self.counts())

    def test_completed_run_does_not_spawn_another_group(self):
        self.advance_room()
        self.advance_room()
        self.assertIsNone(self.ensure(anchor=(40, 40, 0)))
        self.assertEqual((0, 0), self.counts())
