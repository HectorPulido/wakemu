"""Durable qualification of the real 987 -> 45980 -> 981 carrier."""
from random import Random

from postgres_case import PostgresCase


class NativeExternalRetainedStatePostgresTests(PostgresCase):
    def test_real_native_carrier_is_captured_and_reduced_once(self):
        from test_combat_consumable_outcome import CombatConsumableOutcomeTests
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_native_timing_context import native_time_payload
        from wakfu_server.combat_state_handler import StateCarrierContext
        from wakfu_server.combat_health import persist
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.items.consumable_state_reduction import reduce_states
        from wakfu_server.consumable_catalog import load_plan

        self.store.clock = lambda: 1000
        # Match the production-native fixture's account 3 / character 7 IDs.
        accounts = [
            self.store.register(f"external-{i}", "local-password")["id"]
            for i in range(3)
        ]
        for index, account in enumerate(accounts[:2]):
            self.store.create_character(account, ("Other", "Foreign")[index])
        account = accounts[2]
        for name in ("Aaa", "Bbb", "Ccc", "Ddd"):
            self.store.create_character(account, name)
        character_row = self.store.create_character(account, "NativeOwner")
        self.assertEqual(7, character_row["id"])
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character_row["id"])

        (
            native_character,
            _monsters,
            _deck,
            fight,
            factory,
        ) = CombatConsumableOutcomeTests()._fixture(10657)
        character_id = native_character["id"]
        self.assertEqual(character_row["id"], character_id)
        actor = fight.actors[character_id]
        fight.id = 78
        actor.owner_id = account
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=200 WHERE id=%s", (character_id,))
            maximum = effective_character(
                self.store.character(account, character_id, db)
            )["max_hp"]
            db.execute(
                "UPDATE characters SET hp=%s,max_hp=%s,hp_damage=0,health_dead=false WHERE id=%s",
                (maximum, maximum, character_id),
            )
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(78,'finished')"
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(78,%s,%s,0,%s)",
                (character_id, account, generation),
            )

        dispatcher, _ = factory(action_id=2)(
            fight, {"native_retained_container": {"present": False}}
        )
        context = StateCarrierContext(
            0,
            0,
            False,
            None,
            None,
            False,
            False,
            False,
            0,
            native_time_payload(realtime_remaining=0),
        )
        for _ in range(2):
            with fight.effect_resolution():
                self.assertTrue(
                    dispatcher.native_retention.apply_state_reference(
                        dispatcher.native_state_handler,
                        EffectInvocation(2226, 1, actor.id, actor.id, actor.position),
                        987,
                        1,
                        carrier_context=context,
                    )
                )
        fight.phase = "finished"
        fight.winner = 0
        carrier = next(
            entry for entry in actor.state_ledger.entries if entry.reference == 981
        )
        self.assertEqual(2, carrier.level)
        actor.max_hp = maximum
        set_hp_raw_current(actor, maximum)
        with self.store.connection() as db:
            saved = self.store.character(account, character_id, db)
            result = persist(self.store, account, generation, saved, fight, db=db)
            self.assertTrue(result["applied"])
            row = db.execute(
                "SELECT * FROM character_consumable_buffs WHERE character_id=%s AND state_id=981",
                (character_id,),
            ).fetchone()
            self.assertEqual(2, row["level"])
            self.assertIsNone(row["source_item_ref"])
            self.assertIsNone(row["source_item_uid"])
            self.assertEqual(45980, row["native_origin"]["effect_id"])
            self.assertEqual(987, row["native_origin"]["parent_state_id"])
            self.assertIsNone(row["combat_id"])
            remaining_before = row["remaining_ms"]
            plan = load_plan(db, 10657)
            reduction = plan["reduce_states"]
            reduce_states(
                self.store, db, character_id, reduction, generation=generation
            )
            reduced = db.execute(
                "SELECT level,remaining_ms,online_anchor_ms FROM character_consumable_buffs WHERE character_id=%s AND state_id=981",
                (character_id,),
            ).fetchone()
            self.assertEqual(1, reduced["level"])
            self.assertEqual(remaining_before, reduced["remaining_ms"])
            self.assertEqual(1_000_000, reduced["online_anchor_ms"])
            reduce_states(
                self.store, db, character_id, reduction, generation=generation
            )
            self.assertIsNone(
                db.execute(
                    "SELECT uid FROM character_consumable_buffs WHERE character_id=%s AND state_id=981",
                    (character_id,),
                ).fetchone()
            )
