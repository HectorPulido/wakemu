"""Real incoming-damage and owned-tree healing consumers for Sadida passives."""
from copy import deepcopy
import os
import random
import unittest

import test_sadida_remaining_passive_semantics as passive_fixture
import test_combat_spell_transaction as native_fixture
import test_aniripsa_grant_summon_pipeline as lifecycle
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    server_runtime,
)
from wakfu_server.spells import encode_deck


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaReactivePassiveSemanticsTests(unittest.TestCase):
    def test_doll_link_reacts_to_actual_surviving_doll_damage_only_when_equipped(self):
        from wakfu_server.monsters import reference
        from wakfu_server.combat_npc_attack import (
            ability,
            npc_runtime_catalog,
            npc_spell_catalog,
        )

        observations = {}
        for equipped in (False, True):
            with self.subTest(passive=equipped):
                (
                    character,
                    monster,
                    fight,
                ) = native_fixture.SpellTransactionTests().native_server_fixture(
                    10,
                    200,
                    native_qi=True,
                    full_health=True,
                    target_hp=20000,
                    target_level=reference(5525)["max_level"],
                    target_distance=2,
                    variation_seed=17,
                )
                monster["level"] = fight.actors[-7].effective_level
                deck = encode_deck((921,), (916,) if equipped else ())
                rng = random.Random(17)
                fight, packets = prepare_server_initialization(
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=1,
                    rng=rng,
                    fight_start=True,
                )
                helper = passive_fixture.SadidaRemainingPassiveSemanticsTests()
                data = character, monster, fight, deck, rng, packets
                data = helper.seed_transform(data, 921)
                character, monster, fight, deck, rng, _ = data
                doll = helper.profile_actors(fight, 3748)[0]
                turn_helper = lifecycle.AniripsaGrantSummonPipelineTests()
                for _ in range(20):
                    if fight.current.id == -7:
                        break
                    turn_helper.end_current_turn(fight, data[:5])
                self.assertEqual(fight.current.id, -7)
                self.assertEqual(
                    sum(
                        abs(fight.current.position[i] - doll.position[i])
                        for i in (0, 1)
                    ),
                    1,
                )
                before_owner = fight.actors[7].hp
                before_doll = fight.actors[doll.id].hp
                preview = deepcopy(fight)
                rule = ability(monster)
                factory, _ = server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=30,
                    critical=False,
                    rng=rng,
                    compiled=npc_runtime_catalog(),
                )
                dispatcher, _ = factory(
                    preview,
                    dict(
                        actor_id=-7,
                        spell_id=rule["spell_id"],
                        evaluation_level=rule["spell_level"],
                        target_id=doll.id,
                        target=doll.position,
                        costs={key: rule[key] for key in ("ap", "mp", "wp")},
                    ),
                )
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    with preview.effect_resolution():
                        for ref in npc_spell_catalog()["spells"][str(rule["spell_id"])][
                            "levels"
                        ][rule["spell_level"] - 1][2]:
                            dispatcher.execute(
                                EffectInvocation(
                                    ref,
                                    rule["spell_level"],
                                    -7,
                                    doll.id,
                                    doll.position,
                                    native_explicit_target=True,
                                )
                            )
                self.assertGreater(preview.actors[doll.id].hp, 0, trace)
                self.assertLess(preview.actors[doll.id].hp, before_doll, trace)
                selected = [
                    row
                    for row in trace
                    if row.get("effect_reference") == 379545
                    and row.get("status") == "completed"
                ]
                self.assertEqual(bool(selected), equipped, trace)
                self.assertFalse(
                    any(
                        row.get("effect_reference") == 379543
                        and row.get("status") == "completed"
                        for row in trace
                    )
                )
                observations[equipped] = before_owner - preview.actors[7].hp
                self.assertEqual(fight.actors[7].hp, before_owner)
        self.assertEqual(observations[False], 0)
        self.assertGreater(observations[True], 0)

    def test_sylvan_gift_actual_tree_consumption_heals_its_injured_owner(self):
        observations = {}
        helper = passive_fixture.SadidaRemainingPassiveSemanticsTests()
        for equipped in (False, True):
            with self.subTest(passive=equipped):
                data = helper.seed_transform(
                    helper.fixture((917,) if equipped else ()), 8137
                )
                tree = helper.profile_actors(data[2], 5577)[0]
                before = data[2].actors[7].hp
                self.assertLess(before, data[2].actors[7].max_hp)
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    tx = helper.cast(data, 8137, target=tree.position, action_id=12)
                completed = {
                    row.get("effect_reference")
                    for row in trace
                    if row.get("status") == "completed"
                }
                self.assertIn(379675, completed, trace)
                self.assertEqual(379677 in completed, equipped, trace)
                self.assertNotIn(379678, completed, trace)
                self.assertNotIn(379665, completed, trace)
                observations[equipped] = tx.fight.actors[7].hp - before
                self.assertEqual(data[2].actors[7].hp, before)
        self.assertEqual(observations[False], 0)
        self.assertGreater(observations[True], 0)

    def test_sylvan_gift_heal_uses_understanding_ground_cross_shape(self):
        helper = passive_fixture.SadidaRemainingPassiveSemanticsTests()
        for equipped in (False, True):
            with self.subTest(sylvan_gift=equipped):
                passives = (7053, 917) if equipped else (7053,)
                data = helper.seed_transform(helper.fixture(passives), 8137)
                tree = helper.profile_actors(data[2], 5577)[0]
                before = data[2].actors[7].hp
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    tx = helper.cast(data, 8137, target=tree.position, action_id=12)
                completed = {
                    row.get("effect_reference")
                    for row in trace
                    if row.get("status") == "completed"
                }
                self.assertEqual(379678 in completed, equipped, trace)
                self.assertNotIn(379677, completed, trace)
                self.assertNotIn(379665, completed, trace)
                delta = tx.fight.actors[7].hp - before
                self.assertGreater(delta, 0) if equipped else self.assertEqual(delta, 0)
                self.assertEqual(data[2].actors[7].hp, before)
