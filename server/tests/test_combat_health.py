import tempfile
import copy
from contextlib import contextmanager
from unittest.mock import patch
from postgres_case import PostgresCase
from tests import test_combat_rewards
from wakfu_server import health_store, health_policy, health
from wakfu_server.combat_health import persist, persist_aborted_fight
from wakfu_server.consumable_buffs import apply_states, enter_combat, snapshot
from wakfu_server.combat_rewards import Policy, award


class FightExitHealthTests(PostgresCase):
    def state(self, directory):
        (
            store,
            account,
            char,
            generation,
            fight,
        ) = test_combat_rewards.setup_reward_state(self.store)
        char = health_store.initialize(
            store, account, generation, char["id"], coefficient=0
        )
        actor = fight.actors[char["id"]]
        actor.hp = char["hp"] - 9
        actor.max_hp = char["max_hp"]
        return store, account, char, generation, fight

    def test_disconnect_persists_damage_without_rewards_and_duplicate_keeps_world_updates(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            f.phase = "active"
            f.winner = None
            with s.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='active' WHERE id=%s", (f.id,)
                )
            result = persist_aborted_fight(s, a, g, c, f)
            self.assertTrue(result["applied"])
            self.assertEqual(result["character"]["hp"], f.actors[c["id"]].hp)
            self.assertEqual(
                (result["character"]["xp"], result["character"]["kamas"]), (c["xp"], 0)
            )
            self.assertEqual(f.phase, "active")
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )
                current = s.character(a, c["id"], db)
                health_policy.apply(db, current, current["hp"] + 1)
                db.execute("UPDATE characters SET x=44 WHERE id=%s", (c["id"],))
                baseline = db.execute(
                    "SELECT started_at FROM character_regeneration WHERE character_id=%s",
                    (c["id"],),
                ).fetchone()["started_at"]
            s.clock = lambda: 1001
            again = persist_aborted_fight(s, a, g, c, f)
            self.assertFalse(again["applied"])
            self.assertEqual(again["character"]["x"], 44)
            self.assertEqual(again["character"]["hp"], result["character"]["hp"] + 1)
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT started_at FROM character_regeneration WHERE character_id=%s",
                        (c["id"],),
                    ).fetchone()["started_at"],
                    baseline,
                )

    def test_replaced_lease_and_stale_health_do_not_overwrite_new_state(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            with s.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='active' WHERE id=%s", (f.id,)
                )
            with s.connection() as db:
                current = s.character(a, c["id"], db)
                health_policy.apply(db, current, current["hp"] - 1)
            self.assertIsNone(persist_aborted_fight(s, a, g, c, f))
            new = s.begin_session(a)
            s.select_character(a, new, c["id"])
            from wakfu_server.fight_store import create

            newer_fight = create(s, a, new, c["id"])
            self.assertIsNone(persist_aborted_fight(s, a, g, c, f))
            self.assertEqual(s.character(a, c["id"])["hp"], c["hp"] - 1)
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_health_exits WHERE character_id=%s",
                        (c["id"],),
                    ).fetchone()["count"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (f.id,)
                    ).fetchone()["status"],
                    "aborted",
                )
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (newer_fight,)
                    ).fetchone()["status"],
                    "placement",
                )

    def test_old_disconnect_cannot_abort_fight_after_owner_takeover(self):
        with tempfile.TemporaryDirectory() as directory:
            store, account, character, generation, fight = self.state(directory)
            with store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='active' WHERE id=%s",
                    (fight.id,),
                )
                db.execute(
                    "UPDATE combat_fight_participants SET session_generation=%s "
                    "WHERE fight_id=%s AND character_id=%s",
                    (generation, fight.id, character["id"]),
                )
            next_generation = store.begin_session(account)
            store.select_character(account, next_generation, character["id"])
            from wakfu_server.fight_store import takeover_participant

            self.assertTrue(
                takeover_participant(
                    store,
                    account,
                    next_generation,
                    character["id"],
                    fight.id,
                    previous_generation=generation,
                )
            )
            self.assertIsNone(
                persist_aborted_fight(store, account, generation, character, fight)
            )
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                    ).fetchone()["status"],
                    "active",
                )
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_health_exits "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()["count"],
                    0,
                )

    def test_abort_sql_failure_rolls_back_hp_receipt_and_fight_then_retry_succeeds(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            store, account, character, generation, fight = self.state(directory)
            fight.phase = "active"
            fight.winner = None
            with store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
                )
            before = store.character(account, character["id"])
            original_connection = store.connection

            @contextmanager
            def fail_abort_status():
                with original_connection() as db:

                    class FaultingConnection:
                        def execute(self, query, *args, **kwargs):
                            if "UPDATE combat_fights f SET status='aborted'" in query:
                                raise RuntimeError("injected durable abort failure")
                            return db.execute(query, *args, **kwargs)

                        def __getattr__(self, name):
                            return getattr(db, name)

                    yield FaultingConnection()

            with patch.object(store, "connection", side_effect=fail_abort_status):
                with self.assertRaisesRegex(
                    RuntimeError, "injected durable abort failure"
                ):
                    persist_aborted_fight(store, account, generation, character, fight)

            after = store.character(account, character["id"])
            self.assertEqual(
                (after["hp"], after["hp_damage"], after["health_dead"]),
                (before["hp"], before["hp_damage"], before["health_dead"]),
            )
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                    ).fetchone()["status"],
                    "active",
                )
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_health_exits WHERE fight_id=%s",
                        (fight.id,),
                    ).fetchone()["count"],
                    0,
                )

            retried = persist_aborted_fight(
                store, account, generation, character, fight
            )
            self.assertTrue(retried["applied"])
            self.assertEqual(
                retried["character"]["hp"], fight.actors[character["id"]].hp
            )
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                    ).fetchone()["status"],
                    "aborted",
                )
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_health_exits WHERE fight_id=%s",
                        (fight.id,),
                    ).fetchone()["count"],
                    1,
                )

    def test_borrowed_abort_rejects_autocommit_connection(self):
        from wakfu_server.fight_store import abort
        from psycopg import connect

        with tempfile.TemporaryDirectory() as directory:
            store, account, character, generation, fight = self.state(directory)
            with store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
                )
            db = connect(
                store.database.conninfo,
                **store.database.connection_kwargs,
                autocommit=True,
            )
            try:
                with self.assertRaisesRegex(ValueError, "active transaction"):
                    abort(store, account, character["id"], fight.id, db=db)
            finally:
                db.close()
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                    ).fetchone()["status"],
                    "active",
                )

    def test_duplicate_return_does_not_reset_health_or_create_another_award(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_lifecycle import return_to_world
        import struct

        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            runtime = RuntimeMessages(f)
            body = struct.pack(">iB", f.id, 0)
            first = return_to_world(s, a, g, c, runtime, body, wp=6)
            self.assertTrue(first["applied"])
            again = return_to_world(s, a, g, c, runtime, body, wp=6)
            self.assertFalse(again["applied"])
            self.assertEqual(again["packets"], [])
            self.assertEqual(again["character"], first["character"])

    def test_return_encoder_failure_rolls_back_health_exit_then_retry_emits_packets(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_lifecycle import return_to_world
        import struct

        with tempfile.TemporaryDirectory() as directory:
            store, account, character, generation, fight = self.state(directory)
            runtime = RuntimeMessages(fight)
            body = struct.pack(">iB", fight.id, 0)
            with store.connection() as db:
                before_hp = db.execute(
                    "SELECT hp FROM characters WHERE id=%s", (character["id"],)
                ).fetchone()["hp"]
                before_regen = db.execute(
                    "SELECT initial_hp,started_at,last_at,coefficient FROM character_regeneration WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()

            with patch(
                "wakfu_server.combat_lifecycle.outside_progression",
                side_effect=ValueError("Injected progression encoder failure"),
            ):
                with self.assertRaisesRegex(
                    ValueError, "Injected progression encoder failure"
                ):
                    return_to_world(
                        store, account, generation, character, runtime, body, wp=6
                    )

            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT hp FROM characters WHERE id=%s", (character["id"],)
                    ).fetchone()["hp"],
                    before_hp,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT initial_hp,started_at,last_at,coefficient FROM character_regeneration WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone(),
                    before_regen,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS count FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()["count"],
                    0,
                )

            retried = return_to_world(
                store, account, generation, character, runtime, body, wp=6
            )
            self.assertTrue(retried["applied"])
            self.assertTrue(retried["packets"])
            self.assertEqual(
                retried["character"]["hp"], fight.actors[character["id"]].hp
            )
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS count FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()["count"],
                    1,
                )

    def test_active_abort_keeps_zero_hp_and_does_not_apply_finished_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            store, account, character, generation, fight = self.state(directory)
            fight.phase = "active"
            fight.winner = None
            fight.actors[character["id"]].hp = 0
            result = persist(
                store, account, generation, character, fight, reason="abort"
            )
            self.assertEqual((result["character"]["hp"], result["coefficient"]), (0, 0))
            self.assertTrue(result["character"]["health_dead"])
            reopened = health_store.initialize(
                store, account, generation, character["id"], coefficient=1
            )
            self.assertEqual(reopened["hp"], 0)

    def test_finished_recovery_receipt_does_not_reset_later_world_healing(self):
        with tempfile.TemporaryDirectory() as directory:
            store, account, character, generation, fight = self.state(directory)
            fight.actors[character["id"]].hp = 0
            fight.winner = 1
            result = persist(store, account, generation, character, fight)
            self.assertEqual(result["character"]["hp"], 1)
            with store.connection() as db:
                current = store.character(account, character["id"], db)
                health_policy.apply(db, current, 3)
            again = persist(store, account, generation, character, fight)
            self.assertFalse(again["applied"])
            self.assertEqual(again["character"]["hp"], 3)
            self.assertEqual(fight.actors[character["id"]].hp, 0)

    def test_finished_defeat_return_recovers_one_hp_with_regeneration_and_no_rewards(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            f.actors[c["id"]].hp = 0
            f.winner = 1
            result = persist(s, a, g, c, f)
            self.assertEqual(
                (result["character"]["hp"], result["coefficient"]),
                (1, health.exploration_coefficient(result["character"]["max_hp"], 1)),
            )
            self.assertFalse(result["character"]["health_dead"])
            self.assertEqual(
                result["character"]["hp_damage"], result["character"]["max_hp"] - 1
            )
            self.assertEqual(f.actors[c["id"]].hp, 0)
            self.assertEqual(
                (result["character"]["xp"], result["character"]["kamas"]), (c["xp"], 0)
            )
            with s.connection() as db:
                exit_row = db.execute(
                    "SELECT reason,return_acknowledged_at FROM fight_health_exits "
                    "WHERE fight_id=%s AND character_id=%s",
                    (f.id, c["id"]),
                ).fetchone()
                self.assertEqual(exit_row["reason"], "return")
                self.assertIsNotNone(
                    exit_row["return_acknowledged_at"],
                    "a normal PvE persist call is the native return callback",
                )
                db.execute(
                    "UPDATE combat_fight_participants SET session_generation=%s "
                    "WHERE fight_id=%s AND character_id=%s",
                    (g, f.id, c["id"]),
                )
            reopened = health_store.initialize(s, a, g, c["id"], coefficient=1)
            self.assertEqual(reopened["hp"], 1)
            self.assertFalse(reopened["health_dead"])
            replacement = s.begin_session(a)
            s.select_character(a, replacement, c["id"])
            from wakfu_server.fight_store import takeover_participant

            with self.assertRaisesRegex(ValueError, "already acknowledged return"):
                takeover_participant(
                    s,
                    a,
                    replacement,
                    c["id"],
                    f.id,
                    previous_generation=g,
                )
            s.clock = lambda: 1005
            current = health_store.tick(s, a, replacement, c["id"], reopened["hp"])
            self.assertEqual(current["hp"], 2)
            self.assertFalse(current["health_dead"])
            self.assertEqual((current["xp"], current["kamas"]), (c["xp"], 0))
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )

    def test_temporary_combat_maximum_does_not_change_wound_debt(self):
        with tempfile.TemporaryDirectory() as directory:
            store, account, character, generation, fight = self.state(directory)
            character = health_store.sync(
                store,
                account,
                generation,
                character["id"],
                character["hp"],
                50,
                coefficient=0,
            )
            actor = fight.actors[character["id"]]
            actor.max_hp = 120
            actor.hp = 105

            result = persist_aborted_fight(store, account, generation, character, fight)

            self.assertTrue(result["applied"])
            persisted = result["character"]
            self.assertEqual(
                (persisted["max_hp"], persisted["hp"], persisted["hp_damage"]),
                (60, 45, 15),
            )

            healed_fight = copy.deepcopy(fight)
            healed_fight.id = 8
            healed_fight.phase = "active"
            healed_fight.winner = None
            healed_fight.actors[character["id"]].max_hp = 120
            healed_fight.actors[character["id"]].hp = 115
            healed = persist_aborted_fight(
                store, account, generation, persisted, healed_fight
            )
            self.assertTrue(healed["applied"])
            self.assertEqual(
                (
                    healed["character"]["max_hp"],
                    healed["character"]["hp"],
                    healed["character"]["hp_damage"],
                ),
                (60, 55, 5),
            )
            reopened = self.reopen().character(account, character["id"])
            self.assertEqual(
                (reopened["max_hp"], reopened["hp"], reopened["hp_damage"]), (60, 55, 5)
            )

    def test_finished_health_receipt_emits_consumable_counters_once(self):
        store, account, character, generation, fight = self.state("unused")
        with store.connection() as db:
            for reference in (5010, 9811):
                row = db.execute(
                    "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=%s",
                    (reference,),
                ).fetchone()
                apply_states(
                    store,
                    db,
                    character["id"],
                    [row["state"]],
                    source_item_ref=reference,
                    source_item_uid=reference,
                    generation=generation,
                )
            enter_combat(store, db, character["id"], fight.id, generation=generation)
        before = snapshot(store, character["id"])
        fight.native_class_initializations = {}
        fight.native_consumable_initializations = {character["id"]: ()}
        updates = [
            dict(
                uid=state["uid"],
                state_id=state["state_id"],
                removed=False,
                level=state["level"],
                clock=state["clock"],
                remaining_ms=state["remaining_ms"],
            )
            for state in before
        ]
        reward = award(store, account, generation, character["id"], fight, Policy(xp=1))
        self.assertTrue(reward["awarded"])
        with patch(
            "wakfu_server.combat_consumable_states.returning_states",
            return_value=tuple(updates),
        ):
            first = persist(store, account, generation, character, fight)
            self.assertTrue(first["applied"])
            current = {row["state_id"]: row for row in snapshot(store, character["id"])}
            self.assertEqual(current[4436]["level"], 4)
            self.assertNotIn(732, current)
            duplicate = persist(store, account, generation, character, fight)
        self.assertFalse(duplicate["applied"])
        current = {row["state_id"]: row for row in snapshot(store, character["id"])}
        self.assertEqual(current[4436]["level"], 4)
        self.assertNotIn(732, current)

    def test_placement_abort_does_not_emit_fight_end_consumable_counters(self):
        store, account, character, generation, fight = self.state("unused")
        fight.phase = "active"
        fight.winner = None
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='placement' WHERE id=%s", (fight.id,)
            )
            for reference in (5010, 9811):
                descriptor = db.execute(
                    "SELECT plan->'states'->0 AS state FROM native_consumable_actions WHERE item_ref=%s",
                    (reference,),
                ).fetchone()["state"]
                apply_states(
                    store,
                    db,
                    character["id"],
                    [descriptor],
                    source_item_ref=reference,
                    source_item_uid=reference,
                    generation=generation,
                )
            enter_combat(store, db, character["id"], fight.id, generation=generation)

        result = persist_aborted_fight(store, account, generation, character, fight)

        self.assertTrue(result["applied"])
        current = {row["state_id"]: row for row in snapshot(store, character["id"])}
        self.assertEqual(current[4436]["level"], 5)
        self.assertIn(732, current)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
