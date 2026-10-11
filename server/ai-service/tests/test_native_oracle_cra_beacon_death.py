"""Real owned Cra beacon death through the NPC commit/delivery boundary."""
import os
import random
import struct
import unittest
from unittest.mock import patch

import test_native_oracle as oracle_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativeOracleCraBeaconDeathTests(unittest.TestCase):
    def test_actual_npc_attack_delivers_only_beacon_death_and_rolls_back_delivery_failure(
        self,
    ):
        from test_combat_spell_transaction import SpellTransactionTests
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_ai.context.native_context import encode
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_death import newly_registered_death_messages
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            9, 200, native_qi=True, target_distance=3, variation_seed=17
        )
        deck = encode_deck()
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(0),
            fight_start=True,
        )
        _, adapter = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=2,
            critical=False,
            rng=random.Random(0),
        )
        uid = granted_spells(fight, 7)[7793]["uid"]
        selection = eligible_cast_targets(
            fight,
            character,
            deck,
            uid,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            actor_id=7,
            limit=256,
            maximum_eligible=16,
        )
        enemy = fight.actors[-7]
        candidates = [
            row["target"]
            for row in selection["eligible"]
            if abs(row["target"][0] - enemy.position[0])
            + abs(row["target"][1] - enemy.position[1])
            == 1
        ]
        self.assertTrue(candidates, selection)
        source = snapshot(fight)
        created = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *candidates[0]),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(0),
        )
        self.assertEqual(snapshot(fight), source)
        beacon = next(
            actor
            for actor in created.fight.actors.values()
            if getattr(actor, "native_summon_action_book", {}).get("profile") == 3798
        )
        self.assertIn(7781, {entry.reference for entry in beacon.state_ledger.entries})
        # A coherent injured fixture, not a synthetic death or injected damage.
        set_hp_raw_current(beacon, 1)
        self.assertEqual(beacon.hp, 1)
        runtime = RuntimeMessages(created.fight)
        for _ in range(20):
            if runtime.fight.current.id == -7:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, -7)
        oracle = oracle_fixture.NativeOracleTests.oracle_for(
            runtime, character, monster, deck
        )
        action = dict(
            type="cast",
            spellId=7962,
            level=1,
            targetId=beacon.id,
            target=list(beacon.position),
        )
        before = encode(runtime)
        with patch(
            "wakfu_server.combat_los.authoritative_visible", return_value=True
        ), patch(
            "wakfu_server.combat_death.death_messages",
            side_effect=ValueError("beacon death delivery failure"),
        ):
            with self.assertRaisesRegex(ValueError, "beacon death delivery failure"):
                oracle.commit(action, stats_serializer=lambda *args: b"")
        self.assertEqual(encode(runtime), before)
        before_sequence = runtime.fight.sequence
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            packets = oracle.commit(action, stats_serializer=lambda *args: b"")
        deaths = [
            struct.unpack(">iiiqB", body)[3:]
            for opcode, body in packets
            if opcode == 12727
        ]
        self.assertTrue(deaths)
        self.assertEqual({identity for identity, _ in deaths}, {beacon.id})
        self.assertEqual(sum(state == 2 for _, state in deaths), 1)
        dead = runtime.fight.actors[beacon.id]
        self.assertEqual(dead.hp, 0)
        self.assertEqual(dead.native_obstacle_id, -1)
        current_registry(runtime.fight)
        self.assertEqual(
            newly_registered_death_messages(runtime, after_sequence=before_sequence), []
        )
        self.assertNotEqual(encode(runtime), before)
