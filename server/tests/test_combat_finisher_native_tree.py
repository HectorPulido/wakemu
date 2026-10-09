"""Actual owned initialization/cast reaches the original finisher tree."""
import random
import struct
import unittest


class FinisherNativeTreeTests(unittest.TestCase):
    def test_equipped_finisher_runs_on_actual_last_enemy_lethal_cast(self):
        from tests.test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.characters.cosmetics import OwnedCosmetics
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.spells import encode_deck
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from combat_audit_turns import advance_actual_turn

        account = OwnedCosmetics(3, ((5, 20753, 0, 0),)).equip_finishers(
            {"id": 7, "account_id": 3}, (20753,)
        )
        character, creature, fight = SpellTransactionTests().native_server_fixture(
            9, 200, target_hp=12, native_qi=True, owned_cosmetics=account
        )
        deck = encode_deck([4820])
        rng = random.Random(0)
        monsters = {-7: creature}
        initialized, _ = prepare_server_initialization(
            character, monsters, fight, 3, deck, action_id=1, rng=rng, fight_start=True
        )
        self.assertIn(
            4464, {s.reference for s in initialized.actors[7].state_ledger.entries}
        )
        runtime = RuntimeMessages(
            initialized,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                character, monsters, p, deck, rng=rng, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                character, monsters, p, deck, rng=rng, **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character, monsters, deck, action_id=action_id, critical=False, rng=rng
            )[0],
        )
        for _ in range(12):
            if runtime.fight.native_table_turn > 3 and runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        self.assertGreater(runtime.fight.native_table_turn, 3)
        target = runtime.fight.actors[-7].position
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 4820, *target),
            character,
            monsters,
            runtime.fight,
            3,
            deck,
            action_id=20,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(transaction.fight.actors[-7].hp, 0)
        self.assertTrue(
            any(
                row.get("finisher_policy")
                for row in transaction.fight.native_death_event_deliveries.values()
            )
        )
        from wakfu_server.wire import proto_fields
        from wakfu_server.combat_death import death_messages

        decoded = []
        for index, (opcode, payload) in enumerate(transaction.packets):
            if opcode == 12613:
                family, size = struct.unpack_from(">ih", payload, 13)
                fields = dict(proto_fields(payload[19 : 19 + size]))
                decoded.append((index, family, fields))
        finisher = [
            (index, fields) for index, family, fields in decoded if family == 1099
        ]
        self.assertEqual(
            len(finisher),
            1,
            (
                [
                    (family, fields.get(24), fields.get(32), fields.get(56))
                    for _, family, fields in decoded
                ],
                transaction.fight.native_finisher_after_death_packets,
            ),
        )
        finisher_index, fields = finisher[0]
        self.assertEqual(fields[24], 185395)  # Original native leaf identity.
        self.assertEqual(fields[32], 1100010)
        self.assertEqual(fields[56], (-7) & ((1 << 64) - 1))
        damage_indices = [index for index, family, fields in decoded if family == 2]
        self.assertTrue(damage_indices)
        self.assertLess(finisher_index, min(damage_indices))
        self.assertTrue(transaction.fight.native_finisher_after_death_packets["-7"])
        runtime.fight = transaction.fight
        runtime.action_id = transaction.action_id
        death = death_messages(runtime, -7)
        npc_death_states = [
            struct.unpack_from(">qB", payload, 12)
            for opcode, payload in death
            if opcode == 12727
        ]
        self.assertEqual(npc_death_states, [(-7, 0), (-7, 2)])
        from wakfu_server.combat_global_pv_collections import global_fighter_guards

        self.assertTrue(global_fighter_guards(runtime.fight, -7)["baK"])
        self.assertEqual(
            runtime.fight.actors[-7].native_death_status["last_writer"],
            "owned.aTS.F.type2",
        )
        cleanup = [
            (index, payload)
            for index, (opcode, payload) in enumerate(death)
            if opcode == 13560
        ]
        self.assertTrue(cleanup)
        self.assertTrue(all(index > 0 for index, payload in cleanup))
        self.assertNotIn("-7", runtime.fight.native_finisher_after_death_packets)
        delivered = runtime.prepare_delivery(death)
        started = [
            struct.unpack_from(">i", payload, 4)[0]
            for opcode, payload in delivered
            if opcode == 12727
        ]
        removed = [
            struct.unpack_from(">i", payload, 4)[0]
            for opcode, payload in delivered
            if opcode == 13560
        ]
        self.assertTrue(started and removed)
        self.assertGreater(min(removed), max(started))
