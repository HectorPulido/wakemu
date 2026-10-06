from contextlib import contextmanager
from psycopg import Cursor
from postgres_case import PostgresCase
from wakfu_server import health_store


class RecordingCursor(Cursor):
    def execute(self, query, params=None, *, prepare=None, binary=False):
        self.statements.append(query)
        return super().execute(query, params, prepare=prepare, binary=binary)


class TickWritesTests(PostgresCase):
    @contextmanager
    def traced_connection(self):
        cursor_type = type(
            "TestRecordingCursor",
            (RecordingCursor,),
            {
                "statements": self.statements,
            },
        )
        with self.store.database.connection() as db:
            db.cursor_factory = cursor_type
            yield db

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1
        self.statements = []
        self.store.connection = self.traced_connection
        self.account = self.store.register("one", "local-password")["id"]
        self.generation = self.store.begin_session(self.account)
        char = self.store.create_character(self.account, "One")
        self.char = self.store.select_character(
            self.account, self.generation, char["id"]
        )
        self.char = health_store.initialize(
            self.store,
            self.account,
            self.generation,
            char["id"],
            coefficient=1,
            now_ms=0,
        )

    def tick(self, hp, now):
        return health_store.tick(
            self.store, self.account, self.generation, self.char["id"], hp, now_ms=now
        )

    def writes(self):
        return [
            s
            for s in self.statements
            if s.lstrip()
            .upper()
            .startswith(("UPDATE", "INSERT", "DELETE", "CREATE", "ALTER"))
        ]

    def test_full_dead_and_stopped_ticks_are_read_only(self):
        for hp, coefficient in (
            (self.char["max_hp"], 1),
            (0, 1),
            (self.char["max_hp"] - 5, 0),
        ):
            self.char = health_store.sync(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                self.char["hp"],
                hp,
                coefficient=coefficient,
                now_ms=0,
            )
            self.statements.clear()
            for now in (100, 1000, 5000, 10000):
                self.assertEqual(self.tick(hp, now)["hp"], hp)
            self.assertEqual(self.writes(), [])

    def test_skipped_fraction_ticks_keep_baseline_and_highwater_clock(self):
        hp = self.char["max_hp"] - 10
        self.char = health_store.sync(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            self.char["hp"],
            hp,
            coefficient=1,
            now_ms=0,
        )
        self.statements.clear()
        for now in (100, 500, 1000, 1500):
            self.assertEqual(self.tick(hp, now)["hp"], hp)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.tick(hp, 2000)["hp"], hp + 1)
        self.assertEqual(len(self.writes()), 2)  # HP and last_at updates.
        self.statements.clear()
        self.assertEqual(self.tick(hp + 1, 3000)["hp"], hp + 1)
        self.assertEqual(self.writes(), [])
        with self.assertRaisesRegex(ValueError, "clock"):
            self.tick(hp + 1, 2500)
        self.assertEqual(self.tick(hp + 1, 6000)["hp"], hp + 2)
        with self.store.connection() as db:
            state = db.execute(
                "SELECT * FROM character_regeneration WHERE character_id=%s",
                (self.char["id"],),
            ).fetchone()
            self.assertEqual(
                (state["initial_hp"], state["started_at"].timestamp()), (hp, 0)
            )

    def test_replaced_generation_is_checked_even_on_full_hp_noop(self):
        self.store.begin_session(self.account)
        self.statements.clear()
        with self.assertRaisesRegex(ValueError, "session"):
            self.tick(self.char["hp"], 1000)
        self.assertEqual(self.writes(), [])
