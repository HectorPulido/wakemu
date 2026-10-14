"""Player-issued Drheller ore actions change actual owned areas and pay costs."""
import os
import struct
import unittest

import test_aniripsa_grant_summon_pipeline as turns
import test_enutrof_runtime as enutrof
from tools.class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EnutrofCompanionActionConsequencesTests(unittest.TestCase):
    def test_four_actual_ore_actions_replace_only_their_owned_deposit_and_pay(self):
        for reference, deposit_reference in (
            (3541, 203),
            (8257, 204),
            (8258, 205),
            (8259, 202),
        ):
            with self.subTest(action=reference, deposit=deposit_reference):
                data = enutrof.EnutrofRuntimeTests().fixture(passives=(8279,))
                character, monster, fight, deck, rng = data
                companion = next(
                    actor
                    for actor in fight.actors.values()
                    if getattr(actor, "native_summon_source", None)
                )
                for _ in range(20):
                    if fight.current.id == companion.id:
                        break
                    turns.AniripsaGrantSummonPipelineTests().end_current_turn(
                        fight, data
                    )
                self.assertEqual(fight.current.id, companion.id)
                deposits = {
                    uid: row
                    for uid, row in fight.native_effect_areas.items()
                    if row["reference"] in (202, 203, 204, 205)
                }
                replaced = {
                    uid
                    for uid, row in deposits.items()
                    if row["owner_id"] == 7 and row["reference"] == deposit_reference
                }
                self.assertTrue(replaced, deposits)

                def los(origin, target, current):
                    return authoritative_visible(
                        character["map_id"],
                        origin,
                        target,
                        current,
                        blocking_footprints={
                            actor.id: {actor.position[:2]}
                            for actor in current.actors.values()
                            if actor.hp > 0
                        },
                    )

                _, adapter = server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=20,
                    critical=False,
                    rng=rng,
                )
                selection = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    reference,
                    actor_id=companion.id,
                    adapter=adapter,
                    line_of_sight=los,
                    limit=256,
                    maximum_eligible=16,
                )
                occupied = {
                    actor.position for actor in fight.actors.values() if actor.hp > 0
                }
                deposit_cells = {tuple(row["cell"]) for row in deposits.values()}
                choices = [
                    row["target"]
                    for row in selection["eligible"]
                    if tuple(row["target"]) not in occupied | deposit_cells
                ]
                self.assertTrue(choices, selection)
                cell = tuple(choices[0])
                before = snapshot(fight)
                resources = (companion.ap, companion.mp, companion.effect_stats[4])
                tx = prepare_server_spell(
                    struct.pack(">qqiih", companion.id, reference, *cell),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=20,
                    line_of_sight=los,
                    critical=False,
                    rng=rng,
                )
                self.assertEqual(snapshot(fight), before)
                self.assertTrue(any(tx.outcomes))
                after = tx.fight.actors[companion.id]
                costs = tx.plan["costs"]
                self.assertEqual(resources[0] - after.ap, costs["ap"])
                self.assertEqual(resources[1] - after.mp, costs["mp"])
                self.assertEqual(resources[2] - after.effect_stats[4], costs["wp"])
                self.assertEqual(after.position, cell)
                self.assertTrue(replaced.isdisjoint(tx.fight.native_effect_areas))
                created = [
                    row
                    for uid, row in tx.fight.native_effect_areas.items()
                    if uid not in fight.native_effect_areas
                    and row["reference"] == deposit_reference
                ]
                self.assertEqual(len(created), 1)
                self.assertEqual(created[0]["owner_id"], 7)
                self.assertEqual(tuple(created[0]["cell"]), cell)
                for uid, row in deposits.items():
                    if uid not in replaced:
                        self.assertEqual(tx.fight.native_effect_areas.get(uid), row)
