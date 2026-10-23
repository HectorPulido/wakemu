import struct
import json
import ast
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.combat_shared import SharedFight


class CheckpointTests(PostgresCase):
    def test_reconcile_missing_and_identical_committed_snapshot(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        state = snapshot(self.fight)
        receipt = self.checkpoints.reconcile_write(
            self.account, self.generation, self.fight, state, expected_revision=None
        )
        self.assertFalse(receipt["committed"])
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        receipt = self.checkpoints.reconcile_write(
            self.account, self.generation, self.fight, state, expected_revision=None
        )
        self.assertEqual(
            receipt, dict(committed=True, revision=revision, terminal=False)
        )
        receipt = self.checkpoints.reconcile_write(
            self.account, self.generation, self.fight, state, expected_revision=revision
        )
        self.assertFalse(receipt["committed"])

    def test_reconcile_rejects_different_snapshot_and_stale_generation(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        state = snapshot(self.fight)
        self.checkpoints.save(self.account, self.generation, self.fight)
        changed = dict(state, phase="different")
        with self.assertRaisesRegex(ValueError, "cannot be reconciled"):
            self.checkpoints.reconcile_write(
                self.account,
                self.generation,
                self.fight,
                changed,
                expected_revision=None,
            )
        with self.assertRaisesRegex(ValueError, "session is stale"):
            self.checkpoints.reconcile_write(
                self.account,
                "stale-generation",
                self.fight,
                state,
                expected_revision=None,
            )

    def test_reconcile_aborted_terminal_receipt_after_lost_response(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        state = snapshot(self.fight)
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        terminal_revision = self.checkpoints.end(
            self.account,
            self.generation,
            self.fight.id,
            expected_revision=revision,
            status="aborted",
        )
        receipt = self.checkpoints.reconcile_write(
            self.account,
            self.generation,
            self.fight,
            state,
            expected_revision=revision,
            status="aborted",
        )
        self.assertEqual(
            receipt, dict(committed=True, revision=terminal_revision, terminal=True)
        )

    def test_takeover_reconciliation_uses_new_login_and_is_idempotent(self):
        from wakfu_server.fight_checkpoint_store import checkpoint_digest, snapshot
        from wakfu_server.fight_store import takeover_participant

        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=77",
                (self.generation,),
            )
        state = snapshot(self.fight)
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        recovery = dict(
            account_id=self.account,
            generation=self.generation,
            revision=None,
            status=None,
            digest=checkpoint_digest(state),
        )
        new = self.store.begin_session(self.account)
        self.store.select_character(self.account, new, self.character)
        with self.assertRaisesRegex(ValueError, "session is stale"):
            self.checkpoints.reconcile_write(
                self.account, self.generation, self.fight, state, expected_revision=None
            )
        receipt = self.checkpoints.recover_write_for_takeover(
            self.account, self.generation, new, self.fight, recovery
        )
        self.assertEqual(
            receipt, dict(committed=True, revision=revision, terminal=False)
        )
        # Lost membership commit response: repeat against the now-new lease.
        self.assertEqual(
            self.checkpoints.recover_write_for_takeover(
                self.account, self.generation, new, self.fight, recovery
            ),
            receipt,
        )
        self.assertFalse(
            takeover_participant(
                self.store,
                self.account,
                new,
                self.character,
                self.fight.id,
                previous_generation=self.generation,
            )
        )
        # A further login can reconcile an earlier membership transfer whose
        # response was lost, using only the server-recorded generation lineage.
        third = self.store.begin_session(self.account)
        self.store.select_character(self.account, third, self.character)
        self.assertEqual(
            self.checkpoints.recover_write_for_takeover(
                self.account,
                self.generation,
                third,
                self.fight,
                recovery,
                recovery_generations=(new,),
            ),
            receipt,
        )
        self.assertEqual(
            self.checkpoints.save(
                self.account, third, self.fight, expected_revision=revision
            ),
            revision + 1,
        )

    def test_takeover_reconciliation_rejects_mismatch_without_transferring_lease(self):
        from wakfu_server.fight_checkpoint_store import checkpoint_digest, snapshot

        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=77",
                (self.generation,),
            )
        state = snapshot(self.fight)
        self.checkpoints.save(self.account, self.generation, self.fight)
        new = self.store.begin_session(self.account)
        self.store.select_character(self.account, new, self.character)
        recovery = dict(
            account_id=self.account,
            generation=self.generation,
            revision=None,
            status=None,
            digest=checkpoint_digest(dict(state, phase="different")),
        )
        with self.assertRaisesRegex(ValueError, "cannot be reconciled"):
            self.checkpoints.recover_write_for_takeover(
                self.account, self.generation, new, self.fight, recovery
            )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT session_generation FROM combat_fight_participants "
                "WHERE fight_id=77 AND character_id=%s",
                (self.character,),
            ).fetchone()
        self.assertEqual(row["session_generation"], self.generation)

    def test_takeover_reconciliation_preserves_peer_writer_receipt_and_lease(self):
        from wakfu_server.fight_checkpoint_store import checkpoint_digest, snapshot

        peer, peer_character, peer_generation, _ = self._add_shared_owner()
        state = snapshot(self.fight)
        revision = self.checkpoints.save(peer, peer_generation, self.fight)
        recovery = dict(
            account_id=peer,
            generation=peer_generation,
            revision=None,
            status=None,
            digest=checkpoint_digest(state),
        )
        new = self.store.begin_session(self.account)
        self.store.select_character(self.account, new, self.character)
        receipt = self.checkpoints.recover_write_for_takeover(
            self.account, self.generation, new, self.fight, recovery
        )
        self.assertEqual(receipt["revision"], revision)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT account_id,session_generation FROM combat_fight_participants "
                "WHERE fight_id=77"
            ).fetchall()
        self.assertEqual(
            {r["account_id"]: r["session_generation"] for r in rows},
            {self.account: new, peer: peer_generation},
        )
        self.store.begin_session(peer)
        # Receipt writer identity does not authenticate the reader. A still
        # admitted live peer can reconcile that exact old committed snapshot.
        self.assertEqual(
            self.checkpoints.reconcile_write(
                self.account,
                new,
                self.fight,
                state,
                expected_revision=None,
                receipt_writer=(peer, peer_generation),
            ),
            receipt,
        )

    def test_rift_progress_and_checkpoint_share_one_commit(self):
        from unittest.mock import patch

        self.fight.rift_wave_state = dict(instance_id=1, wave=1, turn_budget=40)

        def persist(db, fight):
            self.assertIs(fight, self.fight)
            db.execute(
                "INSERT INTO settings(name,value) VALUES('rift_atomic_probe','1')"
            )

        with patch("wakfu_server.rift_runtime.persist_progress", side_effect=persist):
            self.checkpoints.save(self.account, self.generation, self.fight)
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT value FROM settings WHERE name='rift_atomic_probe'"
                ).fetchone()
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT fight_id FROM fight_checkpoints WHERE fight_id=77"
                ).fetchone()
            )

    def test_failed_rift_progress_rolls_back_checkpoint_and_domain_write(self):
        from unittest.mock import patch

        self.fight.rift_wave_state = dict(instance_id=1, wave=1, turn_budget=40)

        def fail(db, fight):
            db.execute(
                "INSERT INTO settings(name,value) VALUES('rift_atomic_probe','1')"
            )
            raise ValueError("rift receipt rejected")

        with patch("wakfu_server.rift_runtime.persist_progress", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "rift receipt rejected"):
                self.checkpoints.save(self.account, self.generation, self.fight)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT value FROM settings WHERE name='rift_atomic_probe'"
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT fight_id FROM fight_checkpoints WHERE fight_id=77"
                ).fetchone()
            )

    def _add_shared_owner(self):
        other_account = self.store.register(
            f"checkpoint-{self.character}", "second-checkpoint-owner"
        )["id"]
        other_character = self.store.create_character(
            other_account, "Second Checkpoint Hero"
        )["id"]
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other_character)
        other_actor = Actor(
            other_character,
            0,
            (2, 0, 0),
            60,
            6,
            3,
            90,
            1,
            other_account,
            True,
        )
        self.fight.actors[other_character] = other_actor
        self.fight.walkable.add(other_actor.position)
        self.fight.placement[0].add(other_actor.position)
        self.fight._check_positions()
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s AND character_id=%s",
                (self.generation, 77, self.character),
            )
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (77, other_character, other_account, other_generation),
            )
        return other_account, other_character, other_generation, other_actor

    def test_shared_checkpoint_revision_is_shared_across_owner_sockets(self):
        (
            other_account,
            other_character,
            other_generation,
            other_actor,
        ) = self._add_shared_owner()
        shared = SharedFight(self.fight, 1134, 0, None)

        first_revision, terminal = self.checkpoints.save_shared(
            shared, self.account, self.generation
        )
        self.assertEqual((first_revision, terminal), (1, False))

        # B checkpoints after joining and may then advance the same fight; it
        # must see the fight-wide CAS revision rather than a socket-local None.
        other_actor.hp = 47
        second_revision, terminal = self.checkpoints.save_shared(
            shared, other_account, other_generation
        )
        self.assertEqual((second_revision, terminal), (2, False))
        self.assertEqual(
            Checkpoints(self.store).read(self.account, 77)["snapshot"]["actors"][
                str(other_character)
            ]["hp"],
            47,
        )

        third_revision, terminal = self.checkpoints.save_shared(
            shared, self.account, self.generation
        )
        self.assertEqual((third_revision, terminal), (3, False))
        self.assertEqual(shared.checkpoint_revision, 3)

    def test_checkpoint_trace_reports_stages_without_affecting_commit(self):
        shared = SharedFight(self.fight, 1134, 0, None)
        events = []
        revision, terminal = self.checkpoints.save_shared(
            shared,
            self.account,
            self.generation,
            trace=lambda stage, **details: events.append((stage, details)),
        )
        self.assertEqual((revision, terminal), (1, False))
        stages = [stage for stage, _ in events]
        for stage in (
            "lock_wait",
            "lock_acquired",
            "snapshot_started",
            "snapshot_finished",
            "pool_wait",
            "pool_acquired",
            "fight_query_started",
            "fight_query_finished",
            "session_query_started",
            "session_query_finished",
            "committed",
        ):
            self.assertIn(stage, stages)
        for stage, details in events:
            self.assertEqual(details["fight_id"], self.fight.id)
            self.assertNotIn("account_id", details)
            self.assertNotIn("generation", details)
            self.assertNotIn("body", details)
            if "elapsed_ms" in details:
                self.assertGreaterEqual(details["elapsed_ms"], 0)

    def test_shared_checkpoint_trace_measures_lock_wait_without_sleep(self):
        shared = SharedFight(self.fight, 1134, 0, None)
        waiting = threading.Event()
        events = []

        def trace(stage, **details):
            events.append((stage, details))
            if stage == "lock_wait":
                waiting.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with shared.lock:
                future = pool.submit(
                    self.checkpoints.save_shared,
                    shared,
                    self.account,
                    self.generation,
                    trace=trace,
                )
                self.assertTrue(waiting.wait(timeout=2))
            self.assertEqual(future.result(timeout=10), (1, False))
        stages = [stage for stage, _ in events]
        self.assertLess(stages.index("lock_wait"), stages.index("lock_acquired"))

    def test_trace_callback_failure_does_not_change_checkpoint(self):
        shared = SharedFight(self.fight, 1134, 0, None)

        def broken_trace(*_args, **_kwargs):
            raise RuntimeError("diagnostic sink unavailable")

        self.assertEqual(
            self.checkpoints.save_shared(
                shared, self.account, self.generation, trace=broken_trace
            ),
            (1, False),
        )

    def test_concurrent_owner_checkpoints_advance_one_monotonic_revision(self):
        other_account, _, other_generation, _ = self._add_shared_owner()
        shared = SharedFight(self.fight, 1134, 0, None)
        self.checkpoints.save_shared(shared, self.account, self.generation)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(
                pool.map(
                    lambda owner: self.checkpoints.save_shared(
                        shared, owner[0], owner[1]
                    )[0],
                    (
                        (self.account, self.generation),
                        (other_account, other_generation),
                    ),
                )
            )
        self.assertEqual(sorted(results), [2, 3])
        self.assertEqual(shared.checkpoint_revision, 3)
        self.assertEqual(Checkpoints(self.store).read(self.account, 77)["revision"], 3)

    def test_stale_owner_generation_does_not_advance_shared_checkpoint(self):
        other_account, other_character, other_generation, _ = self._add_shared_owner()
        shared = SharedFight(self.fight, 1134, 0, None)
        self.checkpoints.save_shared(shared, self.account, self.generation)
        replacement = self.store.begin_session(other_account)
        self.store.select_character(other_account, replacement, other_character)
        with self.assertRaisesRegex(ValueError, "stale"):
            self.checkpoints.save_shared(shared, other_account, other_generation)
        self.assertEqual(shared.checkpoint_revision, 1)
        self.assertEqual(Checkpoints(self.store).read(self.account, 77)["revision"], 1)

    def test_terminal_shared_checkpoint_is_idempotent(self):
        shared = SharedFight(self.fight, 1134, 0, None)
        revision, terminal = self.checkpoints.save_shared(
            shared, self.account, self.generation, status="ended"
        )
        self.assertEqual((revision, terminal), (2, True))
        with self.store.connection() as db:
            before = db.execute(
                "SELECT revision,status,updated_at FROM fight_checkpoints WHERE fight_id=77"
            ).fetchone()
        self.assertEqual(
            self.checkpoints.save_shared(shared, self.account, self.generation),
            (revision, True),
        )
        with self.store.connection() as db:
            after = db.execute(
                "SELECT revision,status,updated_at FROM fight_checkpoints WHERE fight_id=77"
            ).fetchone()
        self.assertEqual(before, after)

    def test_end_failure_keeps_checkpoint_revision_and_allows_retry(self):
        shared = SharedFight(self.fight, 1134, 0, None)
        original_end = self.checkpoints.end
        calls = 0

        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("injected end failure")
            return original_end(*args, **kwargs)

        self.checkpoints.end = fail_once
        with self.assertRaisesRegex(ValueError, "injected end failure"):
            self.checkpoints.save_shared(
                shared, self.account, self.generation, status="ended"
            )
        self.assertEqual(shared.checkpoint_revision, 1)
        self.assertFalse(shared.checkpoint_terminal)
        revision, terminal = self.checkpoints.save_shared(
            shared, self.account, self.generation, status="ended"
        )
        self.assertEqual((revision, terminal), (3, True))
        row = Checkpoints(self.store).read(self.account, 77)
        self.assertEqual((row["revision"], row["status"]), (3, "ended"))

    def test_async_owner_checkpoints_preserve_canonical_shared_fight(self):
        from wakfu_server.checkpoint_worker import CheckpointWorker

        other_account, _, other_generation, other_actor = self._add_shared_owner()
        shared = SharedFight(self.fight, 1134, 0, None)
        worker = CheckpointWorker(self.checkpoints, workers=2)
        self.addCleanup(worker.close)
        worker.submit(shared, self.account, self.generation)
        self.assertTrue(worker.flush_fight(self.fight.id, timeout=10))
        other_actor.hp = 47
        worker.submit(shared, other_account, other_generation)
        self.assertTrue(worker.flush_fight(self.fight.id, timeout=10))
        saved = self.checkpoints.read(self.account, self.fight.id)
        self.assertEqual(saved["snapshot"]["actors"][str(other_actor.id)]["hp"], 47)
        self.assertEqual(saved["revision"], shared.checkpoint_revision)
        self.assertEqual(saved["revision"], 2)

    def test_cast_limits_preserved_in_durable_checkpoint(self):
        from wakfu_server.combat_spell_usage import validate_usage, consume_usage

        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(self.fight, tuple(self.fight.actors))
        caster = self.fight.actors[self.character]
        for actor in self.fight.actors.values():
            actor.physical_radius = 0
        for _ in range(2):
            rule = validate_usage(self.fight, caster, 4776, 20, (1, 0, 0))
            consume_usage(
                self.fight, dict(actor_id=caster.id, spell_id=4776, native_usage=rule)
            )
        self.checkpoints.save(self.account, self.generation, self.fight)
        saved = Checkpoints(self.store).read(self.account, 77)["snapshot"]
        usage = saved["native_spell_usage"][str(caster.id)]
        self.assertEqual(usage["casts"]["4776"], 2)
        self.assertEqual(usage["targets"]["4776"]["-200"], 2)
        self.assertEqual(saved["native_table_turn"], self.fight.native_table_turn)
        with self.assertRaisesRegex(ValueError, "per target"):
            validate_usage(self.fight, caster, 4776, 20, (1, 0, 0))

    def test_placement_orientation_survives_combat_start_and_checkpoint_roundtrip(self):
        from wakfu_server.combat_orientation import apply
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        runtime = RuntimeMessages(self.fight)
        self.fight.phase = "placement"
        self.fight.ready_owners.clear()
        actor = self.fight.actors[self.character]
        apply(runtime, self.account, struct.pack(">qB", self.character, 7))
        self.assertEqual(actor.direction, 7)

        self.fight.ready(self.account)
        self.assertEqual(self.fight.phase, "active")
        self.assertEqual(actor.direction, 7)
        payloads = {identity: (b"", b"") for identity in self.fight.actors}
        runtime.combat_started(payloads)
        self.assertEqual(actor.direction, 7)

        self.checkpoints.save(
            self.account, self.generation, self.fight, runtime=runtime
        )
        snapshot = Checkpoints(self.store).read(self.account, 77)["snapshot"]
        self.assertEqual(snapshot["actors"][str(self.character)]["direction"], 7)
        self.assertEqual(snapshot["runtime"]["action_id"], runtime.action_id)

    @classmethod
    def setUpClass(cls):
        # Catalogue I/O is unrelated to the session lease under test. Load it
        # before opening sessions so slow machines do not expire a fresh lease.
        from wakfu_server.spell_audit import states_catalog

        cls.state_catalog = states_catalog()

    def test_cost_modifier_snapshot_preserves_unknown_empty_and_live_values(self):
        actor = self.fight.actors[self.character]
        rev = self.checkpoints.save(self.account, self.generation, self.fight)
        snap = self.checkpoints.read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertIsNone(snap["spell_ap_cost_modifiers"])
        actor.spell_ap_cost_modifiers = {}
        rev = self.checkpoints.save(
            self.account, self.generation, self.fight, expected_revision=rev
        )
        snap = self.checkpoints.read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertEqual(snap["spell_ap_cost_modifiers"], {})
        actor.spell_ap_cost_modifiers = {8: -1, 11: 2}
        self.checkpoints.save(
            self.account, self.generation, self.fight, expected_revision=rev
        )
        snap = self.checkpoints.read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertEqual(snap["spell_ap_cost_modifiers"], {"8": -1, "11": 2})

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.account = self.store.register("local", "testing-local")["id"]
        self.character = self.store.create_character(self.account, "Own Hero")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(%s,'active')",
                (77,),
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (77, self.character, self.account),
            )
        self.checkpoints = Checkpoints(self.store)
        pc = Actor(self.character, 0, (0, 0, 0), 60, 6, 3, 10, 1, self.account, True)
        npc = Actor(-200, 1, (1, 0, 0), 12, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(self.account)

    def test_native_hud_breed_and_resource_survive_checkpoint_read(self):
        actor = self.fight.actors[self.character]
        actor.native_hud_breed = 11
        actor.effect_stats = {50: 35}
        self.checkpoints.save(self.account, self.generation, self.fight)
        saved = Checkpoints(self.store).read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertEqual(saved["native_hud_breed"], 11)
        self.assertEqual(saved["effect_stats"]["50"], 35)

    def test_owned_hp_resources_states_and_events_survive_reopen(self):
        self.fight.apply_state(
            self.character,
            -200,
            3442,
            20,
            catalog=self.state_catalog,
            uid=901,
        )
        from wakfu_server.combat_state_ledger import StateTimeline

        self.fight.apply_state(
            self.character,
            -200,
            8913,
            30,
            catalog=self.state_catalog,
            uid=902,
            timeline=StateTimeline(1, self.character, 0, 0, "active"),
        )
        self.fight.actors[-200].combat_states = {
            8913: dict(level=30, expires_at_caster_start=2)
        }
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        self.fight.apply_damage(self.character, -200, 5)
        revision = self.checkpoints.save(
            self.account, self.generation, self.fight, expected_revision=revision
        )
        row = Checkpoints(self.store).read(self.account, 77)
        npc = row["snapshot"]["actors"]["-200"]
        self.assertEqual((npc["hp"], npc["max_hp"], npc["max_mp"]), (7, 12, 3))
        self.assertEqual(npc["combat_states"]["8913"]["level"], 30)
        running = npc["state_ledger"]["entries"][0]
        self.assertEqual(
            (
                running["uid"],
                running["reference"],
                running["level"],
                running["caster_id"],
                running["target_id"],
            ),
            (901, 3442, 20, self.character, -200),
        )
        timer = npc["state_ledger"]["entries"][1]["timer"]
        self.assertEqual(
            timer, dict(actor_id=self.character, expiration_round=2, phase="start")
        )
        self.assertEqual(row["snapshot"]["events"][-1]["kind"], "damage")
        json.dumps(row, default=lambda value: value.isoformat())
        self.assertEqual(
            self.checkpoints.end(
                self.account, self.generation, 77, expected_revision=revision
            ),
            3,
        )

    def test_owned_effect_uid_sequence_and_payloads_are_checkpointed(self):
        self.fight.native_effect_uid_next = 903
        self.fight.native_start_event_delivered = True
        self.fight.native_class_initializations = {self.character: {"breed": 11}}
        self.fight.state_wire_payloads[901] = "0102"
        self.fight.owned_stat_effects[902] = dict(
            uid=902,
            state_uid=901,
            target_id=self.character,
            actual=1,
            stat_id=2,
            payload="0304",
        )
        self.checkpoints.save(self.account, self.generation, self.fight)
        state = Checkpoints(self.store).read(self.account, 77)["snapshot"]
        self.assertEqual(state["native_effect_uid_next"], 903)
        self.assertTrue(state["native_start_event_delivered"])
        self.assertEqual(
            state["native_class_initializations"][str(self.character)], {"breed": 11}
        )
        self.assertEqual(state["state_wire_payloads"]["901"], "0102")
        self.assertEqual(state["owned_stat_effects"]["902"]["state_uid"], 901)

    def test_cas_foreign_account_and_replaced_generation_rejected(self):
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        with self.assertRaises(ValueError):
            self.checkpoints.save(
                self.account, self.generation, self.fight, expected_revision=0
            )
        with self.assertRaises(ValueError):
            self.checkpoints.read(self.account + 1, 77)
        new = self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.checkpoints.save(
                self.account, self.generation, self.fight, expected_revision=revision
            )
        self.store.select_character(self.account, new, self.character)
        with self.assertRaises(ValueError):
            self.checkpoints.save(
                self.account, new, self.fight, expected_revision=revision
            )

    def test_recovery_preserves_hp_and_does_not_resume_fight(self):
        self.fight.apply_damage(self.character, -200, 5)
        self.checkpoints.save(self.account, self.generation, self.fight)
        self.assertEqual(self.checkpoints.recover_interrupted(), 1)
        self.assertEqual(self.checkpoints.recover_interrupted(), 0)
        row = self.checkpoints.read(self.account, 77)
        self.assertEqual(row["status"], "aborted")
        self.assertEqual(row["snapshot"]["actors"]["-200"]["hp"], 7)

    def test_consumable_xp_handoff_checkpoint_is_atomic_and_never_refreshes(self):
        from wakfu_server import consumable_buffs
        from wakfu_server.consumable_catalog import load_plan

        with self.store.connection() as db:
            plan = load_plan(db, 22146)
            row = consumable_buffs.apply_states(
                self.store,
                db,
                self.character,
                plan["states"],
                source_item_ref=22146,
                source_item_uid=77146,
                generation=self.generation,
                now_ms=1000000,
            )[0]
            consumable_buffs.enter_combat(
                self.store,
                db,
                self.character,
                77,
                generation=self.generation,
                now_ms=1000000,
            )
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        self.fight.native_consumable_initializations = {
            self.character: (
                dict(
                    world_uid=row["uid"],
                    combat_uid=9002,
                    state_id=6874,
                    clock="online",
                    handoff_target=plan["states"][0]["metadata"][
                        "native_handoff_target"
                    ],
                    handoff=dict(
                        source_state_id=4872,
                        source_combat_uid=9001,
                        effect_id=316701,
                        applied_at_ms=1000000,
                    ),
                ),
            )
        }
        with self.assertRaisesRegex(ValueError, "Stale or foreign"):
            self.checkpoints.save(
                self.account,
                self.generation,
                self.fight,
                expected_revision=revision + 1,
            )
        with self.store.connection() as db:
            before = db.execute(
                "SELECT * FROM character_consumable_buffs WHERE uid=%s", (row["uid"],)
            ).fetchone()
        self.assertEqual(before["state_id"], 4872)
        self.assertFalse(getattr(self.fight, "native_consumable_handoff_committed", ()))
        saved_revision = self.checkpoints.save(
            self.account,
            self.generation,
            self.fight,
            expected_revision=revision,
        )
        with self.store.connection() as db:
            migrated = db.execute(
                "SELECT * FROM character_consumable_buffs WHERE uid=%s", (row["uid"],)
            ).fetchone()
        self.assertEqual(
            (migrated["state_id"], migrated["level"], migrated["remaining_ms"]),
            (6874, 100, 7200000),
        )
        self.assertEqual(
            (migrated["source_item_ref"], migrated["source_item_uid"]), (22146, 77146)
        )
        self.store.clock = lambda: 1001
        # Simulate recovery without the post-commit query cache. The durable
        # reference remains the authoritative once-only timer-reset fence.
        self.fight.native_consumable_handoff_committed = frozenset()
        self.checkpoints.save(
            self.account,
            self.generation,
            self.fight,
            expected_revision=saved_revision,
        )
        with self.store.connection() as db:
            repeated = db.execute(
                "SELECT * FROM character_consumable_buffs WHERE uid=%s", (row["uid"],)
            ).fetchone()
            current = consumable_buffs.active_states(
                self.store,
                db,
                self.character,
                generation=self.generation,
                now_ms=1001000,
            )[0]
        self.assertEqual(repeated["online_anchor_ms"], migrated["online_anchor_ms"])
        self.assertEqual(repeated["remaining_ms"], migrated["remaining_ms"])
        self.assertEqual(current["remaining_ms"], 7199000)
