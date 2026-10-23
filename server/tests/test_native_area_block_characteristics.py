"""Actual HP-owning faW targets preserve their native absent BLOCK PA."""
from copy import deepcopy
from random import Random
from types import SimpleNamespace
import unittest

import test_monster_fake_fighter_hp_integration as fixture


class NativeAreaBlockCharacteristicsTests(unittest.TestCase):
    def test_hp_only_faw_uses_own_constructor_without_wall_coercion_or_block_draw(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_ordinary_authority import ordinary_cast_authority

        (
            fight,
            _creator,
            _allocated,
            _packets,
        ) = fixture.FakeFighterHpIntegrationTests().create()
        row = fight.native_effect_areas[901]
        self.assertEqual(row["native_area_contract"], "faW")
        self.assertEqual(row["reference"], 566)
        rng = Random(7)
        authority = ordinary_cast_authority(
            actors=lambda preview, source: None,
            timing=SimpleNamespace(state=lambda *args: None),
            rng=rng,
            critical=False,
        )
        effect = dict(native_effect_flags=[])
        invocation = EffectInvocation(100, 141, 7, 901, row["cell"])
        before = deepcopy(
            {key: value for key, value in row.items() if key != "state_ledger"}
        )
        ledger, entries = row["state_ledger"], tuple(row["state_ledger"].entries)
        rng_before = rng.getstate()
        self.assertFalse(authority.damage_block(fight, {}, effect, invocation))
        self.assertEqual(
            {key: value for key, value in row.items() if key != "state_ledger"}, before
        )
        self.assertIs(row["state_ledger"], ledger)
        self.assertEqual(tuple(ledger.entries), entries)
        self.assertEqual(rng.getstate(), rng_before)
        # The concrete PA remains mandatory; do not turn malformed fake
        # fighters into zero BLOCK by reading a generic default dictionary.
        del row["native_faw_hp_constructor"]
        with self.assertRaises(ValueError):
            authority.damage_block(fight, {}, effect, invocation)
        self.assertEqual(rng.getstate(), rng_before)
