"""Aborted Rift login uses canonical company departure and delivery custody."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server import heroes, rift_runtime, rift_transition_delivery as delivery
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.generic_transports import source as native_transport_source
from wakfu_server.position_buffer import Positions


class ClosedRiftLoginRecoveryTests(PostgresCase):
    def test_aborted_company_recovers_once_and_failed_transport_retains_intent(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        names = {"reconcile_closed_rift_login", "acknowledge_rift_login_bootstrap"}
        namespace = {}
        exec(
            compile(
                ast.Module(
                    body=[
                        deepcopy(n)
                        for n in tree.body
                        if isinstance(n, ast.FunctionDef) and n.name in names
                    ],
                    type_ignores=[],
                ),
                "World login recovery helpers",
                "exec",
            ),
            namespace,
        )
        recover = namespace["reconcile_closed_rift_login"]
        account = self.store.register("closed-rift-login", "test-password")["id"]
        main = self.store.create_character(account, "Recovermain")
        hero = self.store.create_character(account, "Recoverhero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        ids = [main["id"], hero["id"]]
        positions = Positions(
            self.store,
            lease_active=lambda a, g, c: (a, g) == (account, generation) and c in ids,
        )
        key = account, generation, main["id"]
        self.addCleanup(delivery._PENDING.pop, key, None)
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            portal = catalog["entrances"][0]
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (portal["map_id"], portal["x"], portal["y"], portal["z"], ids),
            )
        cell = min(published_geometry(catalog["map_id"]).cells)
        entry = delivery.enter(
            self.store,
            positions,
            account,
            generation,
            main["id"],
            portal["map_id"],
            struct.pack(">qHH", portal["object_id"], 11, 0),
            source_allowed=lambda row, source: all(
                row[k] == source[k] for k in ("map_id", "x", "y", "z")
            ),
            resolve_destination=lambda *_: dict(
                map_id=catalog["map_id"], x=cell[0], y=cell[1], z=cell[2]
            ),
            seed="closed-login-company",
        )
        delivery.acknowledge(*key, entry["destination"])
        run = entry["run"]
        self.assertEqual(set(run["members"]), set(ids))
        current = self.store.character(account, main["id"])
        positions.attach(account, generation, current)
        with self.store.connection() as db:
            # A persisted aborted fight is the recovery premise; no combat,
            # victory, health or reward is synthesized by this component.
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('aborted') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "UPDATE rift_instances SET status='running',fight_id=%s WHERE instance_id=%s",
                (fight_id, run["instance_id"]),
            )
            for identity in ids:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (fight_id, identity, account, generation),
                )
            self.assertEqual(len(rift_runtime.reconcile_interrupted(db)), 1)

        def snapshot():
            with self.store.connection() as db:
                return (
                    db.execute(
                        "SELECT id,hp,max_hp,hp_damage,health_dead,level FROM characters WHERE id=ANY(%s) ORDER BY id",
                        (ids,),
                    ).fetchall(),
                    db.execute(
                        "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                        (account,),
                    ).fetchall(),
                )

        before = snapshot()
        self.assertIsNone(
            recover(
                self.store, positions, account, generation, current, live_reconnect=True
            )
        )
        for state in ("entered", "running", "won", "lost"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status=%s WHERE id=%s",
                    (
                        "placement"
                        if state == "entered"
                        else "active"
                        if state == "running"
                        else "finished",
                        fight_id,
                    ),
                )
                db.execute(
                    "UPDATE rift_instances SET status=%s,fight_id=%s,"
                    "ended_at=CASE WHEN %s THEN NULL ELSE CURRENT_TIMESTAMP END "
                    "WHERE instance_id=%s",
                    (
                        state,
                        None if state == "entered" else fight_id,
                        state in ("entered", "running"),
                        run["instance_id"],
                    ),
                )
            self.assertIsNone(
                recover(self.store, positions, account, generation, current)
            )
            self.assertEqual(snapshot(), before)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s", (fight_id,)
            )
            db.execute(
                "UPDATE rift_instances SET status='closed',fight_id=%s,"
                "ended_at=CURRENT_TIMESTAMP WHERE instance_id=%s",
                (fight_id, run["instance_id"]),
            )
        with self.assertRaises((ValueError, PermissionError)):
            recover(self.store, positions, account, "stale", current)
        self.assertEqual(snapshot(), before)
        recovered = recover(self.store, positions, account, generation, current)
        exit_row = next(
            row for row in catalog["objects"] if row["type"] == "Teleporter"
        )
        target = native_transport_source(catalog["map_id"], exit_row["id"])[
            "destinations"
        ][0]
        destination = dict(
            map_id=target["map_id"],
            instance_id=0,
            x=target["x"],
            y=target["y"],
            z=target["z"],
        )
        self.assertEqual({k: recovered[k] for k in destination}, destination)
        self.assertEqual(snapshot(), before)
        self.assertEqual(delivery.pending(*key), destination)
        self.assertNotIn(key, positions.entries)
        for identity in ids:
            row = self.store.character(account, identity)
            self.assertEqual({k: row[k] for k in destination}, destination)
        self.assertIsNone(
            recover(self.store, positions, account, generation, recovered)
        )

        # The initial login ACK is after actual bootstrap/join, not relocation.
        initial = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and any(
                isinstance(s, ast.Expr)
                and isinstance(s.value, ast.Call)
                and isinstance(s.value.func, ast.Name)
                and s.value.func.id == "acknowledge_rift_login_bootstrap"
                for s in n.body
            )
        )
        calls = [
            s.value.func.id
            for s in initial.body
            if isinstance(s, ast.Expr)
            and isinstance(s.value, ast.Call)
            and isinstance(s.value.func, ast.Name)
        ]
        self.assertLess(
            calls.index("join_world"), calls.index("acknowledge_rift_login_bootstrap")
        )

        # Execute the existing real retry function, changing only lexical
        # nonlocals to this isolated namespace. Store/Positions/outbox are real;
        # socket/UI endpoints are delivery observers, not gameplay authority.
        retry = deepcopy(
            next(
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
                and n.name == "deliver_rift_transition"
            )
        )

        class Lexical(ast.NodeTransformer):
            def visit_Nonlocal(self, node):
                return ast.copy_location(ast.Global(names=node.names), node)

        retry = Lexical().visit(retry)
        sent, joined = [], []
        fail = [True]

        def send(*args):
            if fail[0]:
                raise OSError("bounded socket failure")
            sent.append(args[-2:])

        namespace.update(
            loaded=True,
            character=recovered,
            account_id=account,
            generation=generation,
            fight=None,
            combat_session=None,
            STORE=self.store,
            POSITIONS=positions,
            WORLD=SimpleNamespace(leave=Mock()),
            connection=object(),
            service="world",
            cancel_crafting=lambda: None,
            owned_native_bootstrap=lambda c: ((13256, b"bootstrap"), (13984, b"scene")),
            send=send,
            join_world=lambda *a: joined.append(a),
            mark_static_sync_pending=lambda: None,
            record=lambda **k: None,
            Movement=lambda p: dict(p),
            position={},
            movement_state=None,
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[retry], type_ignores=[])),
                "World committed Rift retry",
                "exec",
            ),
            namespace,
        )
        with self.assertRaises(OSError):
            namespace["deliver_rift_transition"]()
        self.assertEqual(delivery.pending(*key), destination)
        self.assertEqual(joined, [])
        fail[0] = False
        self.assertTrue(namespace["deliver_rift_transition"]())
        self.assertEqual(len(sent), 2)
        self.assertEqual(len(joined), 1)
        self.assertIsNone(delivery.pending(*key))
        self.assertFalse(namespace["deliver_rift_transition"]())
        self.assertEqual(snapshot(), before)
        self.assertEqual(self.store.character(account, main["id"])["instance_id"], 0)
