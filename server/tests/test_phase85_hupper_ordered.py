"""Earn runes, pay Runification, then pay an actual conditional Light Arrow."""
import struct
from durable_native_fixture import hupper_constructor, assert_native_enemy
import unittest

import test_combat_huppermage_runtime as fixtures
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import snapshot

REVISION = "08523b7b8f2dd2e7c5fcac816bfcc7e31f777beb61acb0d76913bfcd568007f8"


class HupperOrderedUsageTests(unittest.TestCase):
    def test_earned_runes_runification_then_conditional_light_arrow_without_topups(
        self,
    ):
        self.assertEqual(native_catalog.release(), REVISION)
        # Reuse initialization, not the historical helper.setUp which selected
        # the latest completed cost release independently of the active release.
        helper = fixtures.HuppermageRuntimeTests()
        for elements, expected_arrow_ap in (
            ((5564,), 5),
            ((5562,), 6),
            ((5562, 5564), 5),
        ):
            with self.subTest(elements=elements):
                with hupper_constructor():
                    data = helper.fixture((*elements, 7809, 5594))
                assert_native_enemy(self, data[2], data[1])
                character, monster, fight, deck, rng = data
                self.assertEqual(fight.actors[7].effect_maxima[111], 500)
                self.assertEqual(fight.actors[7].effect_stats[111], 500)
                action_id = 10

                def cast(reference, target):
                    nonlocal fight, action_id
                    before, rng_before = snapshot(fight), rng.getstate()
                    action_id += 1
                    try:
                        tx = prepare_server_spell(
                            struct.pack(">qqiih", 7, (7 << 32) | reference, *target),
                            character,
                            {-7: monster},
                            fight,
                            3,
                            deck,
                            action_id=action_id,
                            line_of_sight=lambda a, b, p: authoritative_visible(
                                1134, a, b, p
                            ),
                            critical=False,
                            rng=rng,
                        )
                    except Exception:
                        self.assertEqual(snapshot(fight), before)
                        self.assertEqual(rng.getstate(), rng_before)
                        raise
                    self.assertEqual(snapshot(fight), before)
                    self.assertTrue(any(tx.outcomes))
                    fight = tx.fight
                    return tx

                for element in elements:
                    cast(element, fight.actors[-7].position)
                runes = {
                    entry.reference for entry in fight.actors[7].state_ledger.entries
                }
                expected_runes = {
                    4064 if element == 5562 else 4065 for element in elements
                }
                self.assertEqual(runes & {4064, 4065, 4066, 4067}, expected_runes)
                count = len(expected_runes)
                before_qb = fight.actors[7].effect_stats[111]
                before_final = fight.actors[7].effect_stats[48]
                paid = cast(7809, fight.actors[7].position)
                self.assertEqual(
                    paid.plan["extra_resource_payment"],
                    (
                        dict(
                            stat_id=111,
                            requested_delta=-50 * count,
                            actual_delta=-50 * count,
                        ),
                    ),
                )
                self.assertEqual(
                    fight.actors[7].effect_stats[48] - before_final, 10 * count
                )
                # The real consumption children return25QB per consumed rune;
                # distinguish full paid cost from the later earned resource gain.
                self.assertEqual(
                    fight.actors[7].effect_stats[111], before_qb - 25 * count
                )
                self.assertFalse(
                    {entry.reference for entry in fight.actors[7].state_ledger.entries}
                    & {4064, 4065, 4066, 4067}
                )

                resources = native_catalog.record(
                    DATA_ROOT / "native-spell-resource-costs.json", "spells", "5594"
                )
                self.assertEqual(
                    resources["baseline"]["resources"]["111"][
                        fight.actors[7].effective_level
                    ],
                    -200,
                )
                self.assertEqual(
                    resources["baseline"]["resources"]["2"][
                        fight.actors[7].effective_level
                    ],
                    6,
                )
                water_rule = next(
                    row
                    for row in resources["conditional"]
                    if row["criteria"] == "HasState(5372)"
                )
                self.assertEqual(
                    water_rule["resources"]["2"][fight.actors[7].effective_level], 5
                )
                self.assertEqual(
                    water_rule["resources"]["111"][fight.actors[7].effective_level],
                    -200,
                )
                if fight.actors[7].ap < expected_arrow_ap:
                    before, before_rng = snapshot(fight), rng.getstate()
                    with self.assertRaises(ValueError):
                        cast(5594, fight.actors[-7].position)
                    self.assertEqual(snapshot(fight), before)
                    self.assertEqual(rng.getstate(), before_rng)
                    current = (character, monster, fight, deck, rng)
                    turns.AniripsaGrantSummonPipelineTests().next_player_turn(
                        fight, current
                    )
                    self.assertEqual(fight.current.id, 7)
                qb, ap, hp = (
                    fight.actors[7].effect_stats[111],
                    fight.actors[7].ap,
                    fight.actors[-7].hp,
                )
                arrow = cast(5594, fight.actors[-7].position)
                self.assertEqual(arrow.plan["costs"]["ap"], expected_arrow_ap)
                self.assertEqual(
                    arrow.plan["extra_resource_payment"],
                    (dict(stat_id=111, requested_delta=-200, actual_delta=-200),),
                )
                self.assertEqual(fight.actors[7].ap, ap - expected_arrow_ap)
                self.assertEqual(fight.actors[7].effect_stats[111], qb - 200)
                self.assertLess(fight.actors[-7].hp, hp)
        self.assertEqual(native_catalog.release(), REVISION)
