"""Real PostgreSQL company clocks exercised through the actual idle World gate."""
import ast
from contextlib import contextmanager
from psycopg import Cursor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import struct

from postgres_case import PostgresCase
from wakfu_server import health, health_policy, health_store
from wakfu_server import heroes


class CompanyExplorationRegenerationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1
        self.owner = self.store.register("company-regen-owner", "test-password")["id"]
        self.generation = self.store.begin_session(self.owner)
        self.members = [
            self.store.create_character(self.owner, name)
            for name in ("Regen Main", "Regen Hero One", "Regen Hero Two")
        ]
        for character in self.members:
            selected = self.store.select_character(
                self.owner, self.generation, character["id"]
            )
            selected = health_store.initialize(
                self.store,
                self.owner,
                self.generation,
                character["id"],
                exploration=True,
                now_ms=1000,
            )
            health_store.sync(
                self.store,
                self.owner,
                self.generation,
                character["id"],
                selected["hp"],
                1,
                coefficient=health.exploration_coefficient(selected["max_hp"], 1),
                now_ms=1000,
            )
        self.main = self.store.select_character(
            self.owner, self.generation, self.members[0]["id"]
        )
        for hero in self.members[1:]:
            heroes.add(
                self.store, self.owner, self.generation, self.main["id"], hero["id"]
            )
        self.before = self.rows()

    def rows(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT id,hp,max_hp,hp_damage,health_dead,map_id,instance_id,x,y,z "
                "FROM characters WHERE account_id=%s ORDER BY id",
                (self.owner,),
            ).fetchall()

    def gate(self, now, *, fight=None, combat_session=None, generation=None):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and "last_health_tick" in ast.unparse(n.test)
            and any(
                isinstance(c, ast.Call)
                and ast.unparse(c.func)
                in ("health_store.tick", "health_store.tick_company")
                for c in ast.walk(n)
            )
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            "<actual-company-world-health-gate>",
            "exec",
        )
        world = Mock()
        self.store.clock = lambda: now / 1000
        context = dict(
            loaded=True,
            character=dict(self.main),
            fight=fight,
            combat_session=combat_session,
            last_health_tick=0,
            time=SimpleNamespace(monotonic=lambda: 10),
            health_store=health_store,
            STORE=self.store,
            account_id=self.owner,
            generation=generation or self.generation,
            WORLD=world,
            health=health,
            record=Mock(),
        )
        exec(code, context)
        self.main = context["character"]
        return world

    def reset(self, *, dead=(), full=False):
        with self.store.connection() as db:
            for member in self.members:
                character = self.store.character(self.owner, member["id"], db)
                hp = 0 if member["id"] in dead else character["max_hp"] if full else 1
                health_policy.apply(db, character, hp)
                coefficient = (
                    0
                    if hp == 0
                    else health.exploration_coefficient(character["max_hp"], hp)
                )
                db.execute(
                    "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
                    "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
                    "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
                    "coefficient=excluded.coefficient,last_at=excluded.last_at",
                    (
                        member["id"],
                        hp,
                        health_store.timestamp(1000),
                        coefficient,
                        health_store.timestamp(1000),
                    ),
                )
        self.main = self.store.character(self.owner, self.members[0]["id"])

    def test_active_owned_company_regenerates_with_native_updates_and_all_fences(self):
        world = self.gate(5000)
        after = self.rows()
        self.assertTrue(
            all(row["hp"] > 1 for row in after),
            "The selected main and BOTH active owned heroes must regenerate",
        )
        for before, row in zip(self.before, after):
            self.assertEqual(
                tuple(before[k] for k in ("map_id", "instance_id", "x", "y", "z")),
                tuple(row[k] for k in ("map_id", "instance_id", "x", "y", "z")),
            )
            expected = health.regenerated(
                1,
                before["max_hp"],
                4000,
                health.exploration_coefficient(before["max_hp"], 1),
            )
            self.assertEqual(row["hp"], expected)
        messages = [
            call.args
            for call in world.update.call_args_list + world.broadcast.call_args_list
        ]
        hp_updates = [
            struct.unpack(">qii", call[-1]) for call in messages if call[-2] == 12436
        ]
        self.assertEqual({r["id"] for r in after}, {r[0] for r in hp_updates})
        for identity, hp, coefficient in hp_updates:
            row = next(r for r in after if r["id"] == identity)
            self.assertEqual(hp, row["hp"])
            self.assertEqual(
                coefficient, health.exploration_coefficient(row["max_hp"], 1)
            )
        self.gate(5000)
        self.assertEqual(self.rows(), after, "Same clock must not heal twice")
        with self.store.connection() as db:
            session = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (self.owner,)
            ).fetchone()
        self.assertEqual(session["character_id"], self.members[0]["id"])

        self.reset(dead=(self.members[2]["id"],))
        self.gate(9000)
        rows = self.rows()
        self.assertTrue(rows[2]["health_dead"])
        self.assertEqual(rows[2]["hp"], 0)
        self.assertGreater(rows[0]["hp"], 1)
        self.assertGreater(rows[1]["hp"], 1)

        self.reset()
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            for member in self.members:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                    "VALUES(%s,%s,%s,0,%s)",
                    (fight_id, member["id"], self.owner, self.generation),
                )
        self.gate(10000)
        self.assertTrue(
            all(row["hp"] == 1 for row in self.rows()),
            "Durable active combat must block idle healing",
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s", (fight_id,)
            )
        for phase in ("placement", "active", "finished"):
            self.gate(
                11000, fight=SimpleNamespace(phase=phase), combat_session=object()
            )
            self.assertTrue(all(row["hp"] == 1 for row in self.rows()))

        self.reset(full=True)
        statements = []
        original_connection = self.store.connection

        class TracedCursor(Cursor):
            def execute(self, query, params=None, *, prepare=None, binary=False):
                statements.append(str(query))
                return super().execute(query, params, prepare=prepare, binary=binary)

        @contextmanager
        def traced_connection():
            with original_connection() as db:
                db.cursor_factory = TracedCursor
                yield db

        full_rows = self.rows()
        with patch.object(self.store, "connection", traced_connection):
            healthy_world = self.gate(12000)
        self.assertEqual(
            len(statements), 1, "Healthy company should need one read-only statement"
        )
        self.assertNotIn("FOR UPDATE", statements[0].upper())
        self.assertTrue(statements[0].lstrip().upper().startswith("WITH"))
        healthy_world.update.assert_not_called()
        healthy_world.broadcast.assert_not_called()
        self.assertEqual(self.rows(), full_rows)
        with self.assertRaisesRegex(ValueError, "clock"):
            self.gate(11999)
        self.assertEqual(self.rows(), full_rows)
        self.reset()

        heroes.remove(
            self.store,
            self.owner,
            self.generation,
            self.main["id"],
            self.members[1]["id"],
        )
        self.gate(13000)
        rows = self.rows()
        self.assertEqual(
            rows[1]["hp"],
            1,
            "Removed owned character must not regenerate as an active hero",
        )
        self.assertGreater(rows[2]["hp"], 1)
        self.store.begin_session(self.owner)
        before_stale = self.rows()
        with self.assertRaises(ValueError):
            self.gate(14000)
        self.assertEqual(self.rows(), before_stale)
