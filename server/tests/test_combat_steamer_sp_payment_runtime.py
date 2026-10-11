"""Actual Steamer SP cost receipt and insufficient-resource rollback."""
import os
import random
import struct
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerSpPaymentRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt

    def test_actual_stasis_flow_pays_sp_once_and_rejects_unfunded_surge(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = self.fixture(actives=(6922, 6918))
        before_sp = fixture[2].actors[7].effect_stats[123]
        paid = self.cast(fixture, 6922)
        self.assertEqual(
            paid.plan["extra_resource_payment"],
            (dict(stat_id=123, requested_delta=-3, actual_delta=-3),),
        )
        self.assertEqual(paid.fight.actors[7].effect_stats[123], before_sp - 3)
        self.assertEqual(fixture[2].actors[7].effect_stats[123], before_sp)
        character, monster, _, deck, rng = fixture
        before = snapshot(paid.fight)
        rng_before = rng.getstate()
        with self.assertRaisesRegex(
            ValueError, "Insufficient authoritative extra spell resource"
        ):
            prepare_server_spell(
                struct.pack(
                    ">qqiih", 7, (7 << 32) | 6918, *paid.fight.actors[-7].position
                ),
                character,
                {-7: monster},
                paid.fight,
                3,
                deck,
                action_id=3,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(paid.fight), before)
        self.assertEqual(rng.getstate(), rng_before)
