"""Actual native981 world capture and all four contextual one-level cures."""
from copy import deepcopy
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import health_store
from wakfu_server.combat_health import persist
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_state_handler import StateCarrierContext
from wakfu_server.inventory_consumable_effects import use
from wakfu_server.inventory_items import grant


class NativeAntiKoReturnPostgresTests(PostgresCase):
    def test_native_capture_return_rollback_and_four_real_cures(self):
        from test_combat_consumable_outcome import CombatConsumableOutcomeTests
        from wakfu_server.consumable_buff_wire import delta
        from wakfu_server.consumable_characteristics import bonuses

        for index in range(3):
            account = self.store.register("native-ko-" + str(index), "test-password")[
                "id"
            ]
        self.assertEqual(3, account)
        for index in range(7):
            character = self.store.create_character(
                account,
                (
                    "NativeA",
                    "NativeB",
                    "NativeC",
                    "NativeD",
                    "NativeE",
                    "NativeF",
                    "NativeG",
                )[index],
                breed=19,
            )
        self.assertEqual(7, character["id"])
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=200 WHERE id=7")
        character = health_store.initialize(self.store, account, generation, 7)
        character = health_store.sync(
            self.store, account, generation, 7, character["hp"], 60
        )
        _, _monsters, _deck, fight, factory = CombatConsumableOutcomeTests()._fixture(
            10657
        )
        actor = fight.actors[7]
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
        for _ in range(4):
            with fight.effect_resolution():
                dispatcher.native_retention.apply_state_reference(
                    dispatcher.native_state_handler,
                    EffectInvocation(2226, 1, 7, 7, actor.position),
                    987,
                    1,
                    carrier_context=context,
                )
        entry = next(row for row in actor.state_ledger.entries if row.reference == 981)
        self.assertEqual(4, entry.level)
        fight.phase, fight.winner = "finished", 0
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(%s,'finished')",
                (fight.id,),
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,7,3,0,%s)",
                (fight.id, generation),
            )
        original_bindings = deepcopy(fight.native_consumable_initializations)
        with self.assertRaisesRegex(RuntimeError, "rollback external capture"):
            with self.store.connection() as db:
                persist(self.store, account, generation, character, fight, db=db)
                raise RuntimeError("rollback external capture")
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) n FROM character_consumable_buffs"
                ).fetchone()["n"],
            )
            self.assertEqual(
                0,
                db.execute("SELECT count(*) n FROM fight_health_exits").fetchone()["n"],
            )
        self.assertEqual(original_bindings, fight.native_consumable_initializations)
        result = persist(self.store, account, generation, character, fight)
        self.assertTrue(result["applied"])
        current = result["character"]
        state = next(
            row for row in current["consumable_states"] if row["state_id"] == 981
        )
        self.assertIsNone(state["source_item_ref"])
        self.assertIsNone(state["source_item_uid"])
        self.assertEqual(45980, state["native_origin"]["effect_id"])
        self.assertEqual(4, state["level"])
        self.assertEqual(actor.max_hp, current["max_hp"])
        self.assertEqual({1: -40}, bonuses(current)["percentages"])
        self.assertEqual(-3, bonuses(current)["stats"][4])
        self.assertEqual(original_bindings, fight.native_consumable_initializations)
        fixed_clock = self.store.clock()
        self.store.clock = lambda: fixed_clock
        container = next(
            row["uid"] for row in current["inventory_containers"] if row["kind"] == 0
        )
        deadline = None
        source_uids = []
        for slot, reference in enumerate((10657, 15980, 20471, 24265)):
            source = grant(
                self.store,
                account,
                generation,
                7,
                reference=reference,
                quantity=2,
                container=container,
                slot=slot,
                allowed_references={reference},
            )
            source_uids.append(source["uid"])
            before = self.store.character(account, 7)
            used = use(
                self.store,
                account,
                generation,
                7,
                struct.pack(">qB", source["uid"], 0),
                expected_hp=before["hp"],
                in_fight=False,
            )
            current = used["character"]
            remaining = [
                row for row in current["consumable_states"] if row["state_id"] == 981
            ]
            if slot < 3:
                self.assertEqual(3 - slot, remaining[0]["level"])
                with self.store.connection() as db:
                    stored = db.execute(
                        "SELECT remaining_ms,online_anchor_ms FROM character_consumable_buffs "
                        "WHERE character_id=7 AND state_id=981"
                    ).fetchone()
                value = stored["remaining_ms"] + stored["online_anchor_ms"]
                deadline = value if deadline is None else deadline
                self.assertEqual(deadline, value)
            else:
                self.assertEqual([], remaining)
            self.assertTrue(
                any(opcode == 13560 for opcode, _ in delta(before, current))
            )
        with self.assertRaises(ValueError):
            use(
                self.store,
                account,
                generation,
                7,
                struct.pack(">qB", source_uids[0], 0),
                expected_hp=current["hp"],
                in_fight=False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                [1, 1, 1, 1],
                [
                    row["quantity"]
                    for row in db.execute(
                        "SELECT quantity FROM inventory_items WHERE uid=ANY(%s) ORDER BY uid",
                        (source_uids,),
                    ).fetchall()
                ],
            )
        repeated = persist(self.store, account, generation, character, fight)
        self.assertFalse(repeated["applied"])
        self.assertFalse(repeated["character"]["consumable_states"])
