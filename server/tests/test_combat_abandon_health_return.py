"""Real PostgreSQL qualification of authenticated abandonment health returns."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from test_combat_abandon import setup_abandon_state
from wakfu_server import combat_abandon, combat_health, health, health_store
from wakfu_server.combat_state import Actor


class AbandonHealthReturnTests(PostgresCase):
    def state(self, *, dead_hero=False):
        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        hero = store.create_character(account, "Companion")
        fight.walkable.add((2, 0, 0))
        fight.placement[0].add((2, 0, 0))
        fight.actors[hero["id"]] = Actor(
            hero["id"],
            0,
            (2, 0, 0),
            hero["hp"],
            6,
            3,
            0,
            hero["level"],
            account,
            True,
            max_hp=hero["max_hp"],
        )
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation,entry_hp,"
                "entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
                (
                    fight.id,
                    hero["id"],
                    account,
                    generation,
                    hero["hp"],
                    hero["max_hp"],
                    hero["hp_damage"],
                    hero["health_dead"],
                ),
            )
        fight.ready(account)
        self.assertEqual(fight.current.id, -200)
        casualty = hero if dead_hero else character
        survivor = character if dead_hero else hero
        fight.apply_damage(-200, casualty["id"], fight.actors[casualty["id"]].hp)
        fight.apply_damage(-200, survivor["id"], 4)
        self.assertEqual(fight.phase, "active")
        return store, account, generation, character, fight, runtime, hero

    def acknowledge(self, values):
        store, account, generation, character, fight, runtime, _ = values
        return combat_abandon.return_to_world(
            store,
            account,
            generation,
            character,
            runtime,
            struct.pack(">iB", fight.id, 0),
            wp=6,
        )

    def receipts(self, values):
        store, _, _, _, fight, _, _ = values
        with store.connection() as db:
            return tuple(
                db.execute(
                    "SELECT character_id,generation,reason,created_at,abandon_return_acknowledged_at "
                    "FROM fight_health_exits WHERE fight_id=%s ORDER BY character_id",
                    (fight.id,),
                )
            )

    def test_dead_main_recovers_after_ack_only_with_native_coefficient_and_repeat_is_noop(
        self,
    ):
        values = self.state()
        store, account, generation, character, fight, runtime, hero = values
        combat_abandon.prepare(store, account, generation, character, runtime, b"")
        before = self.receipts(values)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        self.assertTrue(
            all(row["abandon_return_acknowledged_at"] is None for row in before)
        )
        result = self.acknowledge(values)
        saved = result["character"]
        self.assertEqual((saved["hp"], saved["health_dead"]), (1, False))
        self.assertEqual(store.character(account, hero["id"])["hp"], hero["hp"] - 4)
        self.assertEqual(fight.actors[character["id"]].hp, 0)
        self.assertEqual(fight.winner, None)
        hp_packets = [
            payload for opcode, payload in result["packets"] if opcode == 12436
        ]
        self.assertEqual(
            hp_packets,
            [
                health.packet(
                    saved["id"], 1, health.exploration_coefficient(saved["max_hp"], 1)
                )
            ],
        )
        after = self.receipts(values)
        self.assertEqual(
            [dict(row, abandon_return_acknowledged_at=None) for row in after],
            list(before),
        )
        self.assertTrue(
            all(row["abandon_return_acknowledged_at"] is not None for row in after)
        )
        store.clock = lambda: 1004
        health_store.tick(
            store, account, generation, character["id"], 1, now_ms=1004000
        )
        progressed = store.character(account, character["id"])
        self.assertGreater(progressed["hp"], 1)
        # Also exercise the durable fence after loss of the in-memory flag.
        runtime.abandon_returned = False
        repeated = self.acknowledge(values)
        self.assertEqual(repeated["character"]["hp"], progressed["hp"])
        self.assertEqual(repeated["packets"], [])
        self.assertEqual(self.receipts(values), after)
        self.assertEqual(self.acknowledge(values)["packets"], [])

    def test_dead_hero_recovers_without_healing_wounded_main(self):
        from wakfu_server import heroes

        values = self.state(dead_hero=True)
        store, account, generation, character, _, runtime, hero = values
        combat_abandon.prepare(store, account, generation, character, runtime, b"")
        with self.assertRaisesRegex(
            ValueError, "Dead characters cannot join as heroes"
        ):
            heroes.add(store, account, generation, character["id"], hero["id"])
        self.acknowledge(values)
        self.assertEqual(store.character(account, hero["id"])["hp"], 1)
        self.assertFalse(store.character(account, hero["id"])["health_dead"])
        self.assertEqual(
            store.character(account, character["id"])["hp"], character["hp"] - 4
        )
        self.assertTrue(
            heroes.add(store, account, generation, character["id"], hero["id"])[
                "applied"
            ]
        )

    def test_failure_after_recovery_rolls_back_health_regeneration_and_receipts(self):
        values = self.state()
        store, account, generation, character, _, runtime, _ = values
        combat_abandon.prepare(store, account, generation, character, runtime, b"")
        before = self.receipts(values)
        actual = store.character

        def fail_after_update(owner, identity, db=None):
            result = actual(owner, identity, db)
            if identity == character["id"] and result["hp"] == 1:
                raise RuntimeError("injected return publication failure")
            return result

        with patch.object(store, "character", side_effect=fail_after_update):
            with self.assertRaisesRegex(RuntimeError, "injected return publication"):
                self.acknowledge(values)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        self.assertEqual(self.receipts(values), before)
        self.assertFalse(runtime.abandon_returned)
        with store.connection() as db:
            row = db.execute(
                "SELECT initial_hp,coefficient FROM character_regeneration WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
            self.assertEqual((row["initial_hp"], row["coefficient"]), (0, 0))

    def test_wrong_generation_or_wrong_ack_cannot_recover(self):
        values = self.state()
        store, account, generation, character, fight, runtime, _ = values
        combat_abandon.prepare(store, account, generation, character, runtime, b"")
        with self.assertRaises(ValueError):
            combat_abandon.return_to_world(
                store,
                account,
                generation,
                character,
                runtime,
                struct.pack(">iB", fight.id + 1, 0),
                wp=6,
            )
        store.begin_session(account)
        with self.assertRaises(ValueError):
            self.acknowledge(values)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        self.assertTrue(
            all(
                row["abandon_return_acknowledged_at"] is None
                for row in self.receipts(values)
            )
        )

    def test_invalid_return_packet_rolls_back_completed_health_ack(self):
        values = self.state()
        store, account, generation, character, _, runtime, _ = values
        combat_abandon.prepare(store, account, generation, character, runtime, b"")
        before = self.receipts(values)
        with patch.object(
            combat_abandon,
            "outside_progression",
            side_effect=ValueError("invalid return packet"),
        ):
            with self.assertRaisesRegex(ValueError, "invalid return packet"):
                self.acknowledge(values)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        self.assertEqual(self.receipts(values), before)
        self.assertFalse(runtime.abandon_returned)

    def test_disconnect_abort_does_not_recover_before_an_explicit_continuation(self):
        values = self.state()
        store, account, generation, character, fight, runtime, _ = values
        combat_health.persist_aborted_fight(
            store, account, generation, character, fight
        )
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        self.assertTrue(store.character(account, character["id"])["health_dead"])
        with self.assertRaises(ValueError):
            self.acknowledge(values)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)

    def test_placement_abandon_ack_preserves_living_health(self):
        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        result = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        self.assertEqual(result["character"]["hp"], character["hp"])
        result = combat_abandon.return_to_world(
            store,
            account,
            generation,
            character,
            runtime,
            struct.pack(">iB", fight.id, 0),
            wp=6,
        )
        self.assertEqual(result["character"]["hp"], character["hp"])

    def test_abort_and_normal_ack_columns_preserve_distinct_reason_constraints(self):
        from psycopg.errors import CheckViolation

        values = self.state()
        store, account, generation, character, fight, runtime, _ = values
        combat_abandon.prepare(store, account, generation, character, runtime, b"")
        self.acknowledge(values)
        before = self.receipts(values)
        with self.assertRaises(CheckViolation):
            with store.connection() as db:
                db.execute(
                    "UPDATE fight_health_exits SET return_acknowledged_at=%s "
                    "WHERE fight_id=%s AND character_id=%s",
                    (store.now(), fight.id, character["id"]),
                )
        with self.assertRaises(CheckViolation):
            with store.connection() as db:
                db.execute(
                    "UPDATE fight_health_exits SET reason='return' "
                    "WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                )
        self.assertEqual(self.receipts(values), before)
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits "
                    "WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
