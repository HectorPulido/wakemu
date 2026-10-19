"""Creation/selection cannot partially replace a company frozen in a dungeon."""
from contextlib import contextmanager
from threading import Thread, Event
import struct
import time
from postgres_case import PostgresCase
from wakfu_server.creation import create
from wakfu_server.characters import heroes
from wakfu_server.wire import appearance_section


class FrozenCompanySelectionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("frozen-company", "test-password")["id"]
        self.main = self.store.create_character(self.account, "Frozen Main")
        self.hero = self.store.create_character(self.account, "Frozen Hero")
        self.other = self.store.create_character(self.account, "Other Main")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        with self.store.connection() as db:
            self.party = db.execute(
                "SELECT p.* FROM player_parties p JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
                (self.main["id"],),
            ).fetchone()
            self.run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) "
                "VALUES(%s,%s,%s,1,1,527,1,1,312) RETURNING *",
                (self.party["id"], self.party["revision"], self.main["id"]),
            ).fetchone()
            self.freeze(db)

    def freeze(self, db):
        db.execute(
            "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,'leader') "
            "ON CONFLICT(instance_id,character_id) DO UPDATE SET "
            "party_id=excluded.party_id,session_generation=excluded.session_generation,"
            "party_revision=excluded.party_revision,role=excluded.role",
            (
                self.run["instance_id"],
                self.party["id"],
                self.main["id"],
                self.generation,
                self.party["revision"],
            ),
        )

    def snapshot(self):
        with self.store.connection() as db:
            return (
                db.execute(
                    "SELECT id,name,level,hp,max_hp,hp_damage,health_dead,map_id,instance_id FROM characters WHERE account_id=%s ORDER BY id",
                    (self.account,),
                ).fetchall(),
                db.execute(
                    "SELECT character_id FROM sessions WHERE account_id=%s",
                    (self.account,),
                ).fetchone(),
                db.execute(
                    "SELECT * FROM account_hero_rosters WHERE account_id=%s",
                    (self.account,),
                ).fetchone(),
                db.execute(
                    "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                    (self.account,),
                ).fetchall(),
            )

    def canonical_blobs(self):
        with self.store.connection() as db:
            return tuple(
                db.execute(
                    f"SELECT * FROM {table} WHERE character_id IN "
                    "(SELECT id FROM characters WHERE account_id=%s) ORDER BY character_id",
                    (self.account,),
                ).fetchall()
                for table in ("character_builds", "character_progression")
            )

    def test_protocol_creation_rejects_before_character_or_selection_changes(self):
        before = self.snapshot()
        canonical = self.canonical_blobs()
        name = b"Forbidden Alt"
        body = (
            struct.pack(">qhB", -1, 3, len(name))
            + name
            + b"\x01"
            + appearance_section({"sex": 0})
        )
        self.assertEqual(
            create(self.store, self.account, self.generation, body), (101, None)
        )
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.canonical_blobs(), canonical)
        # Explicit administrative creation does not request automatic selection.
        created = self.store.create_character(self.account, "Admin Alt")
        self.assertGreater(created["id"], self.other["id"])
        self.assertEqual(self.snapshot()[1:], before[1:])

    def test_frozen_selection_is_atomic_but_same_leader_reentry_is_allowed(self):
        before = self.snapshot()
        canonical = self.canonical_blobs()
        with self.assertRaisesRegex(ValueError, "frozen by an active dungeon"):
            self.store.select_character(self.account, self.generation, self.other["id"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.canonical_blobs(), canonical)
        selected = self.store.select_character(
            self.account, self.generation, self.main["id"]
        )
        self.assertEqual(selected["id"], self.main["id"])
        self.assertEqual(self.snapshot(), before)

    def test_dungeon_session_lock_serializes_selection_and_rechecks_membership(self):
        worker = self.reopen()
        original_connection = worker.connection
        observed = Event()
        result = []
        pid = []

        @contextmanager
        def connection():
            with original_connection() as db:
                db.execute("SET LOCAL lock_timeout='5s'")
                pid.append(db.info.backend_pid)
                observed.set()
                yield db

        worker.connection = connection

        def select():
            try:
                worker.select_character(self.account, self.generation, self.other["id"])
                result.append("unexpected success")
            except Exception as error:
                result.append(error)

        before = self.snapshot()
        thread = Thread(target=select)
        with self.store.connection() as db:
            db.execute(
                "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE",
                (self.account,),
            )
            thread.start()
            self.assertTrue(observed.wait(2))
            deadline = time.monotonic() + 2
            blocked = False
            while time.monotonic() < deadline:
                with self.store.connection() as observer:
                    row = observer.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",
                        (pid[0],),
                    ).fetchone()
                if row and row["wait_event_type"] == "Lock":
                    blocked = True
                    break
                time.sleep(0.01)
            self.assertTrue(
                blocked, "Selection must wait on the dungeon admission session fence"
            )
            self.freeze(db)
        thread.join(6)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], ValueError)
        self.assertIn("frozen by an active dungeon", str(result[0]))
        self.assertEqual(self.snapshot(), before)
