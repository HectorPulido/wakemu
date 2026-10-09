"""Aborted room encounters retain audit history and admit a fresh retry."""
from psycopg.errors import UniqueViolation
from postgres_case import PostgresCase
from test_dungeon_progression import DungeonProgressionPostgresTests as Fixture
from wakfu_server import fight_store
from wakfu_server.maps.dungeon_progression import bind_encounter
from wakfu_server.maps.dungeon_fight_binding import abort_room_encounter


class DungeonAbortBindingTests(PostgresCase):
    install_context_policy = Fixture.install_context_policy
    player = Fixture.player
    party = Fixture.party
    create = Fixture.create

    def setUp(self):
        super().setUp()
        from types import SimpleNamespace
        from wakfu_server.maps.dungeon_progression import initialize_run

        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="a" * 64,
            rooms=(SimpleNamespace(order=1, monsters=(monster,)),),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)

    def make_bound_fight(self):
        member = self.members[0]

        def bind(db, identity):
            bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                member["character"]["id"],
                identity,
                player_team=0,
            )

        return fight_store.create(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            on_created=bind,
        )

    def test_abort_preserves_room_revision_and_history_then_allows_retry(self):
        identity = self.make_bound_fight()
        member = self.members[0]
        self.assertTrue(
            fight_store.abort(
                self.store,
                member["account"],
                member["character"]["id"],
                identity,
                expected_generation=member["generation"],
                on_aborted=abort_room_encounter,
            )
        )
        with self.store.connection() as db:
            receipt = abort_room_encounter(db, identity)
            self.assertTrue(receipt["replay"])
            run = db.execute(
                "SELECT current_room,revision,status FROM dungeon_room_runs WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()
            self.assertEqual(
                dict(run), dict(current_room=1, revision=1, status="active")
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_room_encounters WHERE fight_id=%s",
                    (identity,),
                ).fetchone()["status"],
                "aborted",
            )
        fresh = self.make_bound_fight()
        self.assertNotEqual(identity, fresh)

    def test_binding_failure_rolls_back_second_identity(self):
        self.make_bound_fight()
        with self.assertRaises(UniqueViolation):
            self.make_bound_fight()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_fights").fetchone()["n"], 1
            )

    def test_startup_reconciles_only_orphan_aborted_encounter_once(self):
        from wakfu_server.maps.dungeon_fight_binding import reconcile_aborted_encounters

        identity = self.make_bound_fight()
        with self.store.connection() as db:
            self.assertEqual(reconcile_aborted_encounters(db), ())
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s", (identity,)
            )
        with self.store.connection() as db:
            results = reconcile_aborted_encounters(db)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["aborted"])
            self.assertFalse(results[0]["replay"])
            self.assertEqual(results[0]["current_room"], 1)
            self.assertEqual(results[0]["revision"], 1)
        with self.store.connection() as db:
            self.assertEqual(reconcile_aborted_encounters(db), ())
            self.assertEqual(
                db.execute(
                    "SELECT current_room,revision,status FROM dungeon_room_runs WHERE instance_id=%s",
                    (self.instance_id,),
                ).fetchone(),
                dict(current_room=1, revision=1, status="active"),
            )
        replacement = self.make_bound_fight()
        with self.store.connection() as db:
            self.assertEqual(reconcile_aborted_encounters(db), ())
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_room_encounters WHERE fight_id=%s",
                    (replacement,),
                ).fetchone()["status"],
                "active",
            )

    def test_scoped_lazy_binding_releases_only_selected_instance(self):
        from types import SimpleNamespace
        from wakfu_server.maps.dungeon_progression import initialize_run
        from wakfu_server.maps.dungeon_fight_binding import bind_room_group

        first_members, first_party, first_instance = (
            self.members,
            self.party_id,
            self.instance_id,
        )
        first = self.make_bound_fight()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        other_instance = self.instance_id
        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="b" * 64,
            rooms=(SimpleNamespace(order=1, monsters=(monster,)),),
        )
        with self.store.connection() as db:
            initialize_run(db, other_instance, self.party_id, plan)
        other = self.make_bound_fight()
        self.members, self.party_id, self.instance_id = (
            first_members,
            first_party,
            first_instance,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id IN (%s,%s)",
                (first, other),
            )
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) VALUES(1086,%s,99,'[]'::jsonb,'available')",
                (first_instance,),
            )
            db.execute(
                "INSERT INTO dungeon_room_spawn_receipts(instance_id,room_order,asset_map_id,group_id) VALUES(%s,1,1086,99)",
                (first_instance,),
            )
        member = first_members[0]
        replacement = fight_store.create(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            on_created=lambda db, identity: bind_room_group(
                db, (1086, first_instance, 99), member["character"]["id"], identity
            ),
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_room_encounters WHERE fight_id=%s",
                    (first,),
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_room_encounters WHERE fight_id=%s",
                    (other,),
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_room_encounters WHERE fight_id=%s",
                    (replacement,),
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT current_room,revision FROM dungeon_room_runs WHERE instance_id=%s",
                    (first_instance,),
                ).fetchone(),
                dict(current_room=1, revision=1),
            )
