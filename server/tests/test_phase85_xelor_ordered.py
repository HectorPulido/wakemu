"""Actual paid burst, unspent-AP recovery and delayed owner effect across dial death."""
import unittest
import struct
from copy import deepcopy
from wakfu_server.combat_cast import prepare_spell_cast
from wakfu_server.combat_server_spell import server_runtime, prepare_server_spell
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_los import authoritative_visible
from durable_native_fixture import xelor_constructor, assert_native_enemy
from unittest.mock import patch

import test_xelor_runtime_pipeline as fixtures
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot
import json

REVISION = "08523b7b8f2dd2e7c5fcac816bfcc7e31f777beb61acb0d76913bfcd568007f8"


def actual_los(origin, target, fight):
    return authoritative_visible(
        1134,
        origin,
        target,
        fight,
        blocking_footprints={
            actor.id: footprint(actor.position, actor.physical_radius)
            for actor in fight.actors.values()
            if actor.hp > 0
        },
    )


class XelorOrderedUsageTests(unittest.TestCase):
    def test_paid_burst_recovery_and_real_dial_death_preserve_delayed_owner_delivery(
        self,
    ):
        self.assertEqual(native_catalog.release(), REVISION)

        class NativeLOSFixture(fixtures.XelorRuntimePipelineTests):
            def cast(self, data, reference, cell=None, *, action_id=3):
                character, monster, fight, deck, rng = data
                before = snapshot(fight)
                uid = (
                    granted_spells(fight, 7)
                    .get(reference, {})
                    .get("uid", (7 << 32) | reference)
                )
                tx = prepare_server_spell(
                    struct.pack(">qqiih", 7, uid, *(cell or fight.actors[7].position)),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=action_id,
                    line_of_sight=actual_los,
                    critical=False,
                    rng=rng,
                )
                self.assertEqual(snapshot(fight), before)
                self.assertTrue(any(tx.outcomes))
                return tx

        helper = NativeLOSFixture()
        with xelor_constructor(fixtures.native_fixture):
            data = helper.fixture(passives=(758, 761), actives=(754, 775, 2839))
        assert_native_enemy(self, data[2], data[1])
        self.assertEqual(
            (
                data[2].actors[7].ap,
                data[2].actors[7].mp,
                data[2].actors[7].effect_stats[4],
            ),
            (6, 3, 12),
        )
        delayed = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", "340275"
        )
        self.assertIn(1001, delayed["target_masks"][5])
        self.assertIn(2237, delayed["target_masks"][3])
        trace = []
        original = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = original(dispatcher, invocation, **kwargs)
            if invocation.reference in (340275, 340276, 340277, 312719):
                trace.append((invocation.reference, invocation.target_id, result))
            return result

        def cast(reference, cell=None):
            nonlocal data
            tx = helper.cast(data, reference, cell, action_id=20 + len(trace))
            data = helper.adopt(data, tx.fight)
            return tx

        def burst_eligible_dial():
            # The old helper maximizes hour count without considering the next
            # native spell's target geometry. Select among actual lawful dial
            # transactions whose resulting position admits this real754 target.
            character, monster, source, deck, rng = data
            origin = source.actors[7].position
            source_before, rng_before = snapshot(source), rng.getstate()
            rejected = []
            for cell in sorted(source.walkable):
                if not 1 <= abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 3:
                    continue
                if cell[0] != origin[0] and cell[1] != origin[1]:
                    continue
                rng.setstate(rng_before)
                try:
                    tx = helper.cast(data, 5345, cell, action_id=10)
                    hours = [
                        row
                        for row in tx.fight.native_effect_areas.values()
                        if row.get("owner_id") == 7 and 1546 <= row["reference"] <= 1558
                    ]
                    if len(hours) < 12:
                        rejected.append((cell, "fewer than12 actual owned areas"))
                        continue
                    preview = deepcopy(tx.fight)
                    _, adapter = server_runtime(
                        character,
                        {-7: monster},
                        deck,
                        action_id=11,
                        critical=False,
                        rng=rng,
                    )
                    prepare_spell_cast(
                        struct.pack(
                            ">qqiih", 7, (7 << 32) | 754, *preview.actors[-7].position
                        ),
                        character,
                        preview,
                        3,
                        deck,
                        wp=preview.actors[7].effect_stats[4],
                        line_of_sight=actual_los,
                        conditional_context=lambda request, current: adapter.cast_condition(
                            current, request
                        ),
                    )
                except ValueError as error:
                    rejected.append((cell, str(error)))
                    continue
                self.assertEqual(snapshot(source), source_before)
                return tx
            rng.setstate(rng_before)
            self.assertEqual(snapshot(source), source_before)
            self.fail(str({"no lawful dial with actual754 target": rejected}))

        with patch.object(EffectDispatcher, "execute", observe):
            first = burst_eligible_dial()
            born = set(first.fight.actors) - set(data[2].actors)
            self.assertEqual(len(born), 1)
            old_dial = born.pop()
            data = helper.adopt(data, first.fight)
            old_hours = {
                uid
                for uid, row in data[2].native_effect_areas.items()
                if row.get("owner_id") == 7 and 1546 <= row["reference"] <= 1558
            }
            self.assertGreaterEqual(len(old_hours), 12)
            before_wp = data[2].actors[7].effect_stats[4]
            devotion = cast(2839)
            self.assertEqual(devotion.plan["costs"]["wp"], 4)
            self.assertEqual(data[2].actors[7].effect_stats[4], before_wp - 4)
            self.assertIn(7545, helper.states(data[2].actors[7]))
            self.assertFalse(any(ref == 340276 and result for ref, _, result in trace))
            distortion = cast(7794)
            self.assertEqual(distortion.plan["costs"]["wp"], 1)
            self.assertIn(6744, helper.states(data[2].actors[7]))
            before_hp = data[2].actors[-7].hp
            before_ap = data[2].actors[7].ap
            attack = cast(754, data[2].actors[-7].position)
            self.assertEqual(
                data[2].actors[7].ap, before_ap - attack.plan["costs"]["ap"]
            )
            self.assertLess(data[2].actors[-7].hp, before_hp)
            spent_wp = data[2].actors[7].effect_stats[4]
            data = helper.next_owned_turn(data)  # Actual end/ACK/start.
            self.assertEqual(data[2].current.id, 7)
            self.assertGreater(data[2].actors[7].effect_stats[4], spent_wp)
            self.assertNotIn(6744, helper.states(data[2].actors[7]))
            self.assertNotIn(7545, helper.states(data[2].actors[7]))
            self.assertIn((340276, 7, True), trace)
            self.assertIn((312719, 7, True), trace)
            self.assertEqual(data[2].actors[7].max_ap, 9)

            # A genuine recovery turn uses owned Time Theft once and leaves
            # the actual recovered AP unspent. It works after Clockmaking has
            # moved the caster, without inventing a nearby attack recipient.
            ap_before_theft = data[2].actors[7].ap
            theft = cast(3909)
            self.assertEqual(
                (theft.plan["costs"]["ap"], theft.plan["costs"]["wp"]), (0, 1)
            )
            self.assertEqual(data[2].actors[7].ap, ap_before_theft + 1)
            self.assertGreater(data[2].actors[7].ap, 0)
            wp_before_recovery = data[2].actors[7].effect_stats[4]
            self.assertLess(wp_before_recovery, data[2].actors[7].effect_maxima[4])
            data = helper.next_owned_turn(data)
            self.assertEqual(
                data[2].actors[7].effect_stats[4], data[2].actors[7].effect_maxima[4]
            )
            self.assertGreater(data[2].actors[7].effect_stats[4], wp_before_recovery)

            # Schedule again, then use the native replacement spell to actually
            # kill the old dial before the owner's delayed1001 delivery.
            trace.clear()
            cast(2839)
            self.assertIn(7545, helper.states(data[2].actors[7]))
            self.assertFalse(any(ref == 340276 and result for ref, _, result in trace))
            before = snapshot(data[2])
            replaced = helper.dial(data)
            self.assertEqual(snapshot(data[2]), before)
            data = helper.adopt(data, replaced.fight)
            self.assertEqual(data[2].actors[old_dial].hp, 0)
            self.assertTrue(old_hours.isdisjoint(data[2].native_effect_areas))
            self.assertIn(7545, helper.states(data[2].actors[7]))
            current_registry(data[2])
            saved = snapshot(data[2])
            restored = Checkpoints._read_snapshot(json.loads(json.dumps(saved)))
            self.assertEqual(
                restored["native_effect_areas"],
                json.loads(json.dumps(saved["native_effect_areas"])),
            )
            data = helper.next_owned_turn(data)
            self.assertEqual(data[2].current.id, 7)
            self.assertNotIn(7545, helper.states(data[2].actors[7]))
            self.assertEqual(data[2].actors[7].max_ap, 9)
            self.assertEqual(
                sum(
                    ref == 340276 and target == 7 and result
                    for ref, target, result in trace
                ),
                1,
            )
            self.assertNotIn(old_dial, data[2].order)
        self.assertEqual(native_catalog.release(), REVISION)
