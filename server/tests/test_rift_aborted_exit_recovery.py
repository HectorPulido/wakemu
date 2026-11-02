"""Canonical abort repairs retained Rift custody without restoring checkpoints."""
import json
from types import SimpleNamespace

from postgres_case import PostgresCase
from wakfu_server import combat_abandon, heroes, rift_runtime, rift_transition_delivery
from wakfu_server.command_permissions import set_admin
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.position_buffer import Positions
from wakfu_server.test_console import execute
from test_combat_abandon import setup_abandon_state


class RiftAbortedExitRecoveryTests(PostgresCase):
    def test_prepare_abort_closes_bound_rift_in_same_health_transaction(self):
        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        with store.connection() as db:
            run = rift_runtime.enter(
                db,
                3,
                character["id"],
                [character["id"]],
                seed="abort-hook-fixture",
                authorize=lambda *_: True,
            )
            db.execute(
                "UPDATE rift_instances SET status='running',fight_id=%s,completed_waves=2,defeated_monsters=10,last_turn=5 WHERE instance_id=%s",
                (fight.id, run["instance_id"]),
            )
        result = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        self.assertTrue(result["applied"])
        with store.connection() as db:
            after = db.execute(
                "SELECT * FROM rift_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            self.assertEqual(after["status"], "closed")
            self.assertEqual(
                (
                    after["completed_waves"],
                    after["defeated_monsters"],
                    after["last_turn"],
                ),
                (2, 10, 5),
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_health_exits").fetchone()[
                    "n"
                ],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM rift_settlement_receipts"
                ).fetchone()["n"],
                0,
            )
        self.assertFalse(
            combat_abandon.prepare(
                store, account, generation, result["character"], runtime, b""
            )["applied"]
        )

    def test_console_recovers_aborted_binding_but_preserves_real_fights_and_company(
        self,
    ):
        account = self.store.register("stale-rift-console", "test-password")["id"]
        set_admin(
            self.store, account, True, operator="test", reason="isolated Rift recovery"
        )
        main = self.store.create_character(account, "Recovermain")
        hero = self.store.create_character(account, "Recoverhero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        ids = [main["id"], hero["id"]]
        positions = Positions(
            self.store,
            lease_active=lambda a, g, c: a == account and g == generation and c in ids,
        )
        key = account, generation, main["id"]
        self.addCleanup(rift_transition_delivery._PENDING.pop, key, None)
        with self.store.connection() as db:
            run = rift_runtime.enter(
                db,
                3,
                main["id"],
                ids,
                seed="stale-aborted-fixture",
                authorize=lambda *_: True,
            )
            cell = min(published_geometry(run["catalog"]["map_id"]).cells)
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (run["catalog"]["map_id"], run["instance_id"], *cell, ids),
            )
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "UPDATE rift_instances SET status='running',fight_id=%s,wave=3,completed_waves=2,defeated_monsters=10,last_turn=5 WHERE instance_id=%s",
                (fight, run["instance_id"]),
            )
            for cid in ids:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (fight, cid, account, generation),
                )
            # Opaque retained payload models the contradictory durable statuses;
            # this test never deserializes or resumes a native fight from it.
            db.execute(
                "INSERT INTO fight_checkpoints(fight_id,account_id,generation,revision,status,snapshot,updated_at) VALUES(%s,%s,%s,326,'active',%s::jsonb,CURRENT_TIMESTAMP)",
                (
                    fight,
                    account,
                    generation,
                    json.dumps(
                        dict(fixture="retained active checkpoint", phase="active")
                    ),
                ),
            )
            checkpoint = db.execute(
                "SELECT * FROM fight_checkpoints WHERE fight_id=%s", (fight,)
            ).fetchone()
            health = db.execute(
                "SELECT id,hp,max_hp,hp_damage,health_dead FROM characters WHERE id=ANY(%s) ORDER BY id",
                (ids,),
            ).fetchall()
            slots = db.execute(
                "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                (account,),
            ).fetchall()
        current = self.store.character(account, main["id"])
        positions.attach(account, generation, current)

        def command(fighting):
            return execute(
                self.store,
                SimpleNamespace(),
                account,
                generation,
                current,
                "!astrub",
                positions=positions,
                fighting=fighting,
            )

        with self.assertRaisesRegex(ValueError, "running rift"):
            command(lambda _: False)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s", (fight,)
            )
        with self.assertRaisesRegex(ValueError, "running rift"):
            command(lambda identity: identity == hero["id"])
        with self.store.connection() as db:
            other = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (other, hero["id"], account, generation),
            )
        with self.assertRaisesRegex(ValueError, "running rift"):
            command(lambda _: False)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (run["instance_id"],),
                ).fetchone()["status"],
                "running",
            )
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s", (other,)
            )
        moved = command(lambda _: False)
        self.assertEqual(moved["character"]["instance_id"], 0)
        self.assertNotIn(key, positions.entries)
        pending = rift_transition_delivery.pending(*key)
        self.assertEqual((pending["map_id"], pending["instance_id"]), (527, 0))
        with self.store.connection() as db:
            after = db.execute(
                "SELECT * FROM rift_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            self.assertEqual(
                (
                    after["status"],
                    after["wave"],
                    after["completed_waves"],
                    after["defeated_monsters"],
                    after["last_turn"],
                ),
                ("closed", 3, 2, 10, 5),
            )
            self.assertEqual(
                db.execute(
                    "SELECT * FROM fight_checkpoints WHERE fight_id=%s", (fight,)
                ).fetchone(),
                checkpoint,
            )
            self.assertEqual(
                db.execute(
                    "SELECT id,hp,max_hp,hp_damage,health_dead FROM characters WHERE id=ANY(%s) ORDER BY id",
                    (ids,),
                ).fetchall(),
                health,
            )
            self.assertEqual(
                db.execute(
                    "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                    (account,),
                ).fetchall(),
                slots,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM characters WHERE id=ANY(%s) AND map_id=527 AND instance_id=0",
                    (ids,),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM rift_settlement_receipts"
                ).fetchone()["n"],
                0,
            )
        rift_transition_delivery.acknowledge(*key, pending)
        self.assertIsNone(rift_transition_delivery.pending(*key))
        newcomer = self.store.create_character(account, "Afterrecovery")
        selected = self.store.select_character(account, generation, newcomer["id"])
        self.assertEqual(selected["id"], newcomer["id"])
