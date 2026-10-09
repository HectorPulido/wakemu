"""Fight identity creation callbacks share participant commit and rollback."""
from postgres_case import PostgresCase
from test_dungeon_progression import DungeonProgressionPostgresTests as Fixture
from wakfu_server import fight_store


class FightCreationCallbackTests(PostgresCase):
    player = Fixture.player

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.member = self.player()

    def create(self, callback=None):
        return fight_store.create(
            self.store,
            self.member["account"],
            self.member["generation"],
            self.member["character"]["id"],
            on_created=callback,
        )

    def test_callback_observes_owned_participant_before_commit(self):
        observed = []

        def callback(db, fight_id):
            row = db.execute(
                "SELECT character_id,team FROM combat_fight_participants WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()
            observed.append((fight_id, row["character_id"], row["team"]))

        fight_id = self.create(callback)
        self.assertEqual(observed, [(fight_id, self.member["character"]["id"], 0)])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"],
                "placement",
            )

    def test_callback_failure_rolls_back_identity_and_participant(self):
        observed = []

        def callback(db, fight_id):
            observed.append(fight_id)
            raise ValueError("Binding denied")

        with self.assertRaisesRegex(ValueError, "Binding denied"):
            self.create(callback)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT id FROM combat_fights WHERE id=%s", (observed[0],)
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT fight_id FROM combat_fight_participants WHERE fight_id=%s",
                    (observed[0],),
                ).fetchone()
            )

    def test_default_creation_retains_ordinary_placement_identity(self):
        fight_id = self.create()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"],
                "placement",
            )

    def test_non_callable_callback_rejected_before_creation(self):
        with self.assertRaisesRegex(ValueError, "must be callable"):
            self.create(True)

    def test_abort_callback_runs_only_for_successful_authorized_abort(self):
        fight_id = self.create()
        seen = []
        callback = lambda db, identity: seen.append(identity)
        args = (
            self.store,
            self.member["account"],
            self.member["character"]["id"],
            fight_id,
        )
        self.assertFalse(
            fight_store.abort(*args, expected_generation="wrong", on_aborted=callback)
        )
        self.assertEqual(seen, [])
        self.assertTrue(
            fight_store.abort(
                *args,
                expected_generation=self.member["generation"],
                on_aborted=callback,
            )
        )
        self.assertEqual(seen, [fight_id])
        self.assertFalse(fight_store.abort(*args, on_aborted=callback))
        self.assertEqual(seen, [fight_id])

    def test_abort_callback_failure_rolls_back_abort(self):
        fight_id = self.create()

        def denied(db, identity):
            raise ValueError("Cleanup failed")

        with self.assertRaisesRegex(ValueError, "Cleanup failed"):
            fight_store.abort(
                self.store,
                self.member["account"],
                self.member["character"]["id"],
                fight_id,
                on_aborted=denied,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"],
                "placement",
            )
