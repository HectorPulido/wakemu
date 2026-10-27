"""Paid native Sacrier attack with Multibrazos and the undead carrier."""
import random
import struct
import unittest

import audit_active_spells as native
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
    server_runtime,
)
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class UndeadLifestealPaidPipelineTests(unittest.TestCase):
    def test_paid_attack_converts_native_lifesteal_and_allows_normal_turn_end(self):
        origin, enemy = (-23, -143, 70), (-22, -143, 70)
        terrain = native.bounded_arena(
            native.map_geometry(1134), origin, [enemy], radius=12
        )
        character, monster, fight = native.fixture(
            11,
            38,
            enemy,
            terrain,
            origin,
            monster_reference=3646,
            monster_level=12,
        )
        deck = encode_deck([5037], [])
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(7),
            fight_start=True,
        )
        while fight.current.id != 7:
            fight.end_server_turn(fight.current.id, fight.turn_id)
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=2,
            critical=False,
            rng=random.Random(7),
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        invocation = EffectInvocation(
            416673,
            20,
            7,
            7,
            fight.actors[7].position,
            native_retained_container={"present": False},
        )
        # 4805 is the native Multibrazos STATE, not an equipped spell ID.
        # Construct both real carriers and execute their original children.
        for reference, level in ((4805, 20), (61, 1)):
            context = NativeEffectTimingProvider(
                factory.state_catalog
            ).direct_state_reference(
                fight, invocation, reference, level, critical=False
            )
            with fight.effect_resolution():
                dispatcher.native_retention.open_state(invocation)
                try:
                    dispatcher.native_state_handler.apply_reference(
                        None,
                        invocation,
                        reference,
                        level,
                        carrier_context=context,
                        protected=False,
                    )
                finally:
                    dispatcher.native_retention.close_state(invocation)
        states = {
            (entry.reference, entry.level)
            for entry in fight.actors[7].state_ledger.entries
        }
        self.assertIn((4805, 20), states)
        self.assertIn((61, 1), states)
        before = snapshot(fight)
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5037, *origin),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(7),
        )
        self.assertEqual(snapshot(fight), before)
        self.assertLess(result.fight.actors[7].ap, fight.actors[7].ap)
        self.assertLess(result.fight.actors[-7].hp, fight.actors[-7].hp)
        self.assertLess(result.fight.actors[7].hp, fight.actors[7].hp)
        self.assertTrue(
            any(
                event.get("kind") == "damage"
                and event.get("source_id") == event.get("target_id") == 7
                and event.get("amount", 0) > 0
                for event in result.fight.events
            )
        )
        synthetic_damage = []
        for opcode, payload in result.packets:
            if opcode != 12613:
                continue
            try:
                fields = _identity_fields(payload[19:])
            except ValueError:
                continue
            if fields.get(3) == (-3 & ((1 << 64) - 1)):
                synthetic_damage.append(fields)
        self.assertTrue(synthetic_damage, "Missing native initialized eXt child")
        ended, _ = prepare_server_turn_end(
            character,
            {-7: monster},
            result.fight,
            deck,
            actor_id=7,
            action_id=4,
            rng=random.Random(7),
        )
        if ended.phase == "active" and ended.current is not None:
            if ended.current.id == 7:
                ended.end_turn(3, 7, ended.current.turn_count)
            self.assertNotEqual(ended.current.id, 7)
        self.assertIn(ended.phase, ("active", "finished"))
