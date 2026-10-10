"""Rift progression/reward receipts are durable and share caller transactions."""
import uuid
import struct
from contextlib import nullcontext
from unittest.mock import Mock
from postgres_case import PostgresCase
from wakfu_server import rift_runtime as rifts, rift_transition_delivery
from wakfu_server.characters import heroes
from wakfu_server.rift_policy import select_wave


class RiftPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "rf" + uuid.uuid4().hex[:10], "test-password"
        )["id"]
        self.character = self.store.create_character(
            self.account,
            "Rift" + "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:8]),
        )["id"]
        with self.store.connection() as db:
            self.run = rifts.enter(
                db,
                3,
                self.character,
                [self.character],
                seed="test",
                authorize=lambda c, m: True,
            )
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (self.fight_id, self.character, self.account),
            )
            rifts.start(db, self.run["instance_id"], self.character, self.fight_id)
            refs = select_wave(
                self.run["catalog"], self.run["policy"], self.run["seed"], 1
            )
            rifts.bind_wave(
                db, self.run["instance_id"], 1, list(zip([-4, -3, -2, -1], refs))
            )

    def wave(self, db):
        return rifts.record_wave(
            db, self.run["instance_id"], 1, [-4, -3, -2, -1], turn=2
        )

    def test_wave_receipt_replay_survives_reopen(self):
        with self.store.connection() as db:
            first = self.wave(db)
        with self.reopen().connection() as db:
            self.assertEqual(self.wave(db), first)
            run = rifts._run(db, self.run["instance_id"])
            self.assertEqual(
                (run["wave"], run["completed_waves"], run["defeated_monsters"]),
                (2, 1, 4),
            )
            with self.assertRaisesRegex(ValueError, "changed its original roster"):
                rifts.record_wave(
                    db, self.run["instance_id"], 1, [-5, -3, -2, -1], turn=2
                )

    def test_failed_spawn_rolls_back_progress(self):
        with self.assertRaisesRegex(RuntimeError, "spawn failed"):
            with self.store.connection() as db:
                self.wave(db)
                raise RuntimeError("spawn failed")
        with self.store.connection() as db:
            self.assertEqual(
                rifts._run(db, self.run["instance_id"])["completed_waves"], 0
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_wave_receipts").fetchone()[
                    "n"
                ],
                0,
            )

    def test_winning_receipt_calls_reward_authority_once(self):
        calls = []
        with self.store.connection() as db:
            self.wave(db)
            first = rifts.settle(
                db,
                self.run["instance_id"],
                self.fight_id,
                outcome="won",
                turn=40,
                apply_rewards=lambda db, run, result: calls.append(result),
            )
        with self.reopen().connection() as db:
            self.assertEqual(
                first,
                rifts.settle(
                    db,
                    self.run["instance_id"],
                    self.fight_id,
                    outcome="won",
                    turn=40,
                    apply_rewards=lambda *a: self.fail("Repeated reward"),
                ),
            )
        self.assertEqual(len(calls), 1)

    def test_reward_failure_rolls_back_terminal_receipt(self):
        def fail(db, run, result):
            db.execute(
                "INSERT INTO settings(name,value) VALUES('rift_reward_probe','1'::jsonb)"
            )
            raise RuntimeError("reward failed")

        with self.assertRaisesRegex(RuntimeError, "reward failed"):
            with self.store.connection() as db:
                rifts.settle(
                    db,
                    self.run["instance_id"],
                    self.fight_id,
                    outcome="won",
                    turn=40,
                    apply_rewards=fail,
                )
        with self.store.connection() as db:
            self.assertEqual(
                rifts._run(db, self.run["instance_id"])["status"], "running"
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM rift_settlement_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT value FROM settings WHERE name='rift_reward_probe'"
                ).fetchone()
            )

    def test_loss_never_calls_rewards_and_early_survival_rejected(self):
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "budget"):
                rifts.settle(
                    db,
                    self.run["instance_id"],
                    self.fight_id,
                    outcome="won",
                    turn=39,
                    apply_rewards=lambda *a: None,
                )
            rifts.settle(
                db,
                self.run["instance_id"],
                self.fight_id,
                outcome="lost",
                turn=4,
                apply_rewards=lambda *a: self.fail("Loss reward"),
            )
            entered = rifts.enter(
                db,
                4,
                self.character,
                [self.character],
                seed="next",
                authorize=lambda *a: True,
            )
            closed = rifts.close_entered(db, entered["instance_id"], self.character)
            self.assertEqual(closed["status"], "closed")
            self.assertEqual(
                closed, rifts.close_entered(db, entered["instance_id"], self.character)
            )

    def test_overlapping_membership_rejected_and_policy_frozen(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{turn_budget}','80') WHERE name='rift_policy'"
            )
            self.assertEqual(
                rifts._run(db, self.run["instance_id"])["policy"]["turn_budget"], 40
            )
            with self.assertRaisesRegex(ValueError, "already belongs"):
                rifts.enter(
                    db,
                    4,
                    self.character,
                    [self.character],
                    seed="second",
                    authorize=lambda *a: True,
                )

    def test_arbitrary_roster_and_ultimate_keys_fail_closed(self):
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "authoritative rift roster"):
                rifts.record_wave(
                    db, self.run["instance_id"], 1, [-8, -7, -6, -5], turn=2
                )
            with self.assertRaisesRegex(ValueError, "key authority"):
                rifts.enter(
                    db,
                    5,
                    self.character,
                    [self.character],
                    seed="ultimate",
                    authorize=lambda *a: True,
                )

    def test_checkpoint_staging_persists_and_replays_all_wave_bindings(self):
        from types import SimpleNamespace
        from wakfu_server.rift_policy import select_wave

        refs = select_wave(self.run["catalog"], self.run["policy"], self.run["seed"], 2)
        fight = SimpleNamespace(
            id=self.fight_id,
            rift_wave_state=dict(
                instance_id=self.run["instance_id"],
                staged_receipts=[
                    dict(
                        completed_wave=1,
                        actor_ids=[-4, -3, -2, -1],
                        turn=2,
                        next_actor_ids=[-8, -7, -6, -5],
                        next_species_refs=refs,
                    )
                ],
            ),
        )
        with self.store.connection() as db:
            first = rifts.persist_progress(db, fight)
            self.assertEqual(first, rifts.persist_progress(db, fight))
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_wave_rosters").fetchone()[
                    "n"
                ],
                2,
            )

    def test_server_instance_namespace_never_replaces_native_asset_map(self):
        from wakfu_server.native_transports import bootstrap

        character = dict(
            id=self.character,
            account_id=self.account,
            x=0,
            y=0,
            z=0,
            map_id=1314,
            instance_id=self.run["instance_id"],
        )
        self.assertGreater(character["instance_id"], 2**53)
        self.assertEqual(
            bootstrap(character), bootstrap(dict(character, instance_id=0))
        )

    def test_native_exit_cancels_unstarted_run_and_restores_world(self):
        from contextlib import nullcontext
        from unittest.mock import Mock
        import struct
        from wakfu_server import generic_transports, rift_exit

        with self.store.connection() as db:
            rifts.settle(
                db,
                self.run["instance_id"],
                self.fight_id,
                outcome="lost",
                turn=4,
                apply_rewards=None,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s",
                (self.fight_id,),
            )
            entered = rifts.enter(
                db,
                3,
                self.character,
                [self.character],
                seed="exit",
                authorize=lambda *a: True,
            )
        generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, generation, self.character)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1314,instance_id=%s WHERE id=%s",
                (entered["instance_id"], self.character),
            )
        source_id = next(
            o["id"] for o in entered["catalog"]["objects"] if o["type"] == "Teleporter"
        )
        source = generic_transports.source(1314, source_id)
        dest = source["destinations"][0]
        positions = Mock()
        positions.account_barrier = lambda *a: nullcontext()
        result = rift_exit.leave(
            self.store,
            positions,
            self.account,
            generation,
            self.character,
            struct.pack(">qiBi", source_id, dest["destination_id"], 0, 2),
            source_allowed=lambda *a: True,
            fighting=lambda *a: False,
        )
        self.assertEqual(result["destination"]["instance_id"], 0)
        with self.store.connection() as db:
            self.assertEqual(rifts._run(db, entered["instance_id"])["status"], "closed")
            row = db.execute(
                "SELECT map_id,instance_id FROM characters WHERE id=%s",
                (self.character,),
            ).fetchone()
            self.assertEqual(row, dict(map_id=dest["map_id"], instance_id=0))
        positions.flush.assert_called_once_with(account_id=self.account)
        positions.release.assert_called_once_with(
            self.account, generation, self.character
        )

    def test_startup_reconciliation_closes_interrupted_without_rewards(self):
        with self.store.connection() as db:
            self.assertEqual(rifts.reconcile_interrupted(db), ())
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s",
                (self.fight_id,),
            )
            result = rifts.reconcile_interrupted(db)
            self.assertEqual(
                [r["instance_id"] for r in result], [self.run["instance_id"]]
            )
            self.assertEqual(rifts.reconcile_interrupted(db), ())
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM rift_settlement_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertIsNone(rifts.abort_bound_fight(db, self.fight_id))

    def test_terminal_cleared_wave_and_central_abort_are_durable(self):
        from types import SimpleNamespace
        from wakfu_server.fight_store import abort

        fight = SimpleNamespace(
            id=self.fight_id,
            phase="finished",
            rift_wave_state={
                "instance_id": self.run["instance_id"],
                "pending_wave": {
                    "completed_wave": 1,
                    "actor_ids": [-4, -3, -2, -1],
                    "turn": 40,
                },
            },
        )
        with self.store.connection() as db:
            self.assertEqual(len(rifts.persist_progress(db, fight)), 1)
            self.assertEqual(len(rifts.persist_progress(db, fight)), 1)
            self.assertEqual(
                rifts._run(db, self.run["instance_id"])["defeated_monsters"], 4
            )
            self.assertTrue(
                abort(self.store, self.account, self.character, self.fight_id, db=db)
            )
            self.assertEqual(
                rifts._run(db, self.run["instance_id"])["status"], "closed"
            )


class RiftOwnedHeroLifecycleTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "rfhero" + uuid.uuid4().hex[:8], "hero-rift-password"
        )["id"]
        self.main = self.store.create_character(self.account, "Rift Hero Main")
        self.hero = self.store.create_character(self.account, "Rift Owned Hero")
        self.generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, self.generation, self.main["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,level=30 "
                "WHERE id=ANY(%s)",
                ([self.main["id"], self.hero["id"]],),
            )
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )

    def test_enter_freezes_owned_hero_and_cancel_delivers_only_main(self):
        from wakfu_server import rift_entry_adapter, rift_exit

        positions = Mock()
        positions.account_barrier = lambda *_: nullcontext()
        entry = rift_transition_delivery.enter(
            self.store,
            positions,
            self.account,
            self.generation,
            self.main["id"],
            527,
            struct.pack(">qHH", 33010, 11, 0),
            source_allowed=lambda *_: True,
            resolve_destination=lambda _db, selected, _rows: {
                "map_id": selected["map_id"],
                "x": 0,
                "y": 1,
                "z": 0,
            },
            seed="owned-hero-rift",
        )
        run = entry["run"]
        expected = {self.main["id"], self.hero["id"]}
        self.assertEqual(expected, set(run["members"]))
        self.assertEqual(expected, {member["id"] for member in entry["members"]})
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT id,map_id,instance_id FROM characters WHERE id=ANY(%s)",
                (list(expected),),
            ).fetchall()
            auth = db.execute(
                "SELECT c.id,c.account_id,c.map_id,c.instance_id,s.character_id "
                "AS selected_character_id,s.expires_at FROM characters c "
                "LEFT JOIN sessions s ON s.account_id=c.account_id WHERE c.id=ANY(%s)",
                (list(expected),),
            ).fetchall()
            for row in auth:
                self.assertTrue(heroes.session_authorized(db, row))
            authorized = rift_entry_adapter.authorize_start(
                db,
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                struct.pack(">qHH", 33012, 0, 0),
                source_allowed=lambda *_: True,
            )
            self.assertEqual(expected, set(authorized["members"]))
        self.assertEqual(expected, {row["id"] for row in stored})
        self.assertTrue(
            all(
                row["map_id"] == 1314 and row["instance_id"] == run["instance_id"]
                for row in stored
            )
        )

        exit_object = next(
            obj for obj in run["catalog"]["objects"] if obj["type"] == "Teleporter"
        )
        source = __import__(
            "wakfu_server.generic_transports", fromlist=["source"]
        ).source(run["catalog"]["map_id"], exit_object["id"])
        destination = source["destinations"][0]
        body = struct.pack(
            ">qiBi", exit_object["id"], destination["destination_id"], 0, 2
        )
        exited = rift_exit.leave(
            self.store,
            positions,
            self.account,
            self.generation,
            self.main["id"],
            body,
            source_allowed=lambda *_: True,
            fighting=lambda *_: False,
        )
        self.assertEqual(expected, {row["id"] for row in exited["moved_members"]})
        self.assertEqual({self.main["id"]}, {row["id"] for row in exited["members"]})
        self.assertEqual(destination["map_id"], exited["destination"]["map_id"])
        self.assertEqual(
            exited["destination"],
            rift_transition_delivery.pending(
                self.account, self.generation, self.main["id"]
            ),
        )
        self.assertIsNone(
            rift_transition_delivery.pending(
                self.account, self.generation, self.hero["id"]
            )
        )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT id,map_id,instance_id FROM characters WHERE id=ANY(%s)",
                (list(expected),),
            ).fetchall()
            self.assertEqual(
                {self.main["id"], self.hero["id"]}, {r["id"] for r in rows}
            )
            self.assertTrue(all(r["instance_id"] == 0 for r in rows))
        rift_transition_delivery.acknowledge(
            self.account, self.generation, self.main["id"], exited["destination"]
        )
