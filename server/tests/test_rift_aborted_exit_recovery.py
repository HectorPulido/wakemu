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
    def test_completed_company_withdrawal_exits_without_moving_other_account(self):
        import struct
        from wakfu_server import generic_transports, rift_exit

        for mode in ("native", "relocate"):
            with self.subTest(mode=mode):
                account = self.store.register("exit-withdraw-" + mode, "test-password")[
                    "id"
                ]
                peer_account = self.store.register(
                    "exit-peer-" + mode, "test-password"
                )["id"]
                main = self.store.create_character(account, "Exit Main " + mode)
                hero = self.store.create_character(account, "Exit Hero " + mode)
                peer = self.store.create_character(peer_account, "Exit Peer " + mode)
                generation = self.store.begin_session(account)
                peer_generation = self.store.begin_session(peer_account)
                self.store.select_character(account, generation, main["id"])
                self.store.select_character(peer_account, peer_generation, peer["id"])
                heroes.add(self.store, account, generation, main["id"], hero["id"])
                own_ids = [main["id"], hero["id"]]
                ids = own_ids + [peer["id"]]
                with self.store.connection() as db:
                    run = rift_runtime.enter(
                        db, 3, main["id"], ids, seed=mode, authorize=lambda *_: True
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
                        "UPDATE rift_instances SET status='running',fight_id=%s WHERE instance_id=%s",
                        (fight, run["instance_id"]),
                    )
                    for cid, owner in (
                        (main["id"], account),
                        (hero["id"], account),
                        (peer["id"], peer_account),
                    ):
                        db.execute(
                            "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                            "VALUES(%s,%s,%s,0)",
                            (fight, cid, owner),
                        )
                    db.execute(
                        "INSERT INTO combat_pve_withdrawals "
                        "(fight_id,character_id,account_id,session_generation,created_at,returned_at) "
                        "VALUES(%s,%s,%s,%s,now(),now())",
                        (fight, main["id"], account, generation),
                    )
                    before_run = rift_runtime._run(db, run["instance_id"])
                current = self.store.character(account, main["id"])
                peer_before = self.store.character(peer_account, peer["id"])
                positions = Positions(
                    self.store, lease_active=self.store.current_character_session
                )
                positions.attach(account, generation, current)
                positions.attach(peer_account, peer_generation, peer_before)
                key = account, generation, main["id"]
                peer_key = peer_account, peer_generation, peer["id"]
                self.addCleanup(rift_transition_delivery._PENDING.pop, key, None)
                source_id = next(
                    obj["id"]
                    for obj in run["catalog"]["objects"]
                    if obj["type"] == "Teleporter"
                )
                portal = generic_transports.source(current["map_id"], source_id)
                destination = portal["destinations"][0]
                body = struct.pack(
                    ">qiBi", source_id, destination["destination_id"], 0, 2
                )

                def leave():
                    if mode == "native":
                        return rift_exit.leave(
                            self.store,
                            positions,
                            *key,
                            body,
                            source_allowed=lambda *_: True,
                            fighting=lambda cid: cid == peer["id"]
                        )
                    target = dict(
                        map_id=527,
                        instance_id=0,
                        **dict(zip(("x", "y", "z"), min(published_geometry(527).cells)))
                    )
                    return rift_exit.relocate(
                        self.store,
                        positions,
                        *key,
                        current,
                        target,
                        fighting=lambda cid: cid == peer["id"]
                    )

                with self.assertRaisesRegex(ValueError, "running rift"):
                    leave()
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE combat_pve_withdrawals SET health_returned_at=now() WHERE fight_id=%s",
                        (fight,),
                    )
                # The main's receipt cannot authorize moving a still-active hero.
                with self.assertRaisesRegex(ValueError, "running rift"):
                    leave()
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO combat_pve_withdrawals "
                        "(fight_id,character_id,account_id,session_generation,created_at,returned_at,health_returned_at) "
                        "VALUES(%s,%s,%s,%s,now(),now(),now())",
                        (fight, hero["id"], account, generation),
                    )
                from test_temporary_recycling import TemporaryRecyclingTests

                loot_owner = dict(
                    account=account, generation=generation, character=hero
                )
                claim_uid = TemporaryRecyclingTests._temporary_item(self, loot_owner)
                recycle_uid = TemporaryRecyclingTests._temporary_item(
                    self, loot_owner, quantity=50
                )
                result = leave()
                self.assertEqual(
                    set(own_ids), {row["id"] for row in result["moved_members"]}
                )
                for cid in own_ids:
                    self.assertEqual(
                        0, self.store.character(account, cid)["instance_id"]
                    )
                self.assertEqual(
                    peer_before, self.store.character(peer_account, peer["id"])
                )
                self.assertNotIn(key, positions.entries)
                self.assertIn(peer_key, positions.entries)
                self.assertEqual(
                    0, rift_transition_delivery.pending(*key)["instance_id"]
                )
                self.assertIsNone(rift_transition_delivery.pending(*peer_key))
                with self.store.connection() as db:
                    self.assertEqual(
                        before_run, rift_runtime._run(db, run["instance_id"])
                    )
                    self.assertEqual(
                        "active",
                        db.execute(
                            "SELECT status FROM combat_fights WHERE id=%s", (fight,)
                        ).fetchone()["status"],
                    )

                # Consume the real committed departure, then use the same
                # selected lease for all downstream APIs. No exterior position
                # or membership is fabricated after leave().
                pending = rift_transition_delivery.pending(*key)
                outside = self.store.character(account, main["id"])
                positions.attach(account, generation, outside)
                rift_transition_delivery.acknowledge(*key, pending)
                self.assertIsNone(rift_transition_delivery.pending(*key))
                self.assertIn(key, positions.entries)
                positions.release(*key)
                self.store.select_character(account, generation, hero["id"])
                self.store.select_character(account, generation, main["id"])
                positions.attach(
                    account, generation, self.store.character(account, main["id"])
                )
                from wakfu_server import combat_drop_delivery, temporary_recycling

                bag = next(
                    row for row in hero["inventory_containers"] if row["kind"] == 0
                )
                claim_body = struct.pack(">qhbqh", claim_uid, 1, -1, bag["uid"], -1)
                claimed = combat_drop_delivery.claim(self.store, *key, claim_body)
                self.assertEqual(claimed["character"]["id"], hero["id"])
                self.assertFalse(
                    combat_drop_delivery.claim(self.store, *key, claim_body)["applied"]
                )
                recycle_body = temporary_recycling.request(hero["id"], [recycle_uid])[1]
                recycled = temporary_recycling.recycle(
                    self.store, *key, recycle_body, rng=lambda: 0.0
                )
                self.assertEqual(recycled["character"]["id"], hero["id"])
                self.assertFalse(
                    temporary_recycling.recycle(self.store, *key, recycle_body)[
                        "applied"
                    ]
                )
                self.assertTrue(self.store.current_character_session(*key))
                from wakfu_server.shop_domain import ShopService

                token = self.store.issue_token(account, "api", generation=generation)
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE account_wallets SET kamas=5000 WHERE account_id=%s",
                        (account,),
                    )
                    article = db.execute(
                        "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category) "
                        "VALUES(%s,'Withdrawal test item',2027,1,1000,'weapons') RETURNING id",
                        ("exit-followon-" + mode,),
                    ).fetchone()["id"]
                shop = ShopService(self.store)
                purchase = shop.purchase(token, article, "exit-followon-" + mode)
                self.assertEqual(
                    purchase, shop.purchase(token, article, "exit-followon-" + mode)
                )
                self.assertEqual(purchase["item"]["reference"], 2027)
                positions.release(*key)
                created = self.store.create_character(
                    account, "After Exit " + mode, selection_generation=generation
                )
                self.store.select_character(account, generation, created["id"])
                self.store.select_character(account, generation, main["id"])
                heroes.add(self.store, account, generation, main["id"], hero["id"])
                positions.attach(
                    account, generation, self.store.character(account, main["id"])
                )
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT kamas FROM account_wallets WHERE account_id=%s",
                            (account,),
                        ).fetchone()["kamas"],
                        4000,
                    )
                    self.assertEqual(
                        before_run, rift_runtime._run(db, run["instance_id"])
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM combat_fights WHERE id=%s", (fight,)
                        ).fetchone()["status"],
                        "active",
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT character_id FROM account_hero_slots WHERE account_id=%s",
                            (account,),
                        ).fetchone()["character_id"],
                        hero["id"],
                    )
                self.assertEqual(
                    peer_before, self.store.character(peer_account, peer["id"])
                )
                self.assertIn(peer_key, positions.entries)
                self.assertIsNone(rift_transition_delivery.pending(*key))
                self.assertIsNone(rift_transition_delivery.pending(*peer_key))

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
