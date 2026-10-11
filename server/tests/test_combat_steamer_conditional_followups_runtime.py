"""Native Steamer conditional casting after legitimate resource/state producers."""
import itertools
import math
import struct
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerConditionalFollowupsRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_full_wp_producer_changes_actual_microbot_conditional_variants(self):
        for winding, transport, damage in itertools.product((False, True), repeat=3):
            passives = (6925,) + tuple(
                p
                for p, enabled in ((6926, winding), (6930, transport), (6940, damage))
                if enabled
            )
            with self.subTest(passives=passives):
                data = self.fixture(passives)
                self.assertNotIn(
                    7745, {s.reference for s in data[2].actors[7].state_ledger.entries}
                )
                for _ in range(4):
                    data = self.next_owned_turn(data)
                actor = data[2].actors[7]
                self.assertEqual(actor.effect_stats[4], actor.effect_maxima[4])
                self.assertIn(7745, {s.reference for s in actor.state_ledger.entries})
                result = self.cast(data, 7008)
                flags = result.plan["native_casting_flags"]
                self.assertEqual(
                    (flags["minimum"], flags["maximum"]), (3, 5 if transport else 9)
                )
                self.assertEqual(flags["range_modifiable"], winding and not transport)
                self.assertEqual(result.plan["costs"]["ap"], 0 if transport else 1)
                self.assertEqual(result.plan["costs"]["wp"], 1)
                self.assertEqual(
                    len(result.fight.native_microbot_networks[7]["microbot_ids"]), 1
                )

    def test_turret_reinforcement_and_armor_specialization_change_actual_created_pa(
        self,
    ):
        born = {}
        for passives in ((), (6928,), (6941,)):
            with self.subTest(passives=passives):
                data = self.fixture(passives)
                source = data[2].actors[7]
                result = self.cast(data, 7700)
                turret = next(
                    a
                    for a in result.fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                born[passives] = (turret.max_hp, turret.effect_stats[87], source.max_hp)

        # 343969 swaps caster/target, then 344812 selects the45% branch
        # before the30% fallback343970. eYn rounds float32 to nearest;
        # family20 adds that value to the fresh profile's actual1HP.
        def native_hp(ratio, owner_hp):
            f32 = lambda value: struct.unpack("!f", struct.pack("!f", value))[0]
            return 1 + math.floor(f32(f32(ratio) * f32(owner_hp)) + 0.5)

        self.assertEqual(born[()][0], native_hp(0.3, born[()][2]), born)
        self.assertEqual(born[(6928,)][0], native_hp(0.45, born[(6928,)][2]), born)
        # 344137→344139 belongs to player form7648 (Cannoner), not
        # this turret's initial-state plan. 6941's owned stat87+50 is
        # inherited by fresh turret PA; this cast never applies7648.
        self.assertEqual(born[(6941,)][1] - born[()][1], 50, born)

    def test_literal_false_passive_roots_do_not_execute_but_enabled_callbacks_remain(
        self,
    ):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        execute = EffectDispatcher.execute
        trace = []

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (
                344024,
                344025,
                350970,
                350971,
                350972,
                350973,
                395184,
                395185,
            ):
                trace.append((invocation.reference, result))
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            data = self.fixture((6938, 7810), actives=(6902,))
            result = self.cast(data, 6902, target=data[2].actors[-7].position)
            data = self.next_owned_turn(self.adopt(data, result.fight))
        self.assertFalse(any(ref in (344025, 350971) for ref, _ in trace), trace)
        # 350972/350973 are descendants of 350970's literalFalse,
        # not independent enabled post-cast listeners.
        self.assertFalse(any(ref in (350972, 350973) for ref, _ in trace), trace)
        self.assertTrue(any(ref == 395185 and result for ref, result in trace), trace)
