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
