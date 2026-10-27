"""One isolated administrative Rift lifecycle, without simulating a fight."""
import ast
from copy import deepcopy
from pathlib import Path
import struct

from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.characters.creation import create, select_created
from wakfu_server.command_permissions import set_admin
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.combat_groups import Groups
from wakfu_server.console_relocation import relocate
from wakfu_server.position_buffer import Positions
from wakfu_server import rift_transition_delivery as delivery
from wakfu_server import player_parties, generic_transports, rift_exit
from wakfu_server.test_console import execute
from wakfu_server.wire import appearance_section


class ConsoleRiftRelocationTests(PostgresCase):
    def test_admin_departure_company_pending_creation_reentry_and_single_bootstrap(
        self,
    ):
        account = self.store.register("admin-rift-exit", "test-password")["id"]
        set_admin(
            self.store, account, True, operator="test", reason="Rift exit fixture"
        )
        main = self.store.create_character(account, "Riftmain")
        hero = self.store.create_character(account, "Rifthero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        ids = [main["id"], hero["id"]]
        positions = Positions(
            self.store,
            lease_active=lambda a, g, c: a == account and g == generation and c in ids,
        )
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
        portal = catalog["entrances"][0]
        cell = min(published_geometry(catalog["map_id"]).cells)
        destination = dict(map_id=527, instance_id=0, x=0, y=32, z=0)
        key = (account, generation, main["id"])
        self.addCleanup(delivery._PENDING.pop, key, None)

        def character():
            return self.store.character(account, main["id"])

        def acknowledge():
            pending = delivery.pending(*key)
            self.assertIsNotNone(pending)
            delivery.acknowledge(*key, dict(pending, x=pending["x"] + 1))
            self.assertEqual(delivery.pending(*key), pending)
            delivery.acknowledge(*key, pending)
            self.assertIsNone(delivery.pending(*key))

        def enter():
            # Native portal/floor are unchanged; placement is an explicit entry fixture.
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                    (portal["map_id"], portal["x"], portal["y"], portal["z"], ids),
                )
            positions.attach(account, generation, character())
            admitted = delivery.enter(
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
                seed="admin-rift-lifecycle",
            )
            self.assertEqual(set(admitted["run"]["members"]), set(ids))
            acknowledge()
            positions.attach(account, generation, character())
            return admitted["run"]

        def snapshot():
            with self.store.connection() as db:
                return (
                    db.execute(
                        "SELECT * FROM characters WHERE id=ANY(%s) ORDER BY id", (ids,)
                    ).fetchall(),
                    db.execute(
                        "SELECT * FROM rift_instances ORDER BY instance_id"
                    ).fetchall(),
                    db.execute(
                        "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                        (account,),
                    ).fetchall(),
                )

        run = enter()
        source = character()
        before = snapshot()
        with self.assertRaises(ValueError):
            relocate(
                self.store,
                account,
                generation,
                main["id"],
                dict(source, x=source["x"] + 1),
                destination,
                positions=positions,
            )
        with self.assertRaises(ValueError):
            relocate(
                self.store,
                account,
                "stale",
                main["id"],
                source,
                destination,
                positions=positions,
            )
        self.assertEqual(snapshot(), before)
        self.assertIsNone(delivery.pending(*key))
        # Persisted combat and running status are separate authoritative negative controls.
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, hero["id"], account),
            )
        with self.assertRaisesRegex(ValueError, "active fight"):
            relocate(
                self.store,
                account,
                generation,
                main["id"],
                source,
                destination,
                positions=positions,
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
            )
            db.execute(
                "UPDATE rift_instances SET status='running' WHERE instance_id=%s",
                (run["instance_id"],),
            )
        with self.assertRaisesRegex(ValueError, "running"):
            relocate(
                self.store,
                account,
                generation,
                main["id"],
                source,
                destination,
                positions=positions,
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE rift_instances SET status='entered' WHERE instance_id=%s",
                (run["instance_id"],),
            )
        before = snapshot()
        result = execute(
            self.store,
            Groups(),
            account,
            generation,
            source,
            "!astrub",
            positions=positions,
        )
        self.assertEqual(result["action"], "tp")
        after = snapshot()
        self.assertEqual(after[1][0]["status"], "closed")
        self.assertEqual(after[1][0]["members"], before[1][0]["members"])
        self.assertEqual(after[2], before[2])
        for old, new in zip(before[0], after[0]):
            self.assertEqual({k: new[k] for k in destination}, destination)
            for field in ("hp", "max_hp", "hp_damage", "health_dead", "level"):
                self.assertEqual(new[field], old[field])
        self.assertNotIn(key, positions.entries)
        self.assertEqual(delivery.pending(*key), destination)
        self.assertIsNone(delivery.pending(account, generation, hero["id"]))
        acknowledge()

        # A fresh creation/selection and return to the old company must remain usable.
        self.store.clear_character(account, generation)
        name = b"Postrift"
        body = (
            struct.pack(">qhB", -1, 15, len(name))
            + name
            + b"\x01"
            + appearance_section({"sex": 0})
        )
        status, created = create(self.store, account, generation, body)
        self.assertEqual(status, 0)
        self.assertEqual(
            select_created(self.store, account, generation, created["id"])["id"],
            created["id"],
        )
        self.store.select_character(account, generation, main["id"])
        # Selecting another character intentionally clears active hero slots; reselect the owned hero.
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        second = enter()
        self.assertNotEqual(second["instance_id"], run["instance_id"])
        result = execute(
            self.store,
            Groups(),
            account,
            generation,
            character(),
            "!tp 527 0 32 0",
            positions=positions,
        )
        self.assertEqual(result["character"]["instance_id"], 0)
        self.assertEqual(delivery.pending(*key), destination)
        self.assertTrue(
            all(
                self.store.character(account, identity)["instance_id"] == 0
                for identity in ids
            )
        )
        acknowledge()

        # Execute the real World dispatch condition with its alternative body as an observer.
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "result['action'] == 'tp' and deliver_rift_transition()"
        )
        branch = deepcopy(branch)
        branch.orelse = [
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="generic_bootstrap", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                )
            )
        ]
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[])),
            "World tp branch",
            "exec",
        )
        calls = []
        for native in (True, False):
            calls.clear()
            exec(
                code,
                dict(
                    result={"action": "tp"},
                    deliver_rift_transition=lambda: calls.append("native") or native,
                    generic_bootstrap=lambda: calls.append("generic"),
                ),
            )
            self.assertEqual(calls, ["native"] if native else ["native", "generic"])


class NonOwnerEnteredRiftEscapeTests(PostgresCase):
    def test_nonowner_astrub_closes_complete_entered_company_without_changing_native_exit_rights(
        self,
    ):
        owners = []
        ids = []
        owner_by_id = {}
        for index, count in enumerate((2, 1)):
            account = self.store.register(f"nonowner-escape-{index}", "test-password")[
                "id"
            ]
            main = self.store.create_character(account, f"EscapeMain{chr(65 + index)}")[
                "id"
            ]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, main)
            owner = (account, generation, main)
            owners.append(owner)
            ids.append(main)
            owner_by_id[main] = owner
        a, b = owners
        invitation = player_parties.invite(self.store, *a, b[2])
        party = player_parties.answer(self.store, *b, invitation, True)
        for index, (owner, count) in enumerate(zip(owners, (2, 1))):
            for hero_index in range(count):
                hero = self.store.create_character(
                    owner[0], f"EscapeHero{chr(65 + index)}{chr(65 + hero_index)}"
                )["id"]
                heroes.add(self.store, *owner, hero)
                ids.append(hero)
                owner_by_id[hero] = owner
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            entrance = catalog["entrances"][0]
            db.execute(
                "UPDATE characters SET level=33,map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (entrance["map_id"], entrance["x"], entrance["y"], entrance["z"], ids),
            )
        positions = Positions(self.store, lease_active=lambda *key: key in owners)
        for account, generation, main in owners:
            positions.attach(account, generation, self.store.character(account, main))
        arrival = min(published_geometry(catalog["map_id"]).cells)
        entered = delivery.enter(
            self.store,
            positions,
            *a,
            entrance["map_id"],
            struct.pack(">qHH", entrance["object_id"], 11, 0),
            source_allowed=lambda row, source: all(
                row[key] == source[key] for key in ("map_id", "x", "y", "z")
            ),
            resolve_destination=lambda *_: dict(
                map_id=catalog["map_id"], x=arrival[0], y=arrival[1], z=arrival[2]
            ),
            seed="nonowner-administrative-escape",
        )
        run = entered["run"]
        self.assertEqual(run["owner_character_id"], a[2])
        self.assertEqual(set(run["members"]), set(ids))
        for owner in owners:
            pending = delivery.pending(*owner)
            delivery.acknowledge(*owner, pending)
            self.addCleanup(delivery._PENDING.pop, owner, None)
        native = []
        for obj in run["catalog"]["objects"]:
            if obj["type"] != "Teleporter" or obj["map_id"] != catalog["map_id"]:
                continue
            portal = generic_transports.source(obj["map_id"], obj["id"])
            for target in () if portal is None else portal["destinations"]:
                if (
                    not target["criterion"].strip()
                    and target["cyW"] == target["cyX"] == 0
                    and target["cyZ"] < 0
                    and target["native_altitude_walkable"]
                    and target["map_id"] != catalog["map_id"]
                ):
                    native.append((portal, target))
        self.assertTrue(native)
        portal, target = native[0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (portal["x"], portal["y"], portal["z"], ids),
            )
            before = db.execute(
                "SELECT id,hp,max_hp,hp_damage,health_dead,level FROM characters WHERE id=ANY(%s) ORDER BY id",
                (ids,),
            ).fetchall()
            slots = db.execute(
                "SELECT * FROM account_hero_slots ORDER BY account_id,slot"
            ).fetchall()
        for account, generation, main in owners:
            positions.attach(account, generation, self.store.character(account, main))
        with self.assertRaisesRegex(ValueError, "Only the owner"):
            rift_exit.leave(
                self.store,
                positions,
                *b,
                struct.pack(">qiBi", portal["id"], target["destination_id"], 0, 2),
                source_allowed=lambda row, source: all(
                    row[key] == source[key] for key in ("map_id", "x", "y", "z")
                ),
                fighting=lambda identity: False,
            )
        self.assertTrue(all(delivery.pending(*owner) is None for owner in owners))
        # The ordinary public emergency command is authorized for B; B is
        # neither the frozen run owner nor the party leader.
        source = self.store.character(b[0], b[2])
        outcome = execute(
            self.store, Groups(), b[0], b[1], source, "!astrub", positions=positions
        )
        self.assertEqual(outcome["action"], "tp")
        destination = dict(map_id=527, instance_id=0, x=0, y=32, z=0)
        with self.store.connection() as db:
            saved_run = db.execute(
                "SELECT owner_character_id,members,status FROM rift_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            after = db.execute(
                "SELECT id,hp,max_hp,hp_damage,health_dead,level FROM characters WHERE id=ANY(%s) ORDER BY id",
                (ids,),
            ).fetchall()
            rows = db.execute(
                "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s)",
                (ids,),
            ).fetchall()
            self.assertEqual(
                db.execute(
                    "SELECT leader_id FROM player_parties WHERE id=%s", (party,)
                ).fetchone()["leader_id"],
                a[2],
            )
            self.assertEqual(
                db.execute(
                    "SELECT * FROM account_hero_slots ORDER BY account_id,slot"
                ).fetchall(),
                slots,
            )
        self.assertEqual(saved_run["status"], "closed")
        self.assertEqual(saved_run["owner_character_id"], a[2])
        self.assertEqual(set(saved_run["members"]), set(ids))
        self.assertEqual(before, after)
        self.assertTrue(
            all({key: row[key] for key in destination} == destination for row in rows)
        )
        self.assertFalse(positions.entries)
        for owner in owners:
            self.assertEqual(delivery.pending(*owner), destination)
            delivery.acknowledge(*owner, destination)
        for identity in set(ids) - {owner[2] for owner in owners}:
            account, generation, main = owner_by_id[identity]
            self.assertIsNone(delivery.pending(account, generation, identity))
        created = self.store.create_character(
            b[0], "AfterNonOwnerExit", selection_generation=b[1]
        )
        self.assertEqual(
            self.store.select_character(b[0], b[1], created["id"])["id"], created["id"]
        )
